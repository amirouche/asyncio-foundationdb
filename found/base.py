#
# This source file was part of the FoundationDB open source project
# it was forked to implement the Python asyncio bindings in found project.
# see https://github.com/amirouche/asyncio-foundationdb
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018-2021 Amirouche Boubekki <amirouche@hyper.dev>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import asyncio
import atexit
import struct
import threading
from collections import namedtuple

from found._fdb import lib
from found._fdb import ffi


class BaseFoundException(Exception):
    pass


class FoundException(BaseFoundException):
    """Exception raised when FoundationDB returns an error"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code

    def __repr__(self):
        description = ffi.string(lib.fdb_get_error(self.code)).decode("utf-8")
        return "<FoundException {} ({})>".format(description, self.code)


def next_prefix(key):
    """Compute the smallest bytes sequence that does not start with key"""
    key = key.rstrip(b"\xff")
    if len(key) == 0:
        raise ValueError("Key must contain at least one byte not equal to 0xFF.")
    return key[:-1] + bytes((key[-1] + 1,))


def _check(code):
    if code != 0:
        raise FoundException(code)


_network_thread = None
_network_thread_reentrant_lock = threading.RLock()
_loop = None


class NetworkThread(threading.Thread):
    def run(self):
        _check(lib.fdb_run_network())


def _init():
    """Must be called after setting the event loop"""
    try:
        global _loop
        global _network_thread
        # init should only succeed once; If _network_thread is not None,
        # someone already successfully called init
        if _network_thread is not None:
            # This raise FoundException, even if there is no call to FDB API
            raise FoundException(2000)

        _network_thread = NetworkThread()
        _network_thread.daemon = True
        lib.fdb_setup_network()
        _network_thread.start()
        _loop = asyncio.get_event_loop()
    except Exception:  # noqa
        # We assigned _network_thread but did not succeed in init,
        # clear it out so the next caller has chance
        _network_thread = None
        raise


@atexit.register
def _stop_network():
    if _network_thread:
        _check(lib.fdb_stop_network())
        _network_thread.join()


STREAMING_MODE_WANT_ALL = -2
STREAMING_MODE_ITERATOR = -1
STREAMING_MODE_EXACT = 0
STREAMING_MODE_SMALL = 1
STREAMING_MODE_MEDIUM = 2
STREAMING_MODE_LARGE = 3
STREAMING_MODE_SERIAL = 4


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_commit(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    error = lib.fdb_future_get_error(fdb_future)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, None)
        lib.fdb_future_destroy(fdb_future)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))
        lib.fdb_future_destroy(fdb_future)


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_get_range(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    kvs = ffi.new("FDBKeyValue **")
    count = ffi.new("int *")
    more = ffi.new("fdb_bool_t *")
    error = lib.fdb_future_get_keyvalue_array(fdb_future, kvs, count, more)
    if error == 0:
        out = list()
        # XXX: Because ffi.gc doens't work this time and because
        # downstream the code expect a real bytes object; for the time
        # being we do a copy of the whole range iteration

        # total count of buffers for this key-value array
        copy = kvs[0][0:count[0]]

        for kv in copy:
            # XXX: manual unpacking because cffi doesn't known about packing
            # https://bitbucket.org/cffi/cffi/issues/364/make-packing-configureable
            memory = ffi.buffer(ffi.addressof(kv), 24)
            key_ptr, key_length, value_ptr, value_length = struct.unpack(
                "=qiqi", memory
            )
            key = ffi.buffer(ffi.cast("char *", key_ptr), key_length)
            value = ffi.buffer(ffi.cast("char *", value_ptr), value_length)
            # XXX: make a copy again
            out.append((key[:], value[:]))

        _loop.call_soon_threadsafe(aio_future.set_result, (out, count[0], more[0]))
        # since we make copies of the fdb_future result we don't need
        # to keep it around
        lib.fdb_future_destroy(fdb_future)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))
        lib.fdb_future_destroy(fdb_future)


Transaction = namedtuple('Transaction', ('pointer', 'db', 'snapshot'))


def _make_transaction(db, snapshot=False):
    # TODO: maybe free this double pointer?
    out = ffi.new("FDBTransaction **")
    lib.fdb_database_create_transaction(db.pointer, out)
    out = ffi.gc(out[0], lib.fdb_transaction_destroy)
    out = Transaction(out, db, snapshot)
    return out


@ffi.callback("void(FDBFuture *, void *)")
def _on_transaction_get_read_version(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    pointer = ffi.new("int64_t *")
    error = lib.fdb_future_get_int64(fdb_future, pointer)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, pointer[0])
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))
    lib.fdb_future_destroy(fdb_future)


async def read_version(tx):
    fdb_future = lib.fdb_transaction_get_read_version(tx.pointer)
    aio_future = _loop.create_future()
    handle = ffi.new_handle(aio_future)
    lib.fdb_future_set_callback(fdb_future, _on_transaction_get_read_version, handle)
    out = await aio_future
    return out


@ffi.callback("void(FDBFuture *, void *)")
def _on_transaction_get(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    present = ffi.new("fdb_bool_t *")
    value = ffi.new("uint8_t **")
    value_length = ffi.new("int *")
    error = lib.fdb_future_get_value(fdb_future, present, value, value_length)
    if error == 0:
        if present[0] == 0:
            _loop.call_soon_threadsafe(aio_future.set_result, None)
            lib.fdb_future_destroy(fdb_future)
        else:
            # XXX: https://bitbucket.org/cffi/cffi/issues/380/ffibuffer-position-returns-a-buffer
            out = bytes(ffi.buffer(value[0], value_length[0]))
            _loop.call_soon_threadsafe(aio_future.set_result, out)
            lib.fdb_future_destroy(fdb_future)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))
        lib.fdb_future_destroy(fdb_future)


async def get(tx, key):
    assert isinstance(tx, Transaction)
    assert isinstance(key, bytes)
    fdb_future = lib.fdb_transaction_get(
        tx.pointer, key, len(key), tx.snapshot
    )
    aio_future = _loop.create_future()
    handle = ffi.new_handle(aio_future)
    lib.fdb_future_set_callback(fdb_future, _on_transaction_get, handle)
    out = await aio_future
    return out


KeySelector = namedtuple('KeySelector', ('key', 'or_equal', 'offset'))


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
    return KeySelector(key, False, 1)


async def query(tx, key, other, *, limit=0, mode=STREAMING_MODE_ITERATOR):
    key = key if isinstance(key, KeySelector) else gte(key)
    other = other if isinstance(other, KeySelector) else gte(other)
    if key.key < other.key:
        begin = key
        end = other
        reverse = False
    else:
        begin = other
        end = key
        reverse = True

    # the first read was fired off when the FDBRange was initialized
    iteration = 1
    snapshot = tx.snapshot
    while True:
        fdb_future = lib.fdb_transaction_get_range(
            tx.pointer,
            begin.key,
            len(begin.key),
            begin.or_equal,
            begin.offset,
            end.key,
            len(end.key),
            end.or_equal,
            end.offset,
            limit,
            0,
            mode,
            iteration,
            snapshot,
            reverse,
        )
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)
        lib.fdb_future_set_callback(fdb_future, on_transaction_get_range, handle)
        kvs, count, more = await aio_future

        index = 0
        if count == 0:
            return

        for kv in kvs:
            yield kv

            index += 1
            if index == count:
                if not more or limit == count:
                    return

                iteration += 1
                if limit > 0:
                    limit -= count
                if reverse:
                    end = gte(kv[0])
                else:
                    begin = gt(kv[0])
        # loop!


@ffi.callback("void(FDBFuture *, void *)")
def _estimated_size_bytes_callback(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    pointer = ffi.new("int64_t *")
    error = lib.fdb_future_get_int64(fdb_future, pointer)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, pointer[0])
        lib.fdb_future_destroy(fdb_future)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))
        lib.fdb_future_destroy(fdb_future)


async def estimated_size_bytes(tx, begin, end):
    fdb_future = lib.fdb_transaction_get_estimated_range_size_bytes(
        tx.pointer,
        begin,
        len(begin),
        end,
        len(end)
    )
    aio_future = _loop.create_future()
    handle = ffi.new_handle(aio_future)
    lib.fdb_future_set_callback(fdb_future, _estimated_size_bytes_callback, handle)
    size = await aio_future
    return size


def set_read_version(tx, version):
    assert not tx.snapshot
    lib.fdb_transaction_set_read_version(tx.pointer, version)


def set(tx, key, value):
    assert isinstance(tx, Transaction)
    assert isinstance(key, bytes)
    assert isinstance(value, bytes)
    assert not tx.snapshot

    lib.fdb_transaction_set(tx.pointer, key, len(key), value, len(value))


def clear(tx, key, other=None):
    assert isinstance(tx, Transaction)
    assert isinstance(key, bytes)
    if other is None:
        lib.fdb_transaction_clear(tx.pointer, key, len(key))
    else:
        assert isinstance(other, bytes)
        lib.fdb_transaction_clear_range(tx.pointer, key, len(key), other, len(other))


async def _commit(tx):
    fdb_future = lib.fdb_transaction_commit(tx.pointer)
    aio_future = _loop.create_future()
    handle = ffi.new_handle(aio_future)
    lib.fdb_future_set_callback(fdb_future, on_transaction_commit, handle)
    await aio_future


MUTATION_ADD = 2
MUTATION_BIT_AND = 6
MUTATION_BIT_OR = 7
MUTATION_BIT_XOR = 8
MUTATION_MAX = 12
MUTATION_MIN = 13
MUTATION_SET_VERSIONSTAMPED_KEY = 14
MUTATION_SET_VERSIONSTAMPED_VALUE = 15
MUTATION_BYTE_MIN = 16
MUTATION_BYTE_MAX = 17


def _atomic(tx, opcode, key, param):
    lib.fdb_transaction_atomic_op(tx.pointer, key, len(key), param, len(param), opcode)


def add(tx, key, param):
    _atomic(tx, MUTATION_ADD, key, param)


def bit_and(tx, key, param):
    _atomic(tx, MUTATION_BIT_AND, key, param)


def bit_or(tx, key, param):
    _atomic(tx, MUTATION_BIT_OR, key, param)


def bit_xor(tx, key, param):
    _atomic(tx, MUTATION_BIT_XOR, key, param)


def max(tx, key, param):
    _atomic(tx, MUTATION_MAX, key, param)


def byte_max(tx, key, param):
    _atomic(tx, MUTATION_BYTE_MAX, key, param)


def min(tx, key, param):
    _atomic(tx, MUTATION_MIN, key, param)


def byte_min(tx, key, param):
    _atomic(tx, MUTATION_BYTE_MIN, key, param)


def set_versionstamped_key(tx, key, param):
    _atomic(tx, MUTATION_SET_VERSIONSTAMPED_KEY, key, param)


def set_versionstamped_value(tx, key, param):
    _atomic(tx, MUTATION_SET_VERSIONSTAMPED_VALUE, key, param)


@ffi.callback("void(FDBFuture *, void *)")
def _on_error_callback(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    error = lib.fdb_future_get_error(fdb_future)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, None)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundException(error))
    lib.fdb_future_destroy(fdb_future)


async def transactional(db, func, *args, snapshot=False, **kwargs):
    tx = _make_transaction(db, snapshot)
    while True:
        try:
            out = await func(tx, *args, **kwargs)
            await _commit(tx)
        except FoundException as exc:
            fdb_future = lib.fdb_transaction_on_error(tx.pointer, exc.code)
            aio_future = _loop.create_future()
            handle = ffi.new_handle(aio_future)
            lib.fdb_future_set_callback(fdb_future, _on_error_callback, handle)
            await aio_future  # may raise an exception
        else:
            return out


Database = namedtuple('Database', ('pointer',))


async def open(cluster_file=None):

    with _network_thread_reentrant_lock:
        if _network_thread is None:
            _init()

    out = ffi.new("FDBDatabase **")
    cluster_file = cluster_file if cluster_file is not None else ffi.NULL
    lib.fdb_create_database(cluster_file, out)
    out = ffi.gc(out[0], lib.fdb_database_destroy)
    out = Database(out)

    return out
