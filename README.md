# [asyncio-foundationdb](https://github.com/amirouche/asyncio-foundationdb/)

asyncio drivers for FoundationDB, tested with CPython 3.9, 3.10, 3.11, and PyPy 3.8, 3.9.

<!-- [![builds.sr.ht status](https://builds.sr.ht/~amirouche/asyncio-foundationdb/commits/main/.build.yml.svg)](https://builds.sr.ht/~amirouche/asyncio-foundationdb/commits/main/.build.yml?) -->

[![Library Database](https://images.unsplash.com/photo-1544383835-bda2bc66a55d?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1021&q=80)](https://unsplash.com/photos/lRoX0shwjUQ)

## Marketing

In the fast-paced digital landscape, FoundationDB is the unsung hero
of data management. That Key-Value Store serve as the backbone of
countless applications, providing lightning-fast access to essential
information. With its simple yet powerful structure, FoundationDB
effortlessly organizes and retrieve data, making it the go-to choice
for developers seeking speed and efficiency. Whether you're building a
dynamic web application, a datalake knowledge base, a robust caching
system, or a real-time analytics platform, FoundationDB is your trusty
ally, ensuring seamless data access and enabling innovation at the
speed of thought. Discover the key to data-driven success with
FoundationDB – where simplicity meets scalability, and speed meets
reliability

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
- [Getting started](#getting-started)
- [ChangeLog](#changelog)
    - [v0.12.x](#v012x)
- [`import found`](#import-found)
- [`from found import bstore`](#from-found-import-bstore)
- [`from found import nstore`](#from-found-import-nstore)
- [`from found import eavstore`](#from-found-import-eavstore)
- [`from found import pstore`](#from-found-import-pstore)
- [`from found import vnstore`](#from-found-import-vnstore)
<!-- markdown-toc end -->

Enter the world of data organization and retrieval with FoundationDB,
the Ordered Key-Value Store. FoundationDB is your solution for
maintaining structured data in a way that preserves both order and
simplicity. With the power to efficiently sort and access data,
FoundationDB is a versatile tool for a wide range of
applications. From managing time-series data in financial systems, or
hierarchies, to optimizing search functionality in e-commerce
platforms, FoundationDB offers an elegant and reliable solution. Take
control of your data, embrace order, and unlock a new level of
efficiency with FoundationDB - where data is not just stored, but
intelligently organized for streamlined success.

FoundationDB, the bedrock of modern data infrastructure, is the
groundbreaking distributed database system that unlocks new frontiers
in reliability, scalability, and performance. With a unique
combination of ACID transactions, distributed architecture, and a
highly versatile data model, FoundationDB seamlessly handles complex
workloads while ensuring data integrity. It's the go-to choice for
organizations seeking a solid foundation for mission-critical
applications, from e-commerce platforms to cutting-edge IoT
ecosystems. Harness the power of FoundationDB and experience a world
where your data is always available, always consistent, and always
ready to fuel your boldest innovations.

Build on a solid foundation with FoundationDB.

## Installation

In a minute, install foundationdb, getting the latest stable release
from the official release page: https://github.com/apple/foundationdb/releases

Then install asyncio drivers `asyncio-foundationdb`:

```
pip install asyncio-foundationdb
```

## Example

```python
async def readme():

    async def get(tx, key):
        out = await found.get(tx, key)
        return out

    async def set(tx, key, value):
        return found.set(tx, key, value)

    db = await found.open()
    out = await found.transactional(db, get, b'hello')
    assert out is None

    await found.transactional(db, set, b'hello', b'world')
    out = await found.transactional(db, get, b'hello')
    assert out == b'world'

    await found.transactional(db, set, b'azul', b'world')
    out = await found.transactional(db, get, b'azul')
    assert out == b'world'

    async def query(tx, key, other):
        out = await found.all(found.query(tx, key, other))
        return out

    out = await found.transactional(db, query, b'', b'\xFF')
    assert [(b'azul', b'world'), (b'hello', b'world')]

asyncio.run(readme())
```

## ChangeLog

### v0.12.0

- Move back to GitHub;
- Add versioned generic tuple store (code name `vnstore`)

### v0.10.x

- Almost full rewrite
- Remove hooks for the time being
- Port Generic Tuple Store aka. `nstore`
- Add blob store aka. `bstore`
- Add Entity-Attribute-Value store aka. `eavstore`
- Add inverted index store aka. `pstore`

## `import found`

### `found.BaseFoundException`

All `found` exceptions inherit that class.

### `found.FoundException`

Exception raised when there is an error foundationdb client driver, or
foundationdb server side.

### `await found.open(cluster_file=None)`

Open database.

Coroutine that will open a connection with the cluster specified in
the file `cluster_file`. If `cluster_file` is not provided the default
is `/etc/foundationdb/fdb.cluster`. Returns a database object.

### `await found.transactional(db, func, *args, snapshot=False, **kwargs)`

Operate a transaction for `func`.

Coroutine that will operate a transaction against `db` for `func`. If
`snapshot=True` then the transaction is read-only. `func` will receive
an appropriate transaction object as first argument, then `args`, then
`kwargs`. Because of errors `transactional` might run `func` several
times, hence `func` should be idempotent.

### `await found.get(tx, key)`

Get the value associated with `key`.

Coroutine that will fetch the value associated with `key` inside the
database associated with `tx`. `key` must be `bytes`. In case of
success, returns `bytes`. Otherwise, if there is no value associated
with `key`, returns the object `None`.

### `await found.set(tx, key, value)`

Set `key` to `value`.

In the database associated with `tx`, associate `key` with
`value`. Both `key` and `value` must be `bytes`.

### `found.pack(tuple)`

Serialize python objects `tuple` into bytes.

### `found.pack_with_versionstamp(tuple)`

Serialize python objects `tuple` into bytes. `tuple` may contain
`found.Versionstamp` objects.

### `found.unpack(bytes)`

Deserialize bytes into python objects.

### `found.Versionstamp(...)`

FIXME.

### `await found.clear(tx, key, other=None)`

Remove key or keys.

In the database associated with `tx`, clear the specified `key` or
range of keys.

`key` and `other` if provided must be `bytes`.

If `other=None`, then clear the association that might exists with
`key`. Otherwise, if `other` is provided, `found.clear` will remove
any association between `key` and `other` but not the association with
`other` if any (that is `other` is excluded from the range).

### `await found.query(tx, key, other, *, limit=0, mode=STREAMING_MODE_ITERATOR)`

Fetch key-value pairs.

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

Returns the immediatly next byte sequence that is not prefix of `key`.

### `found.lt(key, offset=0)`

### `found.lte(key, offset=0)`

### `found.gt(key, offset=0)`

### `found.gte(key, offset=0)`

### `await found.read_version(tx)`

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

## `from found import bstore`

### `bstore.BStoreException`

Exception specific to `bstore`.

### `bstore.make(name, prefix)`

Handle over a `bstore` called `name` with `prefix`.

### `await bstore.get_or_create(tx, bstore, blob)`

### `await bstore.get(tx, bstore, uid)`

## `from found import nstore`

### `nstore.NStoreException`

Exception specific to `nstore`.

### `nstore.make(name, prefix, n)`

Create a handle over a `nstore` called `name` with `prefix` and `n`
columns.

The argument `name` should be a string, it is really meant to ease
debugging. `prefix` should be a tuple that can be packed with
`found.pack`. Last but not least, `n` is the number of columns in the
returned tuple store (or, if you prefer, the number of tuple items).

It is preferable to store the returned value.

### `await nstore.add(tx, nstore, *items, *, value=b'')`

In the database associated with `tx`, as part of `nstore`, add
`items` associated with `value`.

### `await nstore.remove(tx, nstore, *items)`

In the database associated with `tx`, as part of `nstore`, remove
`items` and the associated value.

### `await nstore.get(tx, nstore, *items)`

In the database associated with `tx`, as part of `nstore`, get the
value associated with `items`. If there is no such items in `nstore`,
returns `None`.

### `nstore.var(name)`

Create a variable called `name` for use with `nstore.query`.

### `await nstore.query(tx, nstore, pattern, *patterns)`

In the database associated with `tx`, as part of `nstore`, generate
mappings that match `pattern` and `patterns`. Both `pattern` and
`patterns` may contain `nstore.var` that will be replaced with
matching values in the generic tuple store.

## `from found import eavstore`

### `eavstore.make(name, prefix)`

Create a handle over an eavstore called `name` with `prefix`.

The argument `name` should be a string, it is really meant to ease
debugging. `prefix` should be a tuple that can be packed with
`found.pack`.

### `await eavstore.create(tx, eavstore, dict)`

Store a dictionary.

In the database associated with `tx`, as part of `eavstore`, save
`dict` and returns its unique identifier.

### `await eavstore.get(tx, eavstore, uid)`

Fetch a dictionary.

In the database associated with `tx`, as part of `eavstore`, retrieve
the dictionary associated with `uid`. If there is no such dictionary,
returns an empty dictionary.

### `await eavstore.remove(tx, eavstore, uid)`

Clear a dictionary.

In the database associated with `tx`, as part of `eavstore`, remove
the dictionary associated with `uid`.

### `await eavstore.update(tx, eavstore, uid, dict)`

Update a dictionary.

In the database associated with `tx`, as part of `eavstore`, replace
the dictionary associated with `uid` with `dict`.

### `await eavstore.query(tx, eavstore, key, value)`

Lookup dictionaries according to sppecification.

In the database associated with `tx`, as part of `eavstore`, generates
unique identifier for dictionaries that have `key` equal to `value`.

## `from found import pstore`

### `pstore.PStoreException`

Exception specific to `pstore`.

### `pstore.make(name, prefix, pool)`

A handle over a `pstore` called `name` with `prefix`, that will use
`pool`.

### `await pstore.index(tx, store, docuid, counter)`

Associates `docuid` with `counter`.

Coroutine that associates the identifier `docuid` with the dict-like
`counter` inside the database associated with `tx` at `store` for
later retriaval with `pstore.search`.

`counter` must be a dict-like mapping string to integers bigger than
zero.

### `await pstore.search(tx, store, keywords, limit)`

Return a sorted list of at most `limit` documents matching `keywords`.

## `from found import vnstore`

### `vnstore.make(name, prefix, items)`

Create a handle over a `vnstore` called `name` with the prefix tuple
`prefix`, and `items` as column names.

The argument name should be a string, it is really meant to ease
debugging. prefix should be a tuple that can be packed with
found.pack. Last but not least, `items` is the columns in the returned
tuple store (or, if you prefer, the name of tuple items).

It is preferable to store the returned value.

### `await vnstore.change_create(tr, vnstore)`

Return the unique idenifier of a new change in database.  Its initial
signifiance is `None` which means it is invisible to other
transactions, and its message `None`.

### `vnstore.change_continue(tr, vsntore, changeid)`

Against transaction `tr`, and `vnstore`, continue a change `changeid`.

### `await vnstore.change_message(tr, vnstore, changeid, message)`

Replace the exisiting message of `changeid` with `message`

### `await vnstore.change_appply(tr, vnstore, changeid)`

Apply the change `changeid` against `vnstore`, setting the next
`uuid7` as significance.

#### Known issue: No serializability guarantee, because of write skew anomaly

- The historization of data introduce a risk of inexact in two steps
  intorduce a serializability problem. This can break things when
  changes are related to some group of triples: Two changes, modify
  two overllaping triples, strict ordering, serializability is not
  guaranteed, hence one transaction may write, a value based on a
  value that was overwritten by another aka. write skew anomaly.

- The use `uuid7` can break consistency, when deleting the same
  triple, and adding another, it may result in two deletion, and two
  additions, that may break the schema.

In other words, as long as we rely `uuid7` we can't consider
transaction commited with `vnstore_change_apply` happen as if all
transaction were commited on after the other, that is, there is not
serializability guarantee.

There is several ways to workaround some of those issues, they require
more code. [Contact me for more info](mailto:amirouchhe@hyper.dev).

### `await vnstore.ask(tr, vnstore, *items)`

Return `True` if `items` is alive in the space `vnstore`.

### `await vnstore.get(tr, vnstore, *items)`

TODO

### `await vnstore.remove(tr, vnstore, *items)`

Remove `items` from `vnstore`.

### `await vnstore.query(tr, vnstore, pattern, *pattern)`

Return immutable mappings where `vnstore.var` from `pattern`, and
`patterns` are replaced with objects from `vnstore`.
