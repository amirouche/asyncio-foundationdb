import asyncio
from uuid import uuid4

import pytest
from fdb.tuple import SingleFloat

import found
import found.base
from found import bstore, eavstore, nstore
from found.nstore import var


def test_pack_unpack():
    value = (
        (uuid4(), None, SingleFloat(3.1415), b"x42", 1, -1, 3.1415, -3.1415, ("abc",)),
        ("d", "e", "f"),
        2.718281828459045,
    )  # noqa
    assert found.unpack(found.pack(value)) == value


async def open():
    # XXX: hack around the fact that the loop is cached in found
    loop = asyncio.get_event_loop()
    found.base._loop = loop

    db = await found.open()

    async def purge(tx):
        await found.clear(tx, b"", b"\xff")

    await found.transactional(db, purge)

    return db


@pytest.mark.asyncio
async def test_noop():
    assert True


@pytest.mark.asyncio
async def test_get():
    # prepare
    db = await open()

    async def test0(tx):
        out = await found.get(tx, b"test")
        # check
        assert out is None

    # exec
    await found.transactional(db, test0)

    async def test1(tx):
        await found.set(tx, b"test", b"test")
        out = await found.get(tx, b"test")
        # check
        assert out == b"test"

    # exec
    await found.transactional(db, test1)


@pytest.mark.asyncio
async def test_query():
    # prepare
    db = await open()

    async def set(tx):
        for number in range(10):
            await found.set(tx, found.pack((number,)), found.pack((str(number),)))

    await found.transactional(db, set)

    async def query(tx):
        out = found.query(tx, found.pack((1,)), found.pack((8,)))
        out = await found.all(out)
        return out

    out = await found.transactional(db, query)
    for (key, value), index in zip(out, range(10)[1:-1]):
        assert found.unpack(key)[0] == index
        assert found.unpack(value)[0] == str(index)


@pytest.mark.asyncio
async def test_query_reverse():
    # prepare
    db = await open()

    async def set(tx):
        for number in range(11):
            await found.set(tx, found.pack((number,)), found.pack((str(number),)))

    await found.transactional(db, set)

    async def query(tx):
        out = found.query(tx, found.pack((8,)), found.pack((4,)))
        out = await found.all(out)
        return out

    out = await found.transactional(db, query)
    keys = [found.unpack(k)[0] for k, v in out]
    values = [found.unpack(v)[0] for k, v in out]
    assert keys == list(reversed(range(4, 9)))
    assert values == [str(x) for x in list(reversed(range(4, 9)))]


@pytest.mark.asyncio
async def test_next_prefix():
    # prepare
    db = await open()

    prefix_zero = b"\x00"
    prefix_one = b"\x01"

    # exec
    async def test(tx):
        await found.set(tx, prefix_zero + b"\x01", found.pack((1,)))
        await found.set(tx, prefix_zero + b"\x02", found.pack((2,)))
        await found.set(tx, prefix_zero + b"\x03", found.pack((3,)))
        await found.set(tx, prefix_one + b"\x42", found.pack((42,)))

    await found.transactional(db, test)

    # check
    async def query0(tx):
        everything = found.query(tx, b"", b"\xFF")
        everything = await found.all(everything)
        assert len(everything) == 4

    await found.transactional(db, query0)

    # check
    async def query1(tx):
        everything = found.query(tx, prefix_zero, found.next_prefix(prefix_zero))
        everything = await found.all(everything)
        assert len(everything) == 3

    await found.transactional(db, query1)


@pytest.mark.asyncio
async def test_read_version():
    # prepare
    db = await open()

    # exec
    async def read_version(tx):
        out = await found.read_version(tx)
        assert out

    await found.transactional(db, read_version)


@pytest.mark.asyncio
async def test_estimated_size_bytes():
    # prepare
    db = await open()

    # initial check

    out = await found.transactional(db, found.estimated_size_bytes, b"\x00", b"\xFF")
    assert out == 0

    # populate with a small set of keys and check

    for i in range(10):
        await found.transactional(
            db, found.set, bytes((i,)), b"\xFF" * found.MAX_SIZE_VALUE
        )

    out = await found.transactional(db, found.estimated_size_bytes, b"\x00", b"\xFF")
    # below 3 MB the estimated size is less accurate, only check it is positive
    assert 0 < out

    # populate with a large set of keys and check
    for i in range(100):
        await found.transactional(
            db, found.set, bytes((i,)), b"\xFF" * found.MAX_SIZE_VALUE
        )

    out = await found.transactional(db, found.estimated_size_bytes, b"\x00", b"\xFF")
    # estimated size hence approximate check
    assert abs(out - (found.MAX_SIZE_VALUE * 100)) < found.MAX_SIZE_VALUE


# nstore tests


@pytest.mark.asyncio
async def test_nstore_empty():
    ntest = nstore.make("test-name", [42], 3)
    assert ntest


@pytest.mark.asyncio
async def test_nstore_simple_single_item_db_subject_lookup():
    db = await open()
    ntest = nstore.make("test-name", [42], 3)

    expected = uuid4()

    async def prepare(tx):
        await nstore.add(tx, ntest, expected, "title", "hyper.dev")

    await found.transactional(db, prepare)

    async def query(tx):
        out = await found.all(
            nstore.select(tx, ntest, var("subject"), "title", "hyper.dev")
        )
        return out

    out = await found.transactional(db, query)
    out = out[0]["subject"]

    assert out == expected


@pytest.mark.asyncio
async def test_nstore_ask_rm_and_ask():
    db = await open()
    ntest = nstore.make("test-name", [42], 3)

    expected = uuid4()

    async def get(tx):
        out = await nstore.get(tx, ntest, expected, "title", "hyper.dev")
        return out

    out = await found.transactional(db, get)

    assert out is None

    async def add(tx):
        await nstore.add(tx, ntest, expected, "title", "hyper.dev")

    await found.transactional(db, add)
    out = await found.transactional(db, get)
    assert out == b""

    async def remove(tx):
        await nstore.remove(tx, ntest, expected, "title", "hyper.dev")

    await found.transactional(db, remove)

    out = await found.transactional(db, get)
    assert out is None


@pytest.mark.asyncio
async def test_nstore_simple_multiple_items_db_subject_lookup():
    db = await open()

    ntest = nstore.make("test-name", [42], 3)

    expected = uuid4()

    async def prepare(tx):
        await nstore.add(tx, ntest, expected, "title", "hyper.dev")
        await nstore.add(tx, ntest, uuid4(), "title", "blog.copernic.com")

    async def query(tx):
        out = await found.all(
            nstore.select(tx, ntest, var("subject"), "title", "hyper.dev")
        )
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)
    out = out[0]["subject"]
    assert out == expected


@pytest.mark.asyncio
async def test_nstore_complex():
    db = await open()

    ntest = nstore.make("test-name", [42], 3)

    async def prepare(tx):
        hyperdev = uuid4()
        await nstore.add(tx, ntest, hyperdev, "title", "hyper.dev")
        await nstore.add(tx, ntest, hyperdev, "keyword", "scheme")
        await nstore.add(tx, ntest, hyperdev, "keyword", "hacker")
        copernic = uuid4()
        await nstore.add(tx, ntest, copernic, "title", "blog.copernic.com")
        await nstore.add(tx, ntest, copernic, "keyword", "corporate")

    async def query(tx):
        seed = nstore.select(tx, ntest, var("identifier"), "keyword", "hacker")
        out = await found.all(
            nstore.where(tx, ntest, seed, var("identifier"), "title", var("blog"))
        )
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)
    out = sorted([x["blog"] for x in out])
    assert out == ["hyper.dev"]


@pytest.mark.asyncio
async def test_nstore_seed_subject_variable():
    db = await open()
    ntest = nstore.make("test-name", [42], 3)

    hyperdev = uuid4()
    copernic = uuid4()
    hypersocial = uuid4()

    async def prepare(tx):
        await nstore.add(tx, ntest, hyperdev, "title", "hyper.dev")
        await nstore.add(tx, ntest, hyperdev, "keyword", "scheme")
        await nstore.add(tx, ntest, hyperdev, "keyword", "hacker")

        await nstore.add(tx, ntest, copernic, "title", "copernic.space")
        await nstore.add(tx, ntest, copernic, "keyword", "corporate")

        await nstore.add(tx, ntest, hypersocial, "title", "hypersocial.space")
        await nstore.add(tx, ntest, hypersocial, "keyword", "python")
        await nstore.add(tx, ntest, hypersocial, "keyword", "hacker")

    async def query(tx):
        out = await found.all(
            nstore.select(tx, ntest, var("subject"), "keyword", "corporate")
        )
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)
    out = out[0]["subject"]

    assert out == copernic


@pytest.mark.asyncio
async def test_nstore_seed_subject_lookup():
    db = await open()

    ntest = nstore.make("test-name", [42], 3)

    hyperdev = uuid4()
    copernic = uuid4()
    hypersocial = uuid4()

    async def prepare(tx):
        await nstore.add(tx, ntest, hyperdev, "title", "hyper.dev")
        await nstore.add(tx, ntest, hyperdev, "keyword", "scheme")
        await nstore.add(tx, ntest, hyperdev, "keyword", "hacker")

        await nstore.add(tx, ntest, copernic, "title", "blog.copernic.com")
        await nstore.add(tx, ntest, copernic, "keyword", "corporate")

        await nstore.add(tx, ntest, hypersocial, "title", "hypersocial.space")
        await nstore.add(tx, ntest, hypersocial, "keyword", "python")
        await nstore.add(tx, ntest, hypersocial, "keyword", "hacker")

    async def query(tx):
        out = await found.all(
            nstore.select(tx, ntest, copernic, var("key"), var("value"))
        )
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)
    out = [dict(x) for x in out]

    expected = [
        {"key": "keyword", "value": "corporate"},
        {"key": "title", "value": "blog.copernic.com"},
    ]
    assert out == expected


@pytest.mark.asyncio
async def test_nstore_seed_object_variable():
    db = await open()
    ntest = nstore.make("test-name", [42], 3)

    hyperdev = uuid4()
    copernic = uuid4()
    hypersocial = uuid4()

    async def prepare(tx):
        await nstore.add(tx, ntest, hyperdev, "title", "hyper.dev")
        await nstore.add(tx, ntest, hyperdev, "keyword", "scheme")
        await nstore.add(tx, ntest, hyperdev, "keyword", "hacker")

        await nstore.add(tx, ntest, copernic, "title", "blog.copernic.com")
        await nstore.add(tx, ntest, copernic, "keyword", "corporate")

        await nstore.add(tx, ntest, hypersocial, "title", "hypersocial.space")
        await nstore.add(tx, ntest, hypersocial, "keyword", "python")
        await nstore.add(tx, ntest, hypersocial, "keyword", "hacker")

    async def query(tx):
        out = await found.all(nstore.select(tx, ntest, hyperdev, "title", var("title")))
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)
    out = out[0]["title"]
    assert out == "hyper.dev"


@pytest.mark.asyncio
async def test_nstore_subject_variable():
    db = await open()
    ntest = nstore.make("test-name", [42], 3)
    hyperdev = uuid4()
    post1 = uuid4()
    post2 = uuid4()

    async def prepare(tx):
        await nstore.add(tx, ntest, hyperdev, "title", "hyper.dev")
        await nstore.add(tx, ntest, hyperdev, "keyword", "scheme")
        await nstore.add(tx, ntest, hyperdev, "keyword", "hacker")
        await nstore.add(tx, ntest, post1, "blog", hyperdev)
        await nstore.add(tx, ntest, post1, "title", "hoply is awesome")
        await nstore.add(tx, ntest, post2, "blog", hyperdev)
        await nstore.add(tx, ntest, post2, "title", "hoply foundiple store")

    # exec, fetch all blog title from hyper.dev

    async def query(tx):
        query = nstore.select(tx, ntest, var("blog"), "title", "hyper.dev")
        query = nstore.where(tx, ntest, query, var("post"), "blog", var("blog"))
        out = await found.all(
            nstore.where(tx, ntest, query, var("post"), "title", var("title"))
        )
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)

    out = sorted([x["title"] for x in out])
    assert out == ["hoply foundiple store", "hoply is awesome"]


@pytest.mark.asyncio
async def test_nstore_query():
    db = await open()

    ntest = nstore.make("test-name", [42], 3)

    async def prepare(tx):
        hyperdev = uuid4()
        post1 = uuid4()
        post2 = uuid4()
        await nstore.add(tx, ntest, hyperdev, "title", "hyper.dev")
        await nstore.add(tx, ntest, hyperdev, "keyword", "scheme")
        await nstore.add(tx, ntest, hyperdev, "keyword", "hacker")
        await nstore.add(tx, ntest, post1, "blog", hyperdev)
        await nstore.add(tx, ntest, post1, "title", "hoply is awesome")
        await nstore.add(tx, ntest, post2, "blog", hyperdev)
        await nstore.add(tx, ntest, post2, "title", "hoply foundiple store")

    # exec, fetch all blog title from hyper.dev

    async def query(tx):
        query = [
            [var("blog"), "title", "hyper.dev"],
            [var("post"), "blog", var("blog")],
            [var("post"), "title", var("title")],
        ]
        out = await found.all(nstore.query(tx, ntest, *query))
        return out

    await found.transactional(db, prepare)
    out = await found.transactional(db, query)
    out = sorted([x["title"] for x in out])
    assert out == ["hoply foundiple store", "hoply is awesome"]


# bstore tests


@pytest.mark.asyncio
async def test_bstore_small():
    db = await open()

    store = bstore.make("bstore-test", (42,))

    expected = b"\xBE\xEF"

    uid = await found.transactional(db, bstore.get_or_create, store, expected)
    out = await found.transactional(db, bstore.get, store, uid)

    assert out == expected


@pytest.mark.asyncio
async def test_bstore_large():
    db = await open()

    store = bstore.make("bstore-test", (42,))

    expected = b"\xBE\xEF" * found.MAX_SIZE_VALUE

    uid = await found.transactional(db, bstore.get_or_create, store, expected)
    out = await found.transactional(db, bstore.get, store, uid)

    assert out == expected


@pytest.mark.asyncio
async def test_bstore_idempotent():
    db = await open()

    store = bstore.make("bstore-test", (42,))

    blob = b"\xBE\xEF" * found.MAX_SIZE_VALUE

    expected = await found.transactional(db, bstore.get_or_create, store, blob)
    out = await found.transactional(db, bstore.get_or_create, store, blob)

    assert out == expected


# eavstore tests


@pytest.mark.asyncio
async def test_eavstore_crud():
    db = await open()

    store = eavstore.make("eavstore-test", (42,))

    expected = dict(hello="world")

    uid = await found.transactional(db, eavstore.create, store, expected)
    out = await found.transactional(db, eavstore.get, store, uid)
    assert out == expected

    other = dict(hello="world", who="me")
    await found.transactional(db, eavstore.update, store, uid, other)
    out = await found.transactional(db, eavstore.get, store, uid)
    assert out == other

    await found.transactional(db, eavstore.remove, store, uid)
    out = await found.transactional(db, eavstore.get, store, uid)
    assert not out


@pytest.mark.asyncio
async def test_eavstore_crud_2():
    db = await open()

    store = eavstore.make("eavstore-test", (42,))

    expected = set()
    mydict = dict(key=42)
    for _ in range(10):
        uid = await found.transactional(db, eavstore.create, store, mydict)
        expected.add(uid)

    # add some unwanted dictionaries, with key != 42
    # before 42
    for value in range(42):
        mydict = dict(key=value)
        uid = await found.transactional(db, eavstore.create, store, mydict)
    # and after 42
    for value in range(43, 84):
        mydict = dict(key=value)
        uid = await found.transactional(db, eavstore.create, store, mydict)

    # query
    async def query(tx, store, key, value):
        out = set()
        async for uid in eavstore.query(tx, store, key, value):
            out.add(uid)
        return out

    out = await found.transactional(db, query, store, "key", 42)

    assert out == expected


@pytest.mark.asyncio
async def test_peace_search_store():
    import multiprocessing
    from concurrent import futures

    from found import pstore

    db = await open()

    store = pstore.make("test-pstore", (42,))

    DOC0 = dict(
        foundationdb=1,
        okvs=2,
        database=42,
    )
    DOC1 = dict(sqlite=1, sql=2, database=3)
    DOC2 = dict(
        spam=42,
    )
    for uid, doc in enumerate((DOC0, DOC1, DOC2)):
        await found.transactional(db, pstore.index, store, uid, doc)

    expected = [(0, 1)]
    out = await found.transactional(db, pstore.search, store, ["foundationdb"], 10)
    assert out == expected

    expected = [(2, 42)]
    out = await found.transactional(db, pstore.search, store, ["spam"], 10)
    assert out == expected

    expected = [(0, 42), (1, 3)]
    out = await found.transactional(db, pstore.search, store, ["database"], 10)
    assert out == expected
