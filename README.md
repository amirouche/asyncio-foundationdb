# [asyncio-foundationdb](https://github.com/amirouche/asyncio-foundationdb/)

FoundationDB drivers for asyncio tested with CPython and PyPy 3.9+.

[![Library Database](https://images.unsplash.com/photo-1544383835-bda2bc66a55d?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1021&q=80)](https://unsplash.com/photos/lRoX0shwjUQ)

**One language. One API. Your data model.**

Most Python applications are secretly two programs: the Python part
you write, and the SQL part you also write, connected by an ORM that
pretends the gap doesn't exist. When something breaks at the boundary
— and it will — you need to hold two mental models at once, or find
someone who speaks both.

asyncio-foundationdb is a bet that this doesn't have to be true.

FoundationDB gives you a foundation (pun intended) that scales from a
weekend project on a single box to a distributed system handling real
production load — without changing your data layer. On top of that,
this library gives you Python-native building blocks: tuple stores,
blob stores, pattern-matching queries, versioned knowledge graphs. No
SQL. No ORM. No impedance mismatch.

You choose your domain model. You express it in Python. You own the
full stack, in one language, with one place to look when things go
wrong.

This is not about avoiding complexity. It's about choosing which
complexity you live with — and keeping it visible.

## Links

- [FoundationDB Website](https://www.foundationdb.org/)
- [FoundationDB Forum](https://forums.foundationdb.org/)
- [FoundationDB Documentation](https://apple.github.io/foundationdb/)

## Installation

In a minute, install FoundationDB 7.3+, getting the latest stable release
from the official release page: https://github.com/apple/foundationdb/releases/tag/7.3.69

Then install asyncio drivers `asyncio-foundationdb`:

```
pip install asyncio-foundationdb
```

To use the built-in HTTP server (powered by [uvicorn](https://www.uvicorn.org/)):

```
pip install asyncio-foundationdb[server]
```

This pulls in `uvicorn`, `jinja2`, `zstandard`, and `more-itertools`.

## Example

```python
async def readme():

    async def get(tx, key):
        out = await found.get(tx, key)
        return out

    async def set(tx, key, value):
        await found.set(tx, key, value)

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
    assert out == [(b'azul', b'world'), (b'hello', b'world')]

asyncio.run(readme())
```

## ChangeLog

### v0.13.0

- Upgrade to FoundationDB 7.3 (API version 730)
- Add binding tester (correctness test suite) with CI workflows, tested under both POSIX threads (`tester_pthread.py`) and asyncio tasks (`tester_aio.py`) concurrency modes
- Add new public APIs: `get_key`, `commit`, `on_error`, `reset`, `cancel`, `get_committed_version`, `get_approximate_size`, `get_versionstamp`, `add_conflict_range`, `set_option`, `get_range_split_points`
- Add `append_if_fits`, `compare_and_clear`, `get_client_version`, `get_addresses_for_key`, `database_set_option`, `network_set_option`, `add_network_thread_completion_hook`, `error_predicate`
- Add docstrings to all public functions and module docstrings to all modules
- Support Python 3.9+
- Refactor base.py to use `asyncio.get_running_loop()` instead of deprecated `asyncio.get_event_loop()`
- Fix `gte()` ignoring the `offset` parameter
- Fix assert bug in readme.py example
- Check `fdb_create_database()` return code for errors
- Make ffibuild.py portable (use `FDB_INCLUDE_DIR` / `FDB_LIB_DIR` env vars)
- Clean up pyproject.toml for Poetry 2.x compatibility
- Upgrade bandit to 1.9+ for Python 3.14 compatibility

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

The function `func` receive transaction object that should be passed
to other database functions. It has a property `vars` that is a
dictionary that can be used to cache objects for the extent of the
transaction.

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

### `found.has_incomplete_versionstamp(tuple)`

Return `True` if `tuple` contains at least one incomplete
`Versionstamp`. Useful to validate input before calling
`found.pack_with_versionstamp`.

### `found.Versionstamp(...)`

Represents a FoundationDB versionstamp. Used with
`found.pack_with_versionstamp` to create keys or values that will be
filled in by FoundationDB with a unique, monotonically increasing
version at commit time.

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

### `await found.get_key(tx, key_selector)`

Resolve a key selector to a key.

In the database associated with `tx`, resolve the given
`key_selector` and return the resulting key as `bytes`. The
`key_selector` should be created with `found.lt`, `found.lte`,
`found.gt`, or `found.gte`.

### `await found.commit(tx)`

Commit the transaction.

Explicitly commit the transaction `tx`. This is done automatically
by `found.transactional`, but is useful when managing transactions
manually with `found._make_transaction`.

### `await found.on_error(tx, code)`

Handle a transaction error.

Pass error `code` to FoundationDB's conflict resolution logic. If
the error is retryable, the transaction is reset and the coroutine
returns. If the error is not retryable, raises `FoundException`.

### `found.reset(tx)`

Reset the transaction.

Reset `tx` to its initial state, as if it had just been created.
This allows the transaction object to be reused for a new operation.

### `found.cancel(tx)`

Cancel the transaction.

Cancel `tx`, causing any pending or future operations on it to fail
with an error.

### `found.get_committed_version(tx)`

Return the committed version of the transaction.

After a successful commit, returns the version at which the
transaction was committed as an integer. Must be called after
`found.commit`.

### `await found.get_approximate_size(tx)`

Return the approximate size of the transaction in bytes.

Returns the approximate byte size of the transaction so far,
including all keys, values, and conflict ranges. Useful for
monitoring whether a transaction is approaching the 10 MB limit.

### `await found.get_versionstamp(tx)`

Return the versionstamp of a committed transaction.

Returns the 10-byte versionstamp as `bytes`. The future must be
created before commit and awaited after commit completes.

### `found.add_conflict_range(tx, begin, end, conflict_type)`

Add a conflict range to the transaction.

Manually add a read or write conflict range to `tx`. `begin` and
`end` must be `bytes`. `conflict_type` must be
`found.CONFLICT_RANGE_TYPE_READ` or
`found.CONFLICT_RANGE_TYPE_WRITE`.

### `found.set_option(tx, option, value=None)`

Set a transaction option.

Set an option on `tx`. `option` must be one of the
`FDB_TR_OPTION_*` integer constants. `value` is optional and must
be `bytes` when provided.

### `found.watch(tx, key)`

Watch a key for changes.

Registers a watch on `key` (synchronous C call) and returns an
`asyncio.Future` that resolves to `None` when the key is modified by another
transaction. The watch only detects external changes after the transaction that
created it has been committed. `key` must be `bytes`.

```python
# Register the watch on a fresh transaction
tx = found._make_transaction(db)
watch_future = found.watch(tx, key)
await found.commit(tx)         # activates the watch for external changes

# ... in another task, modify the key ...
await watch_future             # resolves when the key changes
```

Unused watch futures should be cancelled (`watch_future.cancel()`) to avoid
resource exhaustion (default limit: 10,000 active watches per connection).

### `await found.get_range_split_points(tx, begin, end, chunk_size)`

Get split points for a key range.

In the database associated with `tx`, return a list of `bytes` keys
that divide the range from `begin` to `end` into chunks of approximately
`chunk_size` bytes each. `begin` and `end` must be `bytes`.
`chunk_size` is an integer in bytes. Returns an empty list if the range
is empty or smaller than `chunk_size`.

### `await found.estimated_size_bytes(tx, begin, end)`

Estimate the byte size of a key range.

In the database associated with `tx`, return an estimate of the
byte size of the range from `begin` to `end`. Both `begin` and `end`
must be `bytes`. The estimate is approximate, especially for ranges
smaller than 3 MB.

### `found.next_prefix(key)`

Returns the immediately next byte sequence that is not a prefix of
`key`. Raises `ValueError` if `key` is made entirely of `0xFF` bytes.

### `found.lt(key, offset=0)`

Create a key selector that resolves to the last key lexicographically
less than `key`. `key` must be `bytes`. Use with `found.query`.

### `found.lte(key, offset=0)`

Create a key selector that resolves to the last key lexicographically
less than or equal to `key`. `key` must be `bytes`. Use with
`found.query`.

### `found.gt(key, offset=1)`

Create a key selector that resolves to the first key lexicographically
greater than `key`. `key` must be `bytes`. Use with `found.query`.

### `found.gte(key, offset=1)`

Create a key selector that resolves to the first key lexicographically
greater than or equal to `key`. `key` must be `bytes`. Use with
`found.query`.

### `await found.read_version(tx)`

Return the read version of the transaction `tx` as an integer.

### `await found.set_read_version(tx, version)`

Set the read version of the transaction `tx` to `version`. The
transaction must not be a snapshot transaction.

### `found.co(func)`

Decorator that wraps a synchronous function into a coroutine. The
wrapped function can then be used with `await`.

### `await found.all(aiogenerator)`

Collect all items from an async generator into a list and return it.

### `found.limit(iterator, length)`

Async generator that yields at most `length` items from `iterator`.

### `await found.add(tx, key, param)`

Perform an atomic add of `param` to the value at `key`.

### `await found.bit_and(tx, key, param)`

Perform an atomic bitwise AND of `param` with the value at `key`.

### `await found.bit_or(tx, key, param)`

Perform an atomic bitwise OR of `param` with the value at `key`.

### `await found.bit_xor(tx, key, param)`

Perform an atomic bitwise XOR of `param` with the value at `key`.

### `await found.max(tx, key, param)`

Atomically set the value at `key` to the larger of the existing value
and `param`, compared as unsigned integers.

### `await found.byte_max(tx, key, param)`

Atomically set the value at `key` to the lexicographically larger of
the existing value and `param`.

### `await found.min(tx, key, param)`

Atomically set the value at `key` to the smaller of the existing value
and `param`, compared as unsigned integers.

### `await found.byte_min(tx, key, param)`

Atomically set the value at `key` to the lexicographically smaller of
the existing value and `param`.

### `await found.set_versionstamped_key(tx, key, param)`

Set `key` with an embedded versionstamp to `param`. The key must
contain an incomplete versionstamp.

### `await found.set_versionstamped_value(tx, key, param)`

Set `key` to `param` where `param` contains an embedded versionstamp.
The value must contain an incomplete versionstamp.

### `await found.append_if_fits(tx, key, param)`

Atomically append `param` to the value at `key`. If the resulting value
would exceed the maximum value size, the operation has no effect.

### `await found.compare_and_clear(tx, key, param)`

Atomically clear `key` if its current value equals `param`. If the
value does not match, the key is left unchanged.

### `found.get_client_version()`

Return the FDB client library version string (synchronous).

### `await found.get_addresses_for_key(tx, key)`

Return a list of strings representing the storage server addresses
responsible for `key`. `key` must be `bytes`.

### `found.database_set_option(db, option, value=None)`

Set a database-level option. `option` must be one of the
`FDB_DB_OPTION_*` integer constants. `value` is optional and must
be `bytes` when provided.

### `found.network_set_option(option, value=None)`

Set a network-level option. `option` must be one of the
`FDB_NET_OPTION_*` integer constants. `value` is optional and must
be `bytes` when provided. Must be called before the network thread
starts (i.e., before the first `found.open()` call).

### `found.add_network_thread_completion_hook(callback)`

Register a callback to be invoked when the FDB network thread exits.
`callback` must be a callable taking no arguments.

### `found.error_predicate(predicate, code)`

Test whether an error `code` matches `predicate`. Returns `True` or
`False`. Predicate constants:

- `found.ERROR_PREDICATE_RETRYABLE` (50000)
- `found.ERROR_PREDICATE_MAYBE_COMMITTED` (50001)
- `found.ERROR_PREDICATE_RETRYABLE_NOT_COMMITTED` (50002)

## `from found import bstore`

`bstore` is a content-addressable blob store. You hand it an arbitrary
binary payload and it returns a stable uid; store the same bytes twice
and you get the same uid back without writing a second copy, because
every blob is hashed with blake2b before storage. Reach for `bstore`
when your data includes large or repeated binary objects — files,
images, serialized artifacts — that you want to reference by identity
rather than by the content itself.

### `bstore.BStoreException`

Exception specific to `bstore`.

### `bstore.make(name, prefix)`

Handle over a `bstore` called `name` with `prefix`.

### `await bstore.get_or_create(tx, bstore, blob)`

Store `blob` and return its uid. If a blob with the same content
already exists, return the existing uid without storing a duplicate.

### `await bstore.get(tx, bstore, uid)`

Retrieve the blob associated with `uid`. Raises `BStoreException`
if not found.

## `from found import nstore`

`nstore` is a generic N-tuple store with pattern-matching queries. You
define a store of fixed width N and add tuples to it; you then query by
supplying a pattern where any position can be a concrete value or a
`var`, and the store yields all bindings that satisfy the pattern. It
maintains a minimal set of index permutations automatically so that any
query pattern resolves in a single ordered range scan. Reach for
`nstore` when your data is naturally relational and you want to express
queries as patterns — think Datalog or a triple store — rather than
building explicit indexes by hand.

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

### `nstore.select(tx, nstore, *pattern, seed=Map())`

Yield immutable bindings that match `pattern`. Each element of
`pattern` is either a value or a `nstore.var`. This is the
low-level primitive used by `nstore.query`.

### `nstore.where(tx, nstore, iterator, *pattern)`

For each binding from `iterator`, bind `pattern` and yield matching
bindings from `nstore`. Used to chain queries together.

### `nstore.query(tx, nstore, pattern, *patterns)`

In the database associated with `tx`, as part of `nstore`, generate
mappings that match `pattern` and `patterns`. Both `pattern` and
`patterns` may contain `nstore.var` that will be replaced with
matching values in the generic tuple store.

## `from found import eavstore`

`eavstore` is an entity-attribute-value store for Python dictionaries.
Each call to `create` stores a dict under a generated uid, and the store
automatically maintains a reverse index on every attribute-value pair so
you can look up all entities that share a given key-value combination.
Reach for `eavstore` when your records have irregular shapes — different
keys per entity, optional fields — or when you need attribute-level
lookup without defining a schema up front.

### `eavstore.make(name, prefix)`

Create a handle over an eavstore called `name` with `prefix`.

The argument `name` should be a string, it is really meant to ease
debugging. `prefix` should be a tuple that can be packed with
`found.pack`.

### `await eavstore.create(tx, eavstore, dict, uid=None)`

Store a dictionary.

In the database associated with `tx`, as part of `eavstore`, save
`dict` and returns its unique identifier. If `uid` is provided,
use it instead of generating a new one.

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

Lookup dictionaries according to specification.

In the database associated with `tx`, as part of `eavstore`, generates
unique identifier for dictionaries that have `key` equal to `value`.

## `from found import pstore`

`pstore` is an inverted index for keyword search. You index each
document as a mapping of string terms to positive integer counts; later
you query with a set of keywords and get back the top-scoring document
uids, ranked by how well the terms match. Reach for `pstore` when you
need relevance-ranked full-text or keyword search over documents whose
primary content lives elsewhere in the database.

### `pstore.PStoreException`

Exception specific to `pstore`.

### `pstore.make(name, prefix)`

Create a handle over a `pstore` called `name` with `prefix`.

### `await pstore.index(tx, store, docuid, counter)`

Associates `docuid` with `counter`.

Coroutine that associates the identifier `docuid` with the dict-like
`counter` inside the database associated with `tx` at `store` for
later retrieval with `pstore.search`.

`counter` must be a dict-like mapping string to integers bigger than
zero.

### `await pstore.search(tx, store, keywords, limit)`

Return a sorted list of at most `limit` documents matching `keywords`.

## `from found import vnstore`

`vnstore` is a versioned N-tuple store. It wraps the same pattern-
matching model as `nstore` but groups every addition and removal into a
named change-set; a change is invisible until you explicitly apply it,
at which point it receives a uuid7 significance that defines its place
in history. Reach for `vnstore` when you need an auditable log of
modifications, or when you want to stage a batch of changes for review
before making them visible to other readers.

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

### `await vnstore.change_list(tr, vnstore)`

Return a list of all changes in `vnstore`. Each change is a
dictionary with keys `uid`, `type`, `significance`, and `message`.

### `await vnstore.change_get(tr, vnstore, changeid)`

Return the change as a dictionary with keys `uid`, `type`,
`significance`, and `message`. Returns `None` if the change does
not exist.

### `vnstore.change_continue(tr, vnstore, changeid)`

Against transaction `tr`, and `vnstore`, continue a change `changeid`.
This sets the active change on the transaction so that subsequent
`vnstore.add` and `vnstore.remove` calls are associated with it.

### `await vnstore.change_message(tr, vnstore, changeid, message)`

Replace the existing message of `changeid` with `message`.

### `await vnstore.change_changes(tr, vnstore, changeid)`

Return a list of all tuple modifications (additions and removals)
associated with `changeid`.

### `await vnstore.change_apply(tr, vnstore, changeid)`

Apply the change `changeid` against `vnstore`, setting the next
`uuid7` as significance.

#### Known issue: Weak serializability

The use of `uuid7` instead of versionstamps can break things when
changes happen over overlapping versioned triples. Strict ordering,
serializability is not guaranteed, hence one transaction may write, a
value based on a value that was overwritten by another change that
appears to be commited after according to its `uuid7` significance.
Even if changes are commited in the correct order uuid7 does not
guarantee serializability.

In other words, as long as we rely `uuid7` we can't consider changes
commited with `vnstore_change_apply` happen as if all changes were
commited after the other, that is, there is no serializability
guarantee.

[Contact me for workarounds](mailto:amirouche@hyper.dev)

#### Known issue: consistency

Since changes may be constructed with several transactions, it is
possible that two changes introduce consistency bugs.

[Contact me for workarounds](mailto:amirouche@hyper.dev)

### `vnstore.select(tr, vnstore, *pattern, seed=Map())`

Yield immutable bindings that match `pattern` against alive tuples
in `vnstore`. Each element of `pattern` is either a value or a
`nstore.var`. This is the low-level primitive used by
`vnstore.query`.

### `await vnstore.ask(tr, vnstore, *items)`

Return `True` if `items` is alive in the space `vnstore`.

### `await vnstore.add(tr, vnstore, *items)`

Add `items` to `vnstore` under the current active change (set via
`vnstore.change_continue`). Returns `True`.

### `await vnstore.remove(tr, vnstore, *items)`

Remove `items` from `vnstore` under the current active change. Returns
`True` if the items existed and were removed, `False` otherwise.

### `await vnstore.where(tr, vnstore, iterator, *pattern)`

Bind `pattern` against each binding from `iterator`, then yield
matching bindings from `vnstore`. Used to chain queries together.

### `await vnstore.query(tr, vnstore, pattern, *patterns)`

Return immutable mappings where `vnstore.var` from `pattern`, and
`patterns` are replaced with objects from `vnstore`.

## `from found import pool`

`pool` is a low-level utility, not a domain abstraction. It provides a
single helper that fans an async iterator out to a thread-pool executor
and streams results back as each completes. Reach for it when you need
to parallelize CPU-bound or blocking work alongside async database
operations, and none of the domain stores above is the right layer for
that parallelism.

### `await pool.pool_for_each_par_map(loop, pool, f, p, iterator)`

Apply `p` in `pool` threads over `iterator`, calling `f` on each
result as it completes. `loop` is the asyncio event loop, `pool` is
a `concurrent.futures.ThreadPoolExecutor`.
