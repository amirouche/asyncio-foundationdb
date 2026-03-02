#!/usr/bin/env python3
#
# tester_pthread.py — FoundationDB binding tester stack machine for `found`
#
# POSIX threads variant: START_THREAD spawns OS threads, each with its own
# asyncio event loop.
#
# Implements the stack machine protocol used by the FDB binding tester
# (bindingtester.py) to validate correctness of language bindings.
#
# Invocation: python found/tester_pthread.py <prefix> <api_version> [cluster_file]
#

import asyncio
import struct
import sys
import threading
import traceback

import fdb
import fdb.tuple

import found
from found.base import (
    CONFLICT_RANGE_TYPE_READ,
    CONFLICT_RANGE_TYPE_WRITE,
    KeySelector,
    make_transaction,
)


# ---------------------------------------------------------------------------
# Pending future wrapper — allows the stack to distinguish resolved values
# from coroutines that still need to be awaited.
# ---------------------------------------------------------------------------

class PendingFuture:
    """Wraps an asyncio coroutine or future so the stack can identify it."""

    def __init__(self, coro):
        if asyncio.iscoroutine(coro):
            self._task = asyncio.ensure_future(coro)
        else:
            self._task = coro

    async def resolve(self):
        return await self._task


# ---------------------------------------------------------------------------
# Stack — holds (instruction_index, value) pairs
# ---------------------------------------------------------------------------

class Stack:

    def __init__(self):
        self.items = []

    def push(self, index, value):
        self.items.append((index, value))

    def push_value(self, index, value):
        """Push a raw value, wrapping coroutines as PendingFuture."""
        if asyncio.iscoroutine(value):
            self.items.append((index, PendingFuture(value)))
        else:
            self.items.append((index, value))

    async def pop(self):
        """Pop and resolve the top item. Returns (index, value).
        Futures are awaited; None results become RESULT_NOT_PRESENT;
        FDB errors become tuple-packed ERROR tokens."""
        index, value = self.items.pop()
        if isinstance(value, PendingFuture):
            try:
                value = await value.resolve()
            except found.FoundException as e:
                value = fdb.tuple.pack((b"ERROR", str(e.code).encode("ascii")))
            else:
                if value is None:
                    value = b"RESULT_NOT_PRESENT"
        return index, value

    async def pop_value(self):
        """Pop and return just the resolved value."""
        _, value = await self.pop()
        return value

    def __len__(self):
        return len(self.items)


# ---------------------------------------------------------------------------
# Mutation type name → found function mapping
# ---------------------------------------------------------------------------

ATOMIC_OPCODES = {
    b"ADD": found.base.MUTATION_ADD,
    b"BIT_AND": found.base.MUTATION_BIT_AND,
    b"BIT_OR": found.base.MUTATION_BIT_OR,
    b"BIT_XOR": found.base.MUTATION_BIT_XOR,
    b"APPEND_IF_FITS": found.base.MUTATION_APPEND_IF_FITS,
    b"MAX": found.base.MUTATION_MAX,
    b"MIN": found.base.MUTATION_MIN,
    b"SET_VERSIONSTAMPED_KEY": found.base.MUTATION_SET_VERSIONSTAMPED_KEY,
    b"SET_VERSIONSTAMPED_VALUE": found.base.MUTATION_SET_VERSIONSTAMPED_VALUE,
    b"BYTE_MIN": found.base.MUTATION_BYTE_MIN,
    b"BYTE_MAX": found.base.MUTATION_BYTE_MAX,
    b"COMPARE_AND_CLEAR": found.base.MUTATION_COMPARE_AND_CLEAR,
    # Also handle AND/OR/XOR aliases
    b"AND": found.base.MUTATION_BIT_AND,
    b"OR": found.base.MUTATION_BIT_OR,
    b"XOR": found.base.MUTATION_BIT_XOR,
}

# FDB_TR_OPTION_NEXT_WRITE_NO_WRITE_CONFLICT_RANGE
OPTION_NEXT_WRITE_NO_WRITE_CONFLICT_RANGE = 30


# ---------------------------------------------------------------------------
# Compatibility helper — replaces the removed found.get_range()
# ---------------------------------------------------------------------------

async def _get_range(tx, begin, end, *, limit=0, reverse=False, mode=found.base.STREAMING_MODE_ITERATOR):
    """Collect found.query() into a list with explicit reverse control."""
    return await found.all(found.query(tx, begin, end, limit=limit, reverse=bool(reverse), mode=mode))


# ---------------------------------------------------------------------------
# Tester — reads instructions from FDB and processes them
# ---------------------------------------------------------------------------

class Tester:

    def __init__(self, db, prefix):
        self.db = db
        self.prefix = prefix
        self.stack = Stack()
        self.transactions = {}
        self.tr_name = b"tr"
        self.last_version = 0
        self.threads = []

    def current_transaction(self):
        return self.transactions[self.tr_name]

    def new_transaction(self):
        self.transactions[self.tr_name] = make_transaction(self.db)

    async def run(self):
        self.new_transaction()

        # Read all instructions
        tr = make_transaction(self.db)
        prefix_begin = fdb.tuple.pack((self.prefix,))
        prefix_end = fdb.tuple.pack((self.prefix,)) + b"\xff"
        instructions = await _get_range(tr, prefix_begin, prefix_end)

        for idx, (key, value) in enumerate(instructions):
            op_tuple = fdb.tuple.unpack(value)
            op = op_tuple[0]
            if isinstance(op, str):
                op = op.encode("ascii")

            try:
                await self._process(idx, op, op_tuple)
            except found.FoundException as e:
                self.stack.push(idx, fdb.tuple.pack((b"ERROR", str(e.code).encode("ascii"))))
            except Exception:
                traceback.print_exc()
                print(f"ERROR at instruction {idx}: op={op}", file=sys.stderr)
                raise

        # Wait for all spawned threads
        for t in self.threads:
            t.join()

    async def _process(self, idx, op, op_tuple):
        # Determine the object context (database, snapshot, or transaction)
        obj = None
        is_database = False
        is_snapshot = False

        if op.endswith(b"_DATABASE"):
            op = op[: -len(b"_DATABASE")]
            is_database = True
        elif op.endswith(b"_SNAPSHOT"):
            op = op[: -len(b"_SNAPSHOT")]
            is_snapshot = True

        # --- Stack operations ---

        if op == b"PUSH":
            self.stack.push(idx, op_tuple[1])

        elif op == b"DUP":
            self.stack.items.append(self.stack.items[-1])

        elif op == b"EMPTY_STACK":
            self.stack = Stack()

        elif op == b"SWAP":
            swap_idx = await self.stack.pop_value()
            n = len(self.stack)
            self.stack.items[-1], self.stack.items[n - 1 - swap_idx] = (
                self.stack.items[n - 1 - swap_idx],
                self.stack.items[-1],
            )

        elif op == b"POP":
            await self.stack.pop()

        elif op == b"SUB":
            a = await self.stack.pop_value()
            b = await self.stack.pop_value()
            self.stack.push(idx, a - b)

        elif op == b"CONCAT":
            a = await self.stack.pop_value()
            b = await self.stack.pop_value()
            self.stack.push(idx, a + b)

        elif op == b"WAIT_FUTURE":
            original_idx, value = await self.stack.pop()
            self.stack.push(original_idx, value)

        # --- Transaction management ---

        elif op == b"NEW_TRANSACTION":
            self.new_transaction()

        elif op == b"USE_TRANSACTION":
            name = await self.stack.pop_value()
            self.tr_name = name
            if name not in self.transactions:
                self.transactions[name] = make_transaction(self.db)

        elif op == b"ON_ERROR":
            code = await self.stack.pop_value()
            tx = self.current_transaction()
            coro = found.on_error(tx, code)
            self.stack.push_value(idx, coro)

        elif op == b"COMMIT":
            tx = self.current_transaction()
            coro = found.commit(tx)
            self.stack.push_value(idx, coro)

        elif op == b"RESET":
            found.reset(self.current_transaction())

        elif op == b"CANCEL":
            found.cancel(self.current_transaction())

        # --- Reads ---

        elif op == b"GET":
            key = await self.stack.pop_value()
            if is_database:
                await self._do_database_get(idx, key)
            elif is_snapshot:
                tx = self.current_transaction()
                snap_tx = found.base.Transaction(tx.pointer, tx.db, True, tx.vars)
                result = await found.get(snap_tx, key)
                if result is None:
                    self.stack.push(idx, b"RESULT_NOT_PRESENT")
                else:
                    self.stack.push(idx, result)
            else:
                result = await found.get(self.current_transaction(), key)
                if result is None:
                    self.stack.push(idx, b"RESULT_NOT_PRESENT")
                else:
                    self.stack.push(idx, result)

        elif op == b"GET_KEY":
            key = await self.stack.pop_value()
            or_equal = await self.stack.pop_value()
            offset = await self.stack.pop_value()
            prefix = await self.stack.pop_value()
            ks = KeySelector(key, bool(or_equal), offset)

            if is_database:
                await self._do_database_get_key(idx, ks, prefix)
            elif is_snapshot:
                tx = self.current_transaction()
                snap_tx = found.base.Transaction(tx.pointer, tx.db, True, tx.vars)
                result = await found.get_key(snap_tx, ks)
                result = self._clamp_key(result, prefix)
                self.stack.push(idx, result)
            else:
                result = await found.get_key(self.current_transaction(), ks)
                result = self._clamp_key(result, prefix)
                self.stack.push(idx, result)

        elif op == b"GET_RANGE":
            begin = await self.stack.pop_value()
            end = await self.stack.pop_value()
            limit = await self.stack.pop_value()
            reverse = await self.stack.pop_value()
            mode = await self.stack.pop_value()

            if is_database:
                await self._do_database_get_range(idx, begin, end, limit, reverse, mode)
            elif is_snapshot:
                tx = self.current_transaction()
                snap_tx = found.base.Transaction(tx.pointer, tx.db, True, tx.vars)
                kvs = await _get_range(snap_tx, begin, end, limit=limit, reverse=bool(reverse), mode=mode)
                self.stack.push(idx, self._pack_range(kvs))
            else:
                kvs = await _get_range(self.current_transaction(), begin, end, limit=limit, reverse=bool(reverse), mode=mode)
                self.stack.push(idx, self._pack_range(kvs))

        elif op == b"GET_RANGE_STARTS_WITH":
            prefix_arg = await self.stack.pop_value()
            limit = await self.stack.pop_value()
            reverse = await self.stack.pop_value()
            mode = await self.stack.pop_value()

            begin = prefix_arg
            end = found.next_prefix(prefix_arg)

            if is_database:
                await self._do_database_get_range(idx, begin, end, limit, reverse, mode)
            elif is_snapshot:
                tx = self.current_transaction()
                snap_tx = found.base.Transaction(tx.pointer, tx.db, True, tx.vars)
                kvs = await _get_range(snap_tx, begin, end, limit=limit, reverse=bool(reverse), mode=mode)
                self.stack.push(idx, self._pack_range(kvs))
            else:
                kvs = await _get_range(self.current_transaction(), begin, end, limit=limit, reverse=bool(reverse), mode=mode)
                self.stack.push(idx, self._pack_range(kvs))

        elif op == b"GET_RANGE_SELECTOR":
            begin_key = await self.stack.pop_value()
            begin_or_equal = await self.stack.pop_value()
            begin_offset = await self.stack.pop_value()
            end_key = await self.stack.pop_value()
            end_or_equal = await self.stack.pop_value()
            end_offset = await self.stack.pop_value()
            limit = await self.stack.pop_value()
            reverse = await self.stack.pop_value()
            mode = await self.stack.pop_value()
            prefix = await self.stack.pop_value()

            begin_sel = KeySelector(begin_key, bool(begin_or_equal), begin_offset)
            end_sel = KeySelector(end_key, bool(end_or_equal), end_offset)

            if is_database:
                await self._do_database_get_range_selector(
                    idx, begin_sel, end_sel, limit, reverse, mode, prefix
                )
            elif is_snapshot:
                tx = self.current_transaction()
                snap_tx = found.base.Transaction(tx.pointer, tx.db, True, tx.vars)
                kvs = await _get_range(snap_tx, begin_sel, end_sel, limit=limit, reverse=bool(reverse), mode=mode)
                self.stack.push(idx, self._pack_range(kvs, prefix))
            else:
                kvs = await _get_range(self.current_transaction(), begin_sel, end_sel, limit=limit, reverse=bool(reverse), mode=mode)
                self.stack.push(idx, self._pack_range(kvs, prefix))

        # --- Version operations ---

        elif op == b"GET_READ_VERSION":
            if is_snapshot:
                tx = self.current_transaction()
                snap_tx = found.base.Transaction(tx.pointer, tx.db, True, tx.vars)
                self.last_version = await found.read_version(snap_tx)
            else:
                self.last_version = await found.read_version(self.current_transaction())
            self.stack.push(idx, b"GOT_READ_VERSION")

        elif op == b"SET_READ_VERSION":
            await found.set_read_version(self.current_transaction(), self.last_version)

        elif op == b"GET_COMMITTED_VERSION":
            self.last_version = found.get_committed_version(self.current_transaction())
            self.stack.push(idx, b"GOT_COMMITTED_VERSION")

        elif op == b"GET_APPROXIMATE_SIZE":
            await found.get_approximate_size(self.current_transaction())
            self.stack.push(idx, b"GOT_APPROXIMATE_SIZE")

        elif op == b"GET_VERSIONSTAMP":
            tx = self.current_transaction()
            coro = found.get_versionstamp(tx)
            self.stack.push_value(idx, coro)

        # --- Writes ---

        elif op == b"SET":
            key = await self.stack.pop_value()
            value = await self.stack.pop_value()
            if is_database:
                await self._do_database_set(idx, key, value)
            else:
                await found.set(self.current_transaction(), key, value)

        elif op == b"CLEAR":
            key = await self.stack.pop_value()
            if is_database:
                await self._do_database_clear(idx, key)
            else:
                await found.clear(self.current_transaction(), key)

        elif op == b"CLEAR_RANGE":
            begin = await self.stack.pop_value()
            end = await self.stack.pop_value()
            if is_database:
                await self._do_database_clear_range(idx, begin, end)
            else:
                await found.clear(self.current_transaction(), begin, end)

        elif op == b"CLEAR_RANGE_STARTS_WITH":
            prefix_arg = await self.stack.pop_value()
            begin = prefix_arg
            end = found.next_prefix(prefix_arg)
            if is_database:
                await self._do_database_clear_range(idx, begin, end)
            else:
                await found.clear(self.current_transaction(), begin, end)

        elif op == b"ATOMIC_OP":
            op_type = await self.stack.pop_value()
            key = await self.stack.pop_value()
            value = await self.stack.pop_value()
            if isinstance(op_type, str):
                op_type = op_type.encode("ascii")
            opcode = ATOMIC_OPCODES[op_type]
            if is_database:
                await self._do_database_atomic_op(idx, opcode, key, value)
            else:
                found.base._atomic(self.current_transaction(), opcode, key, value)

        # --- Conflict ranges ---

        elif op == b"READ_CONFLICT_RANGE":
            begin = await self.stack.pop_value()
            end = await self.stack.pop_value()
            found.add_conflict_range(
                self.current_transaction(), begin, end, CONFLICT_RANGE_TYPE_READ
            )
            self.stack.push(idx, b"SET_CONFLICT_RANGE")

        elif op == b"WRITE_CONFLICT_RANGE":
            begin = await self.stack.pop_value()
            end = await self.stack.pop_value()
            found.add_conflict_range(
                self.current_transaction(), begin, end, CONFLICT_RANGE_TYPE_WRITE
            )
            self.stack.push(idx, b"SET_CONFLICT_RANGE")

        elif op == b"READ_CONFLICT_KEY":
            key = await self.stack.pop_value()
            found.add_conflict_range(
                self.current_transaction(), key, key + b"\x00", CONFLICT_RANGE_TYPE_READ
            )
            self.stack.push(idx, b"SET_CONFLICT_KEY")

        elif op == b"WRITE_CONFLICT_KEY":
            key = await self.stack.pop_value()
            found.add_conflict_range(
                self.current_transaction(), key, key + b"\x00", CONFLICT_RANGE_TYPE_WRITE
            )
            self.stack.push(idx, b"SET_CONFLICT_KEY")

        elif op == b"DISABLE_WRITE_CONFLICT":
            found.set_option(
                self.current_transaction(),
                OPTION_NEXT_WRITE_NO_WRITE_CONFLICT_RANGE,
            )

        # --- Size estimation ---

        elif op == b"GET_ESTIMATED_RANGE_SIZE":
            begin = await self.stack.pop_value()
            end = await self.stack.pop_value()
            await found.estimated_size_bytes(self.current_transaction(), begin, end)
            self.stack.push(idx, b"GOT_ESTIMATED_RANGE_SIZE")

        elif op == b"GET_RANGE_SPLIT_POINTS":
            begin = await self.stack.pop_value()
            end = await self.stack.pop_value()
            chunk_size = await self.stack.pop_value()
            await found.base.get_range_split_points(
                self.current_transaction(), begin, end, chunk_size
            )
            self.stack.push(idx, b"GOT_RANGE_SPLIT_POINTS")

        # --- Tuple operations ---

        elif op == b"TUPLE_PACK":
            count = await self.stack.pop_value()
            items = []
            for _ in range(count):
                items.append(await self.stack.pop_value())
            self.stack.push(idx, fdb.tuple.pack(tuple(items)))

        elif op == b"TUPLE_PACK_WITH_VERSIONSTAMP":
            prefix_arg = await self.stack.pop_value()
            count = await self.stack.pop_value()
            items = []
            for _ in range(count):
                items.append(await self.stack.pop_value())
            if not fdb.tuple.has_incomplete_versionstamp(tuple(items)):
                self.stack.push(idx, b"ERROR: NONE")
            else:
                try:
                    packed = fdb.tuple.pack_with_versionstamp(tuple(items), prefix=prefix_arg)
                    self.stack.push(idx, b"OK")
                    self.stack.push(idx, packed)
                except ValueError as e:
                    if str(e).startswith("No incomplete"):
                        self.stack.push(idx, b"ERROR: NONE")
                    else:
                        self.stack.push(idx, b"ERROR: MULTIPLE")

        elif op == b"TUPLE_UNPACK":
            data = await self.stack.pop_value()
            items = fdb.tuple.unpack(data)
            for item in items:
                self.stack.push(idx, fdb.tuple.pack((item,)))

        elif op == b"TUPLE_SORT":
            count = await self.stack.pop_value()
            items = []
            for _ in range(count):
                items.append(await self.stack.pop_value())
            # Items are already tuple-packed bytes (e.g. from TUPLE_UNPACK).
            # Unpack each, sort by pack, then re-pack (matching reference tester).
            unpacked = [fdb.tuple.unpack(item) for item in items]
            unpacked.sort(key=fdb.tuple.pack)
            for item in unpacked:
                self.stack.push(idx, fdb.tuple.pack(item))

        elif op == b"TUPLE_RANGE":
            count = await self.stack.pop_value()
            items = []
            for _ in range(count):
                items.append(await self.stack.pop_value())
            r = fdb.tuple.range(tuple(items))
            self.stack.push(idx, r.start)
            self.stack.push(idx, r.stop)

        elif op == b"ENCODE_FLOAT":
            data = await self.stack.pop_value()
            val = struct.unpack(">f", data)[0]
            self.stack.push(idx, fdb.tuple.SingleFloat(val))

        elif op == b"ENCODE_DOUBLE":
            data = await self.stack.pop_value()
            val = struct.unpack(">d", data)[0]
            self.stack.push(idx, val)

        elif op == b"DECODE_FLOAT":
            val = await self.stack.pop_value()
            f = val.value if isinstance(val, fdb.tuple.SingleFloat) else float(val)
            self.stack.push(idx, struct.pack(">f", f))

        elif op == b"DECODE_DOUBLE":
            val = await self.stack.pop_value()
            self.stack.push(idx, struct.pack(">d", val))

        # --- Threading ---

        elif op == b"START_THREAD":
            prefix_arg = await self.stack.pop_value()
            t = threading.Thread(target=_run_tester_thread, args=(self.db, prefix_arg))
            t.start()
            self.threads.append(t)

        elif op == b"WAIT_EMPTY":
            prefix_arg = await self.stack.pop_value()
            await self._wait_empty(prefix_arg)
            self.stack.push(idx, b"WAITED_FOR_EMPTY")

        elif op == b"LOG_STACK":
            prefix_arg = await self.stack.pop_value()
            await self._log_stack(prefix_arg)

        elif op == b"UNIT_TESTS":
            pass  # No-op for now

        else:
            raise ValueError(f"Unknown operation: {op}")

    # --- Helper methods ---

    def _clamp_key(self, result, prefix):
        """Clamp a get_key result to the prefix range."""
        if result.startswith(prefix):
            return result
        if result < prefix:
            return prefix
        # result >= next_prefix(prefix)
        return found.next_prefix(prefix)

    def _pack_range(self, kvs, prefix=None):
        """Pack a list of (key, value) pairs into a single tuple-packed blob."""
        items = []
        for k, v in kvs:
            if prefix is not None and not k.startswith(prefix):
                continue
            items.append(k)
            items.append(v)
        return fdb.tuple.pack(tuple(items))

    async def _wait_empty(self, prefix):
        """Poll until no keys exist with the given prefix."""
        while True:
            tr = make_transaction(self.db)
            begin = prefix
            end = found.next_prefix(prefix)
            kvs = await _get_range(tr, begin, end, limit=1)
            if len(kvs) == 0:
                return
            await asyncio.sleep(0.1)

    async def _log_stack(self, prefix):
        """Drain the entire stack, writing entries to FDB in batches."""
        entries = []
        while len(self.stack) > 0:
            stack_idx, value = await self.stack.pop()
            entries.append((stack_idx, value))

        entries.reverse()  # We popped in reverse order
        batch_size = 100
        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            tr = make_transaction(self.db)
            for j, (stack_idx, value) in enumerate(batch):
                key = prefix + fdb.tuple.pack((i + j, stack_idx))
                packed = fdb.tuple.pack((value,))[:40000]
                await found.set(tr, key, packed)
            await found.commit(tr)

    # --- Database-level operations (auto-transact with retry) ---

    async def _db_transact(self, func):
        """Run func(tx) with automatic retry on retryable errors."""
        tx = make_transaction(self.db)
        while True:
            try:
                result = await func(tx)
                return result
            except found.FoundException as e:
                await found.on_error(tx, e.code)

    async def _do_database_get(self, idx, key):
        async def op(tx):
            return await found.get(tx, key)
        result = await self._db_transact(op)
        if result is None:
            self.stack.push(idx, b"RESULT_NOT_PRESENT")
        else:
            self.stack.push(idx, result)

    async def _do_database_get_key(self, idx, ks, prefix):
        async def op(tx):
            return await found.get_key(tx, ks)
        result = await self._db_transact(op)
        result = self._clamp_key(result, prefix)
        self.stack.push(idx, result)

    async def _do_database_get_range(self, idx, begin, end, limit, reverse, mode):
        async def op(tx):
            return await _get_range(tx, begin, end, limit=limit, reverse=bool(reverse), mode=mode)
        kvs = await self._db_transact(op)
        self.stack.push(idx, self._pack_range(kvs))

    async def _do_database_get_range_selector(self, idx, begin_sel, end_sel, limit, reverse, mode, prefix):
        async def op(tx):
            return await _get_range(tx, begin_sel, end_sel, limit=limit, reverse=bool(reverse), mode=mode)
        kvs = await self._db_transact(op)
        self.stack.push(idx, self._pack_range(kvs, prefix))

    async def _do_database_set(self, idx, key, value):
        async def op(tx):
            await found.set(tx, key, value)
            await found.commit(tx)
        await self._db_transact(op)
        self.stack.push(idx, b"RESULT_NOT_PRESENT")

    async def _do_database_clear(self, idx, key):
        async def op(tx):
            await found.clear(tx, key)
            await found.commit(tx)
        await self._db_transact(op)
        self.stack.push(idx, b"RESULT_NOT_PRESENT")

    async def _do_database_clear_range(self, idx, begin, end):
        async def op(tx):
            await found.clear(tx, begin, end)
            await found.commit(tx)
        await self._db_transact(op)
        self.stack.push(idx, b"RESULT_NOT_PRESENT")

    async def _do_database_atomic_op(self, idx, opcode, key, value):
        async def op(tx):
            found.base._atomic(tx, opcode, key, value)
            await found.commit(tx)
        await self._db_transact(op)
        self.stack.push(idx, b"RESULT_NOT_PRESENT")


# ---------------------------------------------------------------------------
# Thread helper — each thread gets its own event loop
# ---------------------------------------------------------------------------

def _run_tester_thread(db, prefix):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        tester = Tester(db, prefix)
        loop.run_until_complete(tester.run())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main():
    prefix = sys.argv[1]
    if isinstance(prefix, str):
        prefix = prefix.encode("ascii")

    cluster_file = sys.argv[3] if len(sys.argv) > 3 else None
    db = await found.open(cluster_file)

    tester = Tester(db, prefix)
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
