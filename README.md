# [asyncio-foundationdb](https://github.com/amirouche/asyncio-foundationdb/)

*early draft*

asyncio drivers for foundationdb tested with CPython 3.9

```
pip install asyncio-foundationdb
```

```python
> import found
> found.api_version(630)
> db = await found.open()
> await db.get(b'hello')
> await db.set(b'hello', b'world')
> await tr.get(b'hello')
b'world'
```

## ChangeLog

### v0.9.x

- feature: bump to foundationdb 6.3.15 client API
- feature: add hooks and states

### v0.8.0

- breaking change: replace ``get_rangefoo`` with ``rangefoo`` as async generator
- new: add short syntax for querying `Nstore.query(tr, patterns)`
- chore: remove pipenv, and pre-commit
