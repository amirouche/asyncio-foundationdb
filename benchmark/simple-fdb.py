import asyncio
from random import getrandbits

import fdb


fdb.api_version(510)


def random(size):
    return b'\x00' + bytes(getrandbits(8) for _ in range(size))


@fdb.transactional
def write(tr):
    key = random(512)
    value = random(10240)
    tr.set(key, value)
    return key


@fdb.transactional
def read(tr, key):
    out = tr.get(key)
    return out


def main():
    db = fdb.open()
    for _ in range(10**4):
        # one write, two read
        key = write(db)
        read(db, key)
        read(db, key)


main()
