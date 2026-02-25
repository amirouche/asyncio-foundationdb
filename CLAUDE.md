# CLAUDE.md — asyncio-foundationdb (`found`)

## Quick Start

```bash
make init          # Install deps via Poetry
make check         # Run tests + bandit security lint
```

Requires Python 3.9+ and FoundationDB 7.3 (API version 730). Install FDB on Debian with `make debian`.

## Development Commands

| Command | Description |
|---------|-------------|
| `make init` | `pip install poetry` + `poetry install` |
| `make check` | pytest (verbose, fail-fast, capture=no) + bandit |
| `make check-fast` | pytest with `-x` (stop on first failure) |
| `make check-coverage` | Coverage report (terminal + HTML) |
| `make check-correctness` | FDB binding tester suite (needs running FDB) |
| `make lint` | `pylama found` |
| `make wip` | `black` + `isort` + commit "wip" |
| `make clean` | `git clean -fX` |

Max line length: 100 (see `.flake8`).

## Architecture

**Package:** `found/` — a CFFI-based async Python driver for FoundationDB.

```
found/
  __init__.py      # Re-exports public API from base.py + fdb.tuple utilities
  base.py          # Core: CFFI bridge, async event loop integration, all FDB primitives
  nstore.py        # N-tuple store with pattern matching via Variable
  eavstore.py      # Entity-Attribute-Value store
  bstore.py        # Content-addressable blob store (blake2b dedup, chunked)
  pstore.py        # Inverted index / posting store
  vnstore.py       # Versioned N-tuple store (versionstamp-ordered history)
  pool.py          # Thread pool parallel map utility
  ffibuild.py      # CFFI build config (reads fdb_c.h / fdb_c2.h)
  tester.py        # FDB binding tester stack machine
  tests.py         # All tests live here
```

### Key Design Decisions

- **Namedtuples, not classes.** `Database`, `Transaction`, `KeySelector`, and all store handles (`BStore`, `EAVStore`, `_NStore`, `PStore`, `_VNStore`) are namedtuples. Transaction is immutable; its `.vars` dict is the only mutable part (per-transaction state).
- **CFFI callback bridge.** Async ops wrap C futures: `loop.create_future()` + CFFI callback fires `loop.call_soon_threadsafe(future.set_result, ...)`. Network thread started once on first `open()`.
- **Stores use tuple prefixes** to partition the FDB keyspace. Created via `store.make(name, prefix)`.

## Core API Patterns

### Transactional wrapper (automatic retry)

```python
import found

db = await found.open()

async def my_op(tx, key):
    value = await found.get(tx, key)
    await found.set(tx, key, b"new")  # immediate C call, buffered until commit
    return value

result = await found.transactional(db, my_op, b"mykey")
```

`transactional(db, func, *args, snapshot=False, **kwargs)` creates a transaction, calls `func(tx, *args, **kwargs)`, commits, and retries on conflict.

### Reads are async, writes are immediate

- `await found.get(tx, key)` / `found.query(tx, begin, end)` — async (C future)
- `await found.set(tx, key, value)` / `await found.clear(tx, key)` — declared async but don't await internally; the C call is immediate (buffered until commit)

### Tuple layer

```python
found.pack((prefix, key))      # -> bytes
found.unpack(raw_bytes)        # -> tuple
```

### Key selectors

`found.lt(key)`, `found.lte(key)`, `found.gt(key)`, `found.gte(key)` — return `KeySelector` namedtuples for range queries.

### N-tuple store pattern matching

```python
from found import nstore
from found.nstore import var  # Variable = namedtuple("Variable", ("name",))

store = nstore.make("mystore", [42], 3)  # 3-column store at prefix (42,)

await nstore.add(tx, store, entity, "title", "Hello")

# Query with variables — returns async iterator of immutables.Map bindings
results = await found.all(nstore.select(tx, store, var("who"), "title", "Hello"))
# -> [Map({"who": entity})]

# Chain queries with where()
seed = nstore.select(tx, store, var("id"), "tag", "python")
results = await found.all(nstore.where(tx, store, seed, var("id"), "title", var("title")))
```

### Async iteration helpers

- `await found.all(async_iter)` — collect async generator into list
- `found.limit(async_iter, n)` — take first n items

## Testing

All tests are in `found/tests.py`. Run with `make check`.

```python
@pytest.mark.asyncio
async def test_something():
    db = await open()  # helper: opens DB + clears all data

    async def do_stuff(tx):
        await found.set(tx, found.pack((1,)), b"value")
        out = await found.get(tx, found.pack((1,)))
        assert out == b"value"

    await found.transactional(db, do_stuff)
```

Pattern: wrap test logic in an `async def` passed to `found.transactional()`.

## Dependencies

Core: `foundationdb>=7.3,<7.4`, `cffi`, `immutables`, `aiostream`, `loguru`, `uuid7`
Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `black`, `isort`, `pylama`, `bandit`
