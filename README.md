# [asyncio-foundationdb](https://github.com/amirouche/asyncio-foundationdb/)

*early draft*

asyncio drivers for foundationdb tested with CPython 3.9 and PyPy 3.7

[![Library Database](https://images.unsplash.com/photo-1544383835-bda2bc66a55d?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1021&q=80)](https://unsplash.com/photos/lRoX0shwjUQ)

## Table of Content

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
- [Getting started](#getting-started)
- [ChangeLog](#changelog)
    - [v0.10.x](#v010x)
- [`import found`](#import-found)
<!-- markdown-toc end -->

## Getting started

```
pip install asyncio-foundationdb
```

```python
import found


async def get(tx, key):
    out = await found.get(tx, key)

async def set(tx, key, value):
    found.set(tx, key, value)


db = await found.open()
out = await found.transactional(db, get, b'hello')
assert out is None

await found.transactional(db, set, b'hello', b'world')
out = await found.transactional(db, get, b'hello')
assert out == b'world'
```

## ChangeLog

### v0.10.x

- Almost full rewrite
- Remove hooks for the time being
- Port nstore extensions
- Add BLOB store ie. bstore
- Add EAV store ie. eavstore

## `import found`

### `found.BaseFoundException`

All `found` exceptions inherit that class.

### `found.FoundException`

Exception raised when there is a problem foundationdb client drivers
side or foundationdb server side.

### `async found.open(cluster_file=None)`

Coroutine that will open a connection with the cluster specified in
the file `cluster_file`. If `cluster_file` is not provided the default
is `/etc/foundationdb/fdb.cluster`. Returns a database object.

### `async found.transactional(db, func, *args, snapshot=False, **kwargs)`

Coroutine that will manage a transaction against `db` for `func`
that. If `snapshot=True` then the transaction is read-only. `func`
will receive an appropriate transaction object as first argument, then
`args`, then `kwargs`. Because of errors `transactional` might run
`func` several times, hence `func` should be idempotent.

### `async found.get(tx, key)`

Coroutine that will fetch the value associated with `key` inside the
database associated with `tx`. `key` must be `bytes`. In case of
success, returns `bytes`. Otherwise, if there is no value associated
with `key`, returns the object `None`.

### `found.set(tx, key, value)`

In the database associated with `tx`, associate `key` with
`value`. Both `key` and `value` must be `bytes`.

### `found.clear(tx, key, other=None)`

In the database associated with `tx`, clear the specified `key` or
range of keys.

`key` and `other` if provided must be `bytes`.

If `other=None`, then clear the association that might exists with
`key`. Otherwise, if `other` is provided, `found.clear` will remove
any association between `key` and `other` but not the association with
`other` if any (that is `other` is excluded from the range).

### `async found.query(tx, key, other, *, limit=0, mode=STREAMING_MODE_ITERATOR)`

In the database associated with `tx`, generate at most `limit`
key-value pairs inside the specified range, with the specified order.

If `key < other` then `found.query` generates key-value pairs in
lexicographic order. Otherwise, if `key > other` then `found.query`
generates key-value pairs in reverse lexicographic order, that is
starting at `other` until `key`.

If `limit=0`, then `found.query` generates all key-value pairs in the
specified bounds. Otherwise if `limit > 0` then, it generates at most
`limit` pairs.

The keyword `mode` can be one the following constant:

- `found.STREAMING_MODE_WANT_ALL`
- `found.STREAMING_MODE_ITERATOR`
- `found.STREAMING_MODE_EXACT`
- `found.STREAMING_MODE_SMALL`
- `found.STREAMING_MODE_MEDIUM`
- `found.STREAMING_MODE_LARGE`
- `found.STREAMING_MODE_SERIAL`

### `found.next_prefix(key)`

Returns the immediatly next bytes sequence that is not prefix of `key`.

### `found.lt(key, offset=0)`

### `found.lte(key, offset=0)`

### `found.gt(key, offset=0)`

### `found.gte(key, offset=0)`

### `async found.read_version(tx)`

### `found.set_read_version(tx, version)`

### `found.add(tx, key, param)`

### `found.bit_and(tx, key, param)`

### `found.bit_or(tx, key, param)`

### `found.bit_xor(tx, key, param)`

### `found.max(tx, key, param)`

### `found.byte_max(tx, key, param)`

### `found.min(tx, key, param)`

### `found.byte_min(tx, key, param)`

### `found.set_versionstamped_key(tx, key, param)`

### `found.set_versionstamped_value(tx, key, param)`
