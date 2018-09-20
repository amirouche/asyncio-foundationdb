import asyncio
from random import getrandbits

from found import v510 as fdb


def random(size):
    return b'\x00' + bytes(getrandbits(8) for _ in range(size))


@fdb.transactional
async def write(tr):
    key = random(512)
    value = random(10240)
    tr.set(key, value)
    return key


@fdb.transactional
async def read(tr, key):
    out = await tr.get(key)
    return out


async def main(db):
    for _ in range(10**3):
        # one write, two read
        key = await write(db)
        await read(db, key)
        await read(db, key)


# import uvloop
# asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

loop = asyncio.get_event_loop()
db = loop.run_until_complete(fdb.open())

coroutines = []
for _ in range(100):
    coroutines.append(main(db))


loop.run_until_complete(asyncio.gather(*coroutines))
