# [asyncio-foundationdb](https://github.com/amirouche/asyncio-foundationdb/)

*early draft*

asyncio drivers for foundationdb tested with CPython 3.8

```
pip install asyncio-foundationdb
```

```python
> import found
> import asyncio
> found.api_version(620)
> db = asyncio.run(found.open())
> asyncio.run(db.get(b'hello'))
> db.set(b'hello', b'world')
> asyncio.run(tr.get(b'hello'))
b'world'
```

## [Documentation](https://github.com/amirouche/asyncio-foundationdb/tree/master/doc)

## ChangeLog

### v0.9.0

- feature: bump to foundationdb 6.2.0 client API
- feature: add hooks and states

### v0.8.0

- breaking change: replace ``get_rangefoo`` with ``rangefoo`` as async generator
- new: add short syntax for querying `Nstore.query(tr, patterns)`
- chore: remove pipenv, and pre-commit
