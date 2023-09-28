import asyncio
import found


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
    assert [(b'azul', b'world'), (b'hello', b'world')]

    print('What is done is not to be done.')


asyncio.run(readme())
