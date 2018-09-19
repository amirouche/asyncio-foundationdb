import asyncio
import pytest

import found.v510 as fdb
from found.v510 import base


def test_pack_unpack():
    from found.v510.tuple import SingleFloat
    value = ((None, SingleFloat(3.1415), b'x42', 1, -1, 3.1415, -3.1415, ("abc",)), ("d", "e", "f"), 2.718281828459045)  # noqa
    assert fdb.unpack(fdb.pack(value)) == value


async def open():
    # XXX: hack around the fact that the loop is cached in found
    loop = asyncio.get_event_loop()
    base._loop = loop

    db = await fdb.open()
    # clean database
    tr = db._create_transaction()
    tr.clear_range(b"", b"\xff")
    await tr.commit()

    return db


@pytest.mark.asyncio
async def test_get():
    # preapre
    db = await open()
    tr = db._create_transaction()

    #
    out = await tr.get(b"test")
    assert out is None
    tr.set(b"test", b"test")
    out = await tr.get(b"test")
    assert out == b"test"


@pytest.mark.asyncio
async def test_range():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    for number in range(10):
        tr.set(fdb.pack((number,)), fdb.pack((str(number),)))
    await tr.commit()

    tr = db._create_transaction()
    out = await tr.get_range(fdb.pack((1,)), fdb.pack((8,)))
    await tr.commit()

    # check
    assert out
    for (key, value), index in zip(out, range(10)[1:-1]):
        assert fdb.unpack(key)[0] == index
        assert fdb.unpack(value)[0] == str(index)


@pytest.mark.asyncio
async def test_strinc_range():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    prefix_zero = b'\x00'
    tr.set(prefix_zero + b'\x01', fdb.pack((1,)))
    tr.set(prefix_zero + b'\x02', fdb.pack((2,)))
    tr.set(prefix_zero + b'\x03', fdb.pack((3,)))
    prefix_one = b'\x01'
    tr.set(prefix_one + b'\x42', fdb.pack((42,)))
    await tr.commit()

    # check
    tr = db._create_transaction()
    everything = await tr.get_range(None, None)
    await tr.commit()
    assert len(everything) == 4

    # check
    tr = db._create_transaction()
    everything = await tr.get_range(prefix_zero, fdb.strinc(prefix_zero))
    await tr.commit()
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_read_version():
    # prepare
    db = await open()

    # exec
    tr = db._create_transaction()
    out = await tr.read_version()
    await tr.commit()

    # check
    assert out


@pytest.mark.asyncio
async def test_startswith():
    # prepare
    db = await open()

    # exec
    tr = db._create_transaction()
    prefix_zero = b'\x00'
    tr.set(prefix_zero + b'\x01', fdb.pack((1,)))
    tr.set(prefix_zero + b'\x02', fdb.pack((2,)))
    tr.set(prefix_zero + b'\x03', fdb.pack((3,)))
    prefix_one = b'\x01'
    tr.set(prefix_one + b'\x42', fdb.pack((42,)))
    await tr.commit()

    # check
    tr = db._create_transaction()
    everything = await tr.get_range(None, None)
    await tr.commit()
    assert len(everything) == 4

    # check
    tr = db._create_transaction()
    everything = await tr.get_range_startswith(prefix_zero)
    await tr.commit()
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_transactional():

    @fdb.transactional
    async def deep(tr):
        out = await tr.get(b'\x00')
        return out

    @fdb.transactional
    async def txn(tr):
        tr.set(b'\x00', b'\x00')
        out = await deep(tr)
        return out

    # check
    db = await open()
    out = await txn(db)

    # check
    assert out == b'\x00'
