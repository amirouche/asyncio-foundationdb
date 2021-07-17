# [asyncio-foundationdb](https://github.com/amirouche/asyncio-foundationdb/)

*early draft*

asyncio drivers for foundationdb tested with CPython 3.9 and PyPy 3.7

[![Library Database]](https://images.unsplash.com/photo-1544383835-bda2bc66a55d?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1021&q=80)](https://unsplash.com/photos/lRoX0shwjUQ)

## Getting started

```
pip install asyncio-foundationdb
```

```python
import found


def get(tx, key):
    out = await found.get(tx, key)

def set(tx, key, value):
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

### v0.9.x

- feature: bump to foundationdb 6.3.15 client API
- feature: add hooks and states

### v0.8.0

- breaking change: replace ``get_rangefoo`` with ``rangefoo`` as async generator
- new: add short syntax for querying `Nstore.query(tr, patterns)`
- chore: remove pipenv, and pre-commit

## API reference

### `BaseFoundException`

All `found` exception inherit that class.

### `FoundException`

Exception raised when their is problem foundationdb client drivers
side or foundationdb server side.
