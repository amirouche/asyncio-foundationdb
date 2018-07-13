#
# This source file was part of the FoundationDB open source project
# it was forked to implement the Python asyncio bindings in found project.
# see https://github.com/amirouche/found
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018 Amirouche Boubekki <amirouche@hypermove.net>
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
import logging
import six
import struct
import threading
from enum import Enum
from functools import wraps

from async_generator import async_generator
from async_generator import yield_

import found
from found._fdb_c import lib
from found._fdb_c import ffi


log = logging.getLogger(__name__)


CLIENT_VERSION = 510


class BaseFound:
    """Base class for all found classes"""
    pass


class FoundException(Exception):
    """Base class for all found exceptions"""
    pass


class FoundError(FoundException):
    """Exception raised when FoundationDB API call returns an error"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code

    def __str__(self):
        description = ffi.string(lib.fdb_get_error(self.code)).decode('utf-8')
        return '<FoundError {} ({})>'.format(description, self.code)

    __repr__ = __str__


def strinc(key):
    # XXX: I am not sure what this function is doing.
    key = key.rstrip(b'\xff')
    if len(key) == 0:
        raise ValueError('Key must contain at least one byte not equal to 0xFF.')
    return key[:-1] + six.int2byte(ord(key[-1:]) + 1)


def check(code):
    if code != 0:
        raise FoundError(code)


def ensure_version():
    if found.CURRENT_LOADED_VERSION is None:
        # Configure the client API for the current CLIENT_VERSION
        code = lib.fdb_select_api_version_impl(CLIENT_VERSION, CLIENT_VERSION)
        if code == 2203:  # api_version_not_supported, but that's not helpful to the user
            max_supported_ver = lib.fdb_get_max_api_version()
            if CLIENT_VERSION > max_supported_ver:
                msg = "This version of the FoundationDB Python binding is not supported by "
                msg += "the installed FoundationDB C library. The binding requires a library "
                msg += "that supports API version %d, but the installed library supports a "
                msg += "maximum version of %d."
                msg = msg % (CLIENT_VERSION, max_supported_ver)
                raise RuntimeError(msg)
            else:
                msg = "API version %d is not supported by the installed FoundationDB C library."
                msg = msg % CLIENT_VERSION
                raise RuntimeError(msg)
        elif code != 0:
            raise RuntimeError('FoundationDB API error ({})'.format(code))

        found.CURRENT_LOADED_VERSION = CLIENT_VERSION
    elif found.CURRENT_LOADED_VERSION != CLIENT_VERSION:
        msg = "found already loaded with for a different version "
        raise RuntimeError(msg)
    log.info('found configured to use client API %s', CLIENT_VERSION)
    return True


_network_thread = None
_network_thread_reentrant_lock = threading.RLock()
_loop = None


class NetworkThread(threading.Thread):

    def run(self):
        check(lib.fdb_run_network())


def init():
    "Must be called after setting the event loop"""
    try:
        with _network_thread_reentrant_lock:
            global _loop
            global _network_thread
            # init should only succeed once; If _network_thread is not None,
            # someone already successfully called init
            if _network_thread is not None:
                # This raise FoundError, even if there is no call to FDB API
                raise FoundError(2000)

            _network_thread = NetworkThread()
            _network_thread.daemon = True
            lib.fdb_setup_network()
            _network_thread.start()

            # XXX: the following means, we can not use Found with several event loopsx
            _loop = asyncio.get_event_loop()
    except Exception:  # noqa
        # We assigned _network_thread but did not succeed in init,
        # clear it out so the next caller has chance
        _network_thread = None
        raise


@atexit.register
def _stop_network():
    if _network_thread:
        check(lib.fdb_stop_network())
        _network_thread.join()


class KeySelector:

    def __init__(self, key, or_equal, offset):
        self.key = get_key(key)
        self.or_equal = or_equal
        self.offset = offset

    def __add__(self, offset):
        return KeySelector(self.key, self.or_equal, self.offset + offset)

    def __sub__(self, offset):
        return KeySelector(self.key, self.or_equal, self.offset - offset)

    @classmethod
    def last_less_than(cls, key):
        return cls(key, False, 0)

    @classmethod
    def last_less_or_equal(cls, key):
        return cls(key, True, 0)

    @classmethod
    def first_greater_than(cls, key):
        return cls(key, True, 1)

    @classmethod
    def first_greater_or_equal(cls, key):
        return cls(key, False, 1)


class StreamingMode(Enum):
    WANT_ALL = -2
    ITERATOR = -1
    EXACT = 0
    SMALL = 1
    MEDIUM = 2
    LARGE = 3
    SERIAL = 4


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_get_read_version(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    pointer = ffi.new('int64 *')
    error = lib.fdb_future_get_version(fdb_future, pointer)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, pointer[0])
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
    lib.fdb_future_destroy(fdb_future)


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_get(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    present = ffi.new('fdb_bool_t *')
    value = ffi.new('uint8_t **')
    value_length = ffi.new('int *')
    error = lib.fdb_future_get_value(fdb_future, present, value, value_length)
    if error == 0:
        if present == 0:
            _loop.call_soon_threadsafe(aio_future.set_result, None)
            lib.fdb_future_destroy(fdb_future)
        else:
            # TODO: maybe wrap in a factory to keep the closure lightweight
            def free(_):
                # XXX: the destruction of the future is delayed until
                # there is no more references to the value. Hope it works!
                lib.fdb_future_destroy(fdb_future)

            handle = ffi.gc(value[0], free)
            out = ffi.buffer(handle, value_length[0])
            _loop.call_soon_threadsafe(aio_future.set_result, out)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
        lib.fdb_future_destroy(fdb_future)


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_commit(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    error = lib.fdb_future_get_error(fdb_future)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, None)
        lib.fdb_future_destroy(fdb_future)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
        lib.fdb_future_destroy(fdb_future)


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_get_key(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    key = ffi.new('int8_t **')
    key_length = ffi.new('int *')
    error = lib.fdb_future_get_key(fdb_future, key, key_length)
    if error == 0:
        # TODO: what happens when there is no such key
        buffer = ffi.buffer(key[0], key_length[0])

        # TODO: do something like on_transaction_get_range_free
        def free(_):
            # XXX: the destruction of the future is delayed until
            # there is no more references to the value. Hope it works!
            lib.fdb_future_destroy(fdb_future)

        out = ffi.gc(buffer, free)
        _loop.call_soon_threadsafe(aio_future.set_result, out)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
        lib.fdb_future_destroy(fdb_future)


def on_transaction_get_range_free(fdb_future, total):
    # XXX: factory function that should allow to keep around a
    # lightweight closure around free function instead of the whole
    # on_transaction_get_range bazaar. Hope it works!

    def free(_):
        nonlocal total
        total -= 1
        if total == 0:
            lib.fdb_future_destroy(fdb_future)

    return free


@ffi.callback("void(FDBFuture *, void *)")
def on_transaction_get_range(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    kvs = ffi.new('FDBKeyValue **')
    count = ffi.new('int *')
    more = ffi.new('fdb_bool_t *')
    error = lib.fdb_future_get_keyvalue_array(fdb_future, kvs, count, more)
    if error == 0:
        out = list()
        # XXX: Because ffi.gc doens't work this time and because
        # downstream the code expect a real bytes object; for the time
        # being we do a copy

        # total count of buffers for this key-value array
        # total = count[0] * 2
        # free = on_transaction_get_range_free(fdb_future, total)

        for kv in kvs[0][0:count[0]]:
            # XXX: manual unpacking because cffi doesn't known about packing
            # https://bitbucket.org/cffi/cffi/issues/364/make-packing-configureable
            memory = ffi.buffer(ffi.addressof(kv), 24)
            key_ptr, key_length, value_ptr, value_length = struct.unpack('=qiqi', memory)
            key = ffi.buffer(ffi.cast('char *', key_ptr), key_length)
            value = ffi.buffer(ffi.cast('char *', value_ptr), value_length)
            # key = ffi.gc(key, free)
            # value = ffi.gc(value, free)
            # XXX: make a copy
            out.append((key[:], value[:]))

        _loop.call_soon_threadsafe(aio_future.set_result, (out, count[0], more[0]))
        # since we make copies of the fdb_future result we don't need
        # to keep it around
        lib.fdb_future_destroy(fdb_future)
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
        lib.fdb_future_destroy(fdb_future)


def get_key(obj):
    # XXX: not sure this as_foundationdb_key is really needed/useful
    try:
        key = obj.as_foundationdb_key()
    except AttributeError:
        key = obj
    assert isinstance(key, bytes)
    return key


def get_value(obj):
    # Same as above
    try:
        value = obj.as_foundationdb_value()
    except AttributeError:
        value = obj
    assert isinstance(obj, bytes)
    return value


class BaseTransaction(BaseFound):

    def __init__(self, pointer, database, snapshot):
        self._pointer = pointer
        self._database = database
        self._snapshot = snapshot

    def __del__(self):
        lib.fdb_transaction_destroy(self._pointer)

    @property
    def options():
        raise NotImplemented()  # TODO

    async def read_version(self):
        """Get the read version of the transaction"""
        fdb_future = lib.fdb_transaction_get_read_version(self._pointer)
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)
        lib.fdb_future_set_callback(
            fdb_future,
            on_transaction_get_read_version,
            handle
        )
        out = await aio_future
        return out

    async def get(self, key):
        key = get_key(key)
        fdb_future = lib.fdb_transaction_get(self._pointer, key, len(key), self._snapshot)
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)
        lib.fdb_future_set_callback(
            fdb_future,
            on_transaction_get,
            handle
        )
        out = await aio_future
        return out

    async def get_key(self, key_selector):
        key = get_key(key_selector.key)
        fdb_future = lib.fdb_transaction_get_key(
            self._pointer,
            key,
            len(key),
            key_selector.or_equal,
            key_selector.offset,
            self._snapshot
        )
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)
        lib.fdb_future_set_callback(
            fdb_future,
            on_transaction_get_key,
            handle
        )
        out = await aio_future
        return out

    def get_range(
            self,
            begin,
            end,
            limit=0,
            reverse=False,
            mode=StreamingMode.ITERATOR):

        @async_generator
        async def iter_():
            nonlocal begin
            nonlocal end

            def default(key):
                return KeySelector.first_greater_or_equal(key)

            # begin and end can be None, anyway convert to a KeySelector
            begin = default(b'') if begin is None else begin if isinstance(begin, KeySelector) else default(begin)  # noqa
            end = default(b'\xff') if end is None else end if isinstance(end, KeySelector) else default(end)  # noqa
            iteration = 1  # Why one?!
            seen = 0
            snapshot = self._snapshot
            while True:
                fdb_future = lib.fdb_transaction_get_range(
                    self._pointer,
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
                    mode.value,
                    iteration,  # what's is its purpose?
                    snapshot,
                    reverse,
                )
                aio_future = _loop.create_future()
                handle = ffi.new_handle(aio_future)
                lib.fdb_future_set_callback(fdb_future, on_transaction_get_range, handle)
                kvs, count, more = await aio_future

                if count == 0:
                    return

                for kv in kvs:
                    await yield_(kv)

                    # it seems like fdb client can return more than what is
                    # requested, so we count ourselves
                    seen += 1
                    if limit > 0 and seen == limit:
                        return
                # re-compute the range
                if reverse:
                    end = KeySelector.first_greater_or_equal(kvs[-1][0])
                else:
                    begin = KeySelector.first_greater_than(kvs[-1][0])
                # loop!

        return iter_()

    async def get_range_startswith(
            self,
            prefix,
            limit=0,
            reverse=False,
            mode=StreamingMode.ITERATOR):
        prefix = get_key(prefix)
        return self.get_range(prefix, strinc(prefix), limit, reverse, mode)


class Transaction(BaseTransaction):

    def __init__(self, pointer, database):
        super().__init__(pointer, database, False)
        self.snapshot = BaseTransaction(pointer, database, True)

    def __del__(self):
        # because self.pointer is shared with self.snapshot, we
        # override this to avoid a double free
        pass

    def set_read_version(self, version):
        lib.fdb_transaction_set_read_version(self._pointer, version)

    def set(self, key, value):
        key = get_key(key)
        value = get_value(value)
        lib.fdb_transaction_set(self._pointer, key, len(key), value, len(value))

    async def commit(self):
        fdb_future = lib.fdb_transaction_commit(self._pointer)
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)
        lib.fdb_future_set_callback(
            fdb_future,
            on_transaction_commit,
            handle
        )
        await aio_future

    async def _on_error(self, code):
        fdb_future = lib.fdb_transaction_on_error(self._pointer, code)
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)

        @ffi.callback("void(FDBFuture *, void *)")
        def callback(fdb_future, aio_future):
            aio_future = ffi.from_handle(aio_future)
            error = lib.fdb_future_get_error(fdb_future)
            if error == 0:
                _loop.call_soon_threadsafe(aio_future.set_result)
            else:
                _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
            lib.fdb_future_destroy(fdb_future)

        lib.fdb_future_set_callback(fdb_future, callback, handle)
        await aio_future  # may raise an exception


class Database(BaseFound):

    def __init__(self, pointer):
        self._pointer = pointer

    def __del__(self):
        lib.fdb_database_destroy(self._pointer)

    @property
    def options():
        raise NotImplemented()  # TODO

    def _create_transaction(self):
        pointer = ffi.new('FDBTransaction **')
        lib.fdb_database_create_transaction(self._pointer, pointer)
        return Transaction(pointer[0], self)


@ffi.callback("void(FDBFuture *, void *)")
def on_create_database(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    pointer = ffi.new('FDBDatabase **')
    error = lib.fdb_future_get_database(fdb_future, pointer)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, pointer[0])
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
    lib.fdb_future_destroy(fdb_future)


class Cluster(BaseFound):

    def __init__(self, pointer):
        self._pointer = pointer

    @property
    def options():
        raise NotImplemented()  # TODO

    def __del__(self):
        lib.fdb_cluster_destroy(self._pointer)

    async def open(self, name):
        name = name.encode('utf-8')
        fdb_future = lib.fdb_cluster_create_database(self._pointer, name, len(name))
        aio_future = _loop.create_future()
        handle = ffi.new_handle(aio_future)
        lib.fdb_future_set_callback(fdb_future, on_create_database, handle)
        pointer = await aio_future
        return Database(pointer)


@ffi.callback("void(FDBFuture *, void *)")
def on_create_cluster(fdb_future, aio_future):
    aio_future = ffi.from_handle(aio_future)
    pointer = ffi.new('FDBCluster **')
    error = lib.fdb_future_get_cluster(fdb_future, pointer)
    if error == 0:
        _loop.call_soon_threadsafe(aio_future.set_result, pointer[0])
    else:
        _loop.call_soon_threadsafe(aio_future.set_exception, FoundError(error))
    lib.fdb_future_destroy(fdb_future)


async def create_cluster(cluster_file=None):
    fdb_future = lib.fdb_create_cluster(cluster_file or ffi.NULL)
    aio_future = _loop.create_future()
    handle = ffi.new_handle(aio_future)
    lib.fdb_future_set_callback(fdb_future, on_create_cluster, handle)
    pointer = await aio_future
    return Cluster(pointer)


_clusters = dict()
_databases = dict()

cache_lock = threading.Lock()


async def open(cluster_file=None):
    """Open the database specified by `cluster_file` or the default
    cluster indicated by the fdb.cluster file in a platform-specific
    location. Initializes the FoundationDB interface as required"""

    ensure_version()

    with _network_thread_reentrant_lock:
        if _network_thread is None:
            init()

    with cache_lock:
        try:
            cluster = _clusters[cluster_file]
        except KeyError:
            cluster = _clusters[cluster_file] = await create_cluster(cluster_file)

        # in the 510 bindings, it is apparently possible to open different
        # databases in the same cluster but that is not supported by
        # the underlying client API. YAGNI for the time being. We hardcode
        # the database name and do not expose it in the public API
        database_name = 'DB'
        try:
            db = _databases[(cluster_file, database_name)]
        except KeyError:
            db = _databases[(cluster_file, database_name)] = await cluster.open(database_name)

        return db


def transactional(func):

    @wraps(func)
    async def wrapper(db_or_tx, *args, **kwargs):
        if isinstance(db_or_tx, Transaction):
            out = await func(db_or_tx, *args, **kwargs)
            return out
        else:
            tx = db_or_tx._create_transaction()
            while True:
                try:
                    out = await func(tx, *args, **kwargs)
                    await tx.commit()
                except FoundError as exc:
                    await tx._on_error(exc.code)
                else:
                    return out

    return wrapper
