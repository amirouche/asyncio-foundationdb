"""Asyncio bridge for FoundationDB via CFFI."""
#
# base.py — asyncio bridge for FoundationDB via CFFI
#
# Forked from https://github.com/amirouche/asyncio-foundationdb
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018-2026 Amirouche Boubekki <amirouche.boubekki@gmail.com>
#
# Licensed under the Apache License, Version 2.0
#

import asyncio
import atexit
import struct
import threading
from collections import namedtuple

from found._fdb import ffi, lib

assert struct.calcsize("P") == 8, "found requires a 64-bit Python interpreter"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BaseFoundException(Exception):
    pass


class FoundException(BaseFoundException):
    """Exception raised when FoundationDB returns an error."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code

    def __repr__(self):
        description = ffi.string(lib.fdb_get_error(self.code)).decode("utf-8")
        return "<FoundException {} ({})>".format(description, self.code)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def next_prefix(key):
    """Compute the smallest bytes sequence that does not start with key."""
    key = key.rstrip(b"\xff")
    if len(key) == 0:
        raise ValueError("Key must contain at least one byte not equal to 0xFF.")
    return key[:-1] + bytes((key[-1] + 1,))


def _check(code):
    if code != 0:
        raise FoundException(code)


# ---------------------------------------------------------------------------
# Network thread — one per process, started once
#
# CHANGE: _loop is no longer a module-level global captured at _init() time.
# Each call-site now uses asyncio.get_running_loop() to get the loop that is
# actually running the coroutine.  This is necessary because:
#
#   1. asyncio.get_event_loop() is deprecated as a way to get a running loop
#      (it emits DeprecationWarning in 3.10+ when there is no current loop).
#   2. The old code would silently use a stale loop reference if _init() was
#      called before the real application loop started (e.g. at import time).
#   3. A single process might legitimately run successive event loops
#      (e.g. in tests), and each `await` should resolve on the loop that
#      issued it.
#
# The callbacks use a (loop, future) pair stored as a CFFI handle so they
# always call back into the right loop regardless of which one is "current".
# ---------------------------------------------------------------------------

_network_thread = None
_network_thread_lock = threading.Lock()


class _NetworkThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="fdb-network")

    def run(self):
        _check(lib.fdb_run_network())


def _ensure_network():
    """Start the FDB network thread exactly once (thread-safe)."""
    global _network_thread
    with _network_thread_lock:
        if _network_thread is not None:
            return
        _check(lib.fdb_setup_network())
        _network_thread = _NetworkThread()
        _network_thread.start()


@atexit.register
def _stop_network():
    if _network_thread is not None:
        _check(lib.fdb_stop_network())
        _network_thread.join()


# ---------------------------------------------------------------------------
# Core bridge helper
#
# CHANGE: instead of storing just the asyncio Future as a CFFI handle, we now
# store a (loop, future) pair.  This way every C callback has an unambiguous
# reference to the loop it must call back into, without relying on a stale
# module-level _loop variable.
#
# We also keep the handle alive by storing it in a dict keyed by the FDB
# future pointer, and remove it once the callback fires.  In the original
# code the handle was a local variable in the calling coroutine, kept alive
# only because CFFI held a borrowed reference — that is technically fine but
# relies on CPython's refcount behaviour in a way that is hard to audit.
# ---------------------------------------------------------------------------

# fdb_future_ptr (int) -> cffi handle object
_pending_handles: dict = {}
_pending_handles_lock = threading.Lock()


def _register_callback(fdb_future, callback, loop, aio_future):
    """
    Wire up a CFFI callback so that when fdb_future is ready it resolves
    aio_future on the given loop.

    Returns the aio_future so callers can `await` it directly.
    """
    pair = (loop, aio_future)
    handle = ffi.new_handle(pair)
    # Keep the handle alive until the callback fires
    key = int(ffi.cast("uintptr_t", fdb_future))
    with _pending_handles_lock:
        _pending_handles[key] = handle
    lib.fdb_future_set_callback(fdb_future, callback, handle)
    return aio_future


def _release_handle(fdb_future):
    key = int(ffi.cast("uintptr_t", fdb_future))
    with _pending_handles_lock:
        _pending_handles.pop(key, None)


# ---------------------------------------------------------------------------
# CFFI callbacks
#
# CHANGE: every callback now unpacks the (loop, future) pair from the handle
# instead of relying on the module-global _loop.  The fdb_future is destroyed
# *before* scheduling the asyncio callback so the C memory is released as
# early as possible, and we don't risk it being accessed after Python resumes.
# ---------------------------------------------------------------------------

@ffi.callback("void(FDBFuture *, void *)")
def _cb_watch(fdb_future, handle):
    loop, aio_future = ffi.from_handle(handle)
    error = lib.fdb_future_get_error(fdb_future)
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, None)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_get(fdb_future, handle):
    loop, aio_future = ffi.from_handle(handle)
    present = ffi.new("fdb_bool_t *")
    value = ffi.new("uint8_t **")
    value_length = ffi.new("int *")
    error = lib.fdb_future_get_value(fdb_future, present, value, value_length)
    if error == 0:
        if present[0]:
            # Copy the bytes out before destroying the future
            out = bytes(ffi.buffer(value[0], value_length[0]))
        else:
            out = None
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, out)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_get_range(fdb_future, handle):
    loop, aio_future = ffi.from_handle(handle)
    kvs = ffi.new("FDBKeyValue **")
    count = ffi.new("int *")
    more = ffi.new("fdb_bool_t *")
    error = lib.fdb_future_get_keyvalue_array(fdb_future, kvs, count, more)
    if error == 0:
        out = []
        copy = kvs[0][0:count[0]]
        for kv in copy:
            # Manual struct unpacking — CFFI does not respect FDBKeyValue's
            # actual packing on all platforms (see original XXX comment).
            # Layout: key_ptr(8) key_len(4) value_ptr(8) value_len(4) = 24
            memory = ffi.buffer(ffi.addressof(kv), 24)
            key_ptr, key_length, value_ptr, value_length = struct.unpack(
                "=qiqi", memory
            )
            key = bytes(ffi.buffer(ffi.cast("char *", key_ptr), key_length))
            value = bytes(ffi.buffer(ffi.cast("char *", value_ptr), value_length))
            out.append((key, value))
        result = (out, count[0], bool(more[0]))
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, result)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_int64(fdb_future, handle):
    """Generic callback for operations that resolve to an int64."""
    loop, aio_future = ffi.from_handle(handle)
    pointer = ffi.new("int64_t *")
    error = lib.fdb_future_get_int64(fdb_future, pointer)
    result = pointer[0]
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, result)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_get_key(fdb_future, handle):
    """Callback for fdb_transaction_get_key — copies key bytes from the future."""
    loop, aio_future = ffi.from_handle(handle)
    key = ffi.new("uint8_t const **")
    key_length = ffi.new("int *")
    error = lib.fdb_future_get_key(fdb_future, key, key_length)
    if error == 0:
        out = bytes(ffi.buffer(key[0], key_length[0]))
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, out)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_get_key_array(fdb_future, handle):
    """Callback for fdb_future_get_key_array — returns a list of bytes keys.

    Requires a 64-bit Python interpreter (pointer size == 8 bytes).
    FDBKey is #pragma pack(4): pointer(8) + int(4) = 12 bytes, no trailing pad.
    We unpack manually (same strategy as _cb_get_range / FDBKeyValue) to avoid
    any CFFI-vs-compiler layout disagreement."""
    loop, aio_future = ffi.from_handle(handle)
    keys = ffi.new("FDBKey const **")
    count = ffi.new("int *")
    error = lib.fdb_future_get_key_array(fdb_future, keys, count)
    if error == 0:
        out = []
        if count[0] > 0:
            copy = keys[0][0:count[0]]
            for k in copy:
                # Layout with pack(4): key_ptr(8) key_len(4) = 12 bytes
                memory = ffi.buffer(ffi.addressof(k), 12)
                key_ptr, key_length = struct.unpack("=qi", memory)
                out.append(bytes(ffi.buffer(ffi.cast("char *", key_ptr), key_length)))
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, out)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_get_string_array(fdb_future, handle):
    """Callback for fdb_future_get_string_array — returns a list of UTF-8 strings."""
    loop, aio_future = ffi.from_handle(handle)
    strings = ffi.new("const char ***")
    count = ffi.new("int *")
    error = lib.fdb_future_get_string_array(fdb_future, strings, count)
    if error == 0:
        out = []
        for i in range(count[0]):
            out.append(ffi.string(strings[0][i]).decode("utf-8"))
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, out)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


@ffi.callback("void(FDBFuture *, void *)")
def _cb_error(fdb_future, handle):
    """Used for fdb_transaction_on_error — resolves to None or raises."""
    loop, aio_future = ffi.from_handle(handle)
    error = lib.fdb_future_get_error(fdb_future)
    _release_handle(fdb_future)
    lib.fdb_future_destroy(fdb_future)
    if error == 0:
        loop.call_soon_threadsafe(aio_future.set_result, None)
    else:
        loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))


# ---------------------------------------------------------------------------
# Streaming constants
# ---------------------------------------------------------------------------

STREAMING_MODE_WANT_ALL = -2
STREAMING_MODE_ITERATOR = -1
STREAMING_MODE_EXACT = 0
STREAMING_MODE_SMALL = 1
STREAMING_MODE_MEDIUM = 2
STREAMING_MODE_LARGE = 3
STREAMING_MODE_SERIAL = 4


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

Transaction = namedtuple("Transaction", ("pointer", "db", "snapshot", "vars"))


def _make_transaction(db, snapshot=False):
    out = ffi.new("FDBTransaction **")
    lib.fdb_database_create_transaction(db.pointer, out)
    out = ffi.gc(out[0], lib.fdb_transaction_destroy)
    return Transaction(out, db, snapshot, dict())


# ---------------------------------------------------------------------------
# Public async API
#
# CHANGE: every coroutine now calls asyncio.get_running_loop() at the point
# of suspension rather than reading the stale module-level _loop.
# ---------------------------------------------------------------------------

async def read_version(tx):
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_read_version(tx.pointer)
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_int64, loop, aio_future)
    return await aio_future


async def get(tx, key):
    assert isinstance(tx, Transaction)
    assert isinstance(key, bytes)
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get(tx.pointer, key, len(key), tx.snapshot)
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_get, loop, aio_future)
    return await aio_future


# ---------------------------------------------------------------------------
# Key selectors
# ---------------------------------------------------------------------------

KeySelector = namedtuple("KeySelector", ("key", "or_equal", "offset"))


def lt(key, offset=0):
    assert isinstance(key, bytes)
    return KeySelector(key, False, offset)


def lte(key, offset=0):
    assert isinstance(key, bytes)
    return KeySelector(key, True, offset)


def gt(key, offset=1):
    assert isinstance(key, bytes)
    return KeySelector(key, True, offset)


def gte(key, offset=1):
    assert isinstance(key, bytes)
    # BUG FIX: original returned KeySelector(key, False, 1) ignoring `offset`
    return KeySelector(key, False, offset)


# ---------------------------------------------------------------------------
# Range query — async generator
# ---------------------------------------------------------------------------

async def query(tx, key, other, *, limit=0, mode=STREAMING_MODE_ITERATOR):
    loop = asyncio.get_running_loop()

    key = key if isinstance(key, KeySelector) else gte(key)
    other = other if isinstance(other, KeySelector) else gte(other)

    if key.key < other.key:
        begin, end, reverse = key, other, False
    else:
        begin = KeySelector(other.key, False, other.offset)
        end = KeySelector(key.key, True, key.offset)
        reverse = True

    iteration = 1
    snapshot = tx.snapshot

    while True:
        fdb_future = lib.fdb_transaction_get_range(
            tx.pointer,
            begin.key, len(begin.key), begin.or_equal, begin.offset,
            end.key,   len(end.key),   end.or_equal,   end.offset,
            limit, 0, mode, iteration, snapshot, reverse,
        )
        aio_future = loop.create_future()
        _register_callback(fdb_future, _cb_get_range, loop, aio_future)
        kvs, count, more = await aio_future

        if count == 0:
            return

        for i, kv in enumerate(kvs):
            yield kv

            if i == count - 1:
                if not more or limit == count:
                    return
                iteration += 1
                if limit > 0:
                    limit -= count
                if reverse:
                    end = gte(kv[0])
                else:
                    begin = gt(kv[0])


# ---------------------------------------------------------------------------
# Estimated size
# ---------------------------------------------------------------------------

async def estimated_size_bytes(tx, begin, end):
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_estimated_range_size_bytes(
        tx.pointer, begin, len(begin), end, len(end)
    )
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_int64, loop, aio_future)
    return await aio_future


# ---------------------------------------------------------------------------
# Writes (synchronous at the C level, wrapped as coroutines for API uniformity)
# ---------------------------------------------------------------------------

async def set_read_version(tx, version):
    assert not tx.snapshot
    lib.fdb_transaction_set_read_version(tx.pointer, version)


async def set(tx, key, value):
    assert isinstance(tx, Transaction)
    assert isinstance(key, bytes)
    assert isinstance(value, bytes)
    assert not tx.snapshot
    lib.fdb_transaction_set(tx.pointer, key, len(key), value, len(value))


async def clear(tx, key, other=None):
    assert isinstance(tx, Transaction)
    assert isinstance(key, bytes)
    if other is None:
        lib.fdb_transaction_clear(tx.pointer, key, len(key))
    else:
        assert isinstance(other, bytes)
        lib.fdb_transaction_clear_range(tx.pointer, key, len(key), other, len(other))


# ---------------------------------------------------------------------------
# Atomic mutations
# ---------------------------------------------------------------------------

MUTATION_ADD = 2
MUTATION_BIT_AND = 6
MUTATION_BIT_OR = 7
MUTATION_BIT_XOR = 8
MUTATION_APPEND_IF_FITS = 9
MUTATION_MAX = 12
MUTATION_MIN = 13
MUTATION_SET_VERSIONSTAMPED_KEY = 14
MUTATION_SET_VERSIONSTAMPED_VALUE = 15
MUTATION_BYTE_MIN = 16
MUTATION_BYTE_MAX = 17
MUTATION_COMPARE_AND_CLEAR = 20


def _atomic(tx, opcode, key, param):
    lib.fdb_transaction_atomic_op(tx.pointer, key, len(key), param, len(param), opcode)


async def add(tx, key, param):                    _atomic(tx, MUTATION_ADD, key, param)
async def bit_and(tx, key, param):                _atomic(tx, MUTATION_BIT_AND, key, param)
async def bit_or(tx, key, param):                 _atomic(tx, MUTATION_BIT_OR, key, param)
async def bit_xor(tx, key, param):                _atomic(tx, MUTATION_BIT_XOR, key, param)
async def max(tx, key, param):                    _atomic(tx, MUTATION_MAX, key, param)
async def byte_max(tx, key, param):               _atomic(tx, MUTATION_BYTE_MAX, key, param)
async def min(tx, key, param):                    _atomic(tx, MUTATION_MIN, key, param)
async def byte_min(tx, key, param):               _atomic(tx, MUTATION_BYTE_MIN, key, param)
async def append_if_fits(tx, key, param):          _atomic(tx, MUTATION_APPEND_IF_FITS, key, param)
async def compare_and_clear(tx, key, param):       _atomic(tx, MUTATION_COMPARE_AND_CLEAR, key, param)
async def set_versionstamped_key(tx, key, param): _atomic(tx, MUTATION_SET_VERSIONSTAMPED_KEY, key, param)
async def set_versionstamped_value(tx, key, param): _atomic(tx, MUTATION_SET_VERSIONSTAMPED_VALUE, key, param)


# ---------------------------------------------------------------------------
# Commit and retry loop
# ---------------------------------------------------------------------------

async def _commit(tx):
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_commit(tx.pointer)
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_watch, loop, aio_future)
    await aio_future


async def commit(tx):
    """Public commit — same as _commit."""
    await _commit(tx)


async def on_error(tx, code):
    """Wraps fdb_transaction_on_error. Returns when the transaction can be retried,
    or raises if the error is not retryable."""
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_on_error(tx.pointer, code)
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_error, loop, aio_future)
    await aio_future


def reset(tx):
    """Wraps fdb_transaction_reset (synchronous)."""
    lib.fdb_transaction_reset(tx.pointer)


def cancel(tx):
    """Wraps fdb_transaction_cancel (synchronous)."""
    lib.fdb_transaction_cancel(tx.pointer)


def get_committed_version(tx):
    """Wraps fdb_transaction_get_committed_version (synchronous, returns int64)."""
    version = ffi.new("int64_t *")
    _check(lib.fdb_transaction_get_committed_version(tx.pointer, version))
    return version[0]


async def get_approximate_size(tx):
    """Wraps fdb_transaction_get_approximate_size (async future -> int64)."""
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_approximate_size(tx.pointer)
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_int64, loop, aio_future)
    return await aio_future


async def get_versionstamp(tx):
    """Wraps fdb_transaction_get_versionstamp (async future -> key bytes).
    Must be called after commit."""
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_versionstamp(tx.pointer)
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_get_key, loop, aio_future)
    return await aio_future


async def get_key(tx, key_selector):
    """Wraps fdb_transaction_get_key (async future -> key bytes)."""
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_key(
        tx.pointer,
        key_selector.key, len(key_selector.key),
        key_selector.or_equal, key_selector.offset,
        tx.snapshot,
    )
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_get_key, loop, aio_future)
    return await aio_future



def add_conflict_range(tx, begin, end, conflict_type):
    """Wraps fdb_transaction_add_conflict_range (synchronous)."""
    _check(lib.fdb_transaction_add_conflict_range(
        tx.pointer, begin, len(begin), end, len(end), conflict_type
    ))


def set_option(tx, option, value=None):
    """Wraps fdb_transaction_set_option."""
    if value is None:
        _check(lib.fdb_transaction_set_option(tx.pointer, option, ffi.NULL, 0))
    else:
        _check(lib.fdb_transaction_set_option(tx.pointer, option, value, len(value)))


# Conflict range type constants
CONFLICT_RANGE_TYPE_READ = 0
CONFLICT_RANGE_TYPE_WRITE = 1


async def get_range_split_points(tx, begin, end, chunk_size):
    """Wraps fdb_transaction_get_range_split_points.

    Returns a list of bytes keys that divide the range [begin, end) into
    chunks of approximately chunk_size bytes each."""
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_range_split_points(
        tx.pointer, begin, len(begin), end, len(end), chunk_size
    )
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_get_key_array, loop, aio_future)
    return await aio_future


def watch(tx, key):
    """Wraps fdb_transaction_watch.

    Registers a watch on key immediately (synchronous C call) and returns an
    asyncio.Future that resolves to None when the key is next modified by
    another transaction.

    The watch only detects external changes after the transaction that created
    it has been committed. Typical usage:

        watch_future = found.watch(tx, key)
        await found.commit(tx)            # activates the watch
        # ... in another task, modify the key ...
        await watch_future                # waits until the key changes

    key must be bytes."""
    assert isinstance(key, bytes)
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_watch(tx.pointer, key, len(key))
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_watch, loop, aio_future)
    return aio_future


async def get_addresses_for_key(tx, key):
    """Wraps fdb_transaction_get_addresses_for_key (async future -> list of strings)."""
    assert isinstance(key, bytes)
    loop = asyncio.get_running_loop()
    fdb_future = lib.fdb_transaction_get_addresses_for_key(tx.pointer, key, len(key))
    aio_future = loop.create_future()
    _register_callback(fdb_future, _cb_get_string_array, loop, aio_future)
    return await aio_future


async def transactional(db, func, *args, snapshot=False, **kwargs):
    loop = asyncio.get_running_loop()
    tx = _make_transaction(db, snapshot)
    while True:
        try:
            out = await func(tx, *args, **kwargs)
            await _commit(tx)
        except FoundException as exc:
            fdb_future = lib.fdb_transaction_on_error(tx.pointer, exc.code)
            aio_future = loop.create_future()
            _register_callback(fdb_future, _cb_error, loop, aio_future)
            await aio_future  # raises if the error is not retryable
        else:
            return out


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

Database = namedtuple("Database", ("pointer",))


async def open(cluster_file=None):
    _ensure_network()
    out = ffi.new("FDBDatabase **")
    cluster_file_c = (
        cluster_file.encode() if isinstance(cluster_file, str)
        else cluster_file if cluster_file is not None
        else ffi.NULL
    )
    _check(lib.fdb_create_database(cluster_file_c, out))
    out = ffi.gc(out[0], lib.fdb_database_destroy)
    return Database(out)


# ---------------------------------------------------------------------------
# Database options
# ---------------------------------------------------------------------------

def database_set_option(db, option, value=None):
    """Wraps fdb_database_set_option (synchronous)."""
    if value is None:
        _check(lib.fdb_database_set_option(db.pointer, option, ffi.NULL, 0))
    else:
        _check(lib.fdb_database_set_option(db.pointer, option, value, len(value)))


# ---------------------------------------------------------------------------
# Network options and hooks
# ---------------------------------------------------------------------------

def network_set_option(option, value=None):
    """Wraps fdb_network_set_option (synchronous). Must be called before network start."""
    if value is None:
        _check(lib.fdb_network_set_option(option, ffi.NULL, 0))
    else:
        _check(lib.fdb_network_set_option(option, value, len(value)))


_completion_hooks = []


@ffi.callback("void(void *)")
def _completion_hook_trampoline(param):
    idx = ffi.cast("intptr_t", param)
    _completion_hooks[idx]()


def add_network_thread_completion_hook(callback):
    """Register a callback to be invoked when the network thread exits."""
    idx = len(_completion_hooks)
    _completion_hooks.append(callback)
    _check(lib.fdb_add_network_thread_completion_hook(
        _completion_hook_trampoline, ffi.cast("void *", idx)
    ))


# ---------------------------------------------------------------------------
# Client version and error predicates
# ---------------------------------------------------------------------------

def get_client_version():
    """Return the FDB client library version string."""
    return ffi.string(lib.fdb_get_client_version()).decode("utf-8")


ERROR_PREDICATE_RETRYABLE = 50000
ERROR_PREDICATE_MAYBE_COMMITTED = 50001
ERROR_PREDICATE_RETRYABLE_NOT_COMMITTED = 50002


def error_predicate(predicate, code):
    """Test whether an error code matches a predicate (retryable, maybe-committed, etc.)."""
    return bool(lib.fdb_error_predicate(predicate, code))
