import asyncio
from uuid import uuid4

import pytest
from fdb.tuple import SingleFloat

import found
import found.base
from found.ext import bstore, eavstore, nstore, vnstore
from found.ext.nstore import var


def test_pack_unpack():
    value = (
        (uuid4(), None, SingleFloat(3.1415), b"x42", 1, -1, 3.1415, -3.1415, ("abc",)),
        ("d", "e", "f"),
        2.718281828459045,
    )  # noqa
    assert found.unpack(found.pack(value)) == value


async def open():
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
        everything = found.query(tx, b"", b"\xff")
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
async def test_get_range_split_points():
    # prepare
    db = await open()

    begin = found.pack((0,))
    end = found.pack((100,))

    # populate with a small amount of data (keeps DB size below estimation noise)
    for i in range(10):
        await found.transactional(db, found.set, found.pack((i,)), b"\x00" * 100)

    # chunk_size of 1 byte asks FDB for as many split points as possible
    out = await found.transactional(db, found.get_range_split_points, begin, end, 1)

    # split points may be empty for small data sets — verify shape only
    assert isinstance(out, list)
    for key in out:
        assert isinstance(key, bytes)
        assert begin <= key <= end


@pytest.mark.asyncio
async def test_estimated_size_bytes():
    # prepare
    db = await open()

    # initial check

    out = await found.transactional(db, found.estimated_size_bytes, b"\x00", b"\xff")
    assert out == 0

    # populate with a small set of keys and check

    for i in range(10):
        await found.transactional(db, found.set, bytes((i,)), b"\xff" * found.MAX_SIZE_VALUE)

    out = await found.transactional(db, found.estimated_size_bytes, b"\x00", b"\xff")
    # below 3 MB the estimated size is less accurate, only check it is positive
    assert 0 < out

    # populate with a large set of keys and check
    for i in range(100):
        await found.transactional(db, found.set, bytes((i,)), b"\xff" * found.MAX_SIZE_VALUE)

    out = await found.transactional(db, found.estimated_size_bytes, b"\x00", b"\xff")
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
        out = await found.all(nstore.select(tx, ntest, var("subject"), "title", "hyper.dev"))
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
        out = await found.all(nstore.select(tx, ntest, var("subject"), "title", "hyper.dev"))
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
        out = await found.all(nstore.select(tx, ntest, var("subject"), "keyword", "corporate"))
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
        out = await found.all(nstore.select(tx, ntest, copernic, var("key"), var("value")))
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
        out = await found.all(nstore.where(tx, ntest, query, var("post"), "title", var("title")))
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

    expected = b"\xbe\xef"

    uid = await found.transactional(db, bstore.get_or_create, store, expected)
    out = await found.transactional(db, bstore.get, store, uid)

    assert out == expected


@pytest.mark.asyncio
async def test_bstore_large():
    db = await open()

    store = bstore.make("bstore-test", (42,))

    expected = b"\xbe\xef" * found.MAX_SIZE_VALUE

    uid = await found.transactional(db, bstore.get_or_create, store, expected)
    out = await found.transactional(db, bstore.get, store, uid)

    assert out == expected


@pytest.mark.asyncio
async def test_bstore_idempotent():
    db = await open()

    store = bstore.make("bstore-test", (42,))

    blob = b"\xbe\xef" * found.MAX_SIZE_VALUE

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
async def test_co_decorator():
    @found.co
    def add(a, b):
        return a + b

    result = await add(1, 2)
    assert result == 3


@pytest.mark.asyncio
async def test_all():
    async def gen():
        for i in range(5):
            yield i

    out = await found.all(gen())
    assert out == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_limit():
    async def gen():
        for i in range(10):
            yield i

    out = await found.all(found.limit(gen(), 3))
    assert out == [0, 1, 2]

    # limit of 0 yields nothing
    out = await found.all(found.limit(gen(), 0))
    assert out == []


@pytest.mark.asyncio
async def test_query_with_limit():
    db = await open()

    async def setup(tx):
        for number in range(10):
            await found.set(tx, found.pack((number,)), found.pack((str(number),)))

    await found.transactional(db, setup)

    async def do_query(tx):
        out = found.query(tx, found.pack((0,)), found.pack((9,)), limit=3)
        return await found.all(out)

    out = await found.transactional(db, do_query)
    assert len(out) == 3
    assert found.unpack(out[0][0])[0] == 0


@pytest.mark.asyncio
async def test_set_read_version():
    db = await open()

    # First, get a valid read version
    async def get_version(tx):
        return await found.read_version(tx)

    version = await found.transactional(db, get_version)

    # Now use set_read_version on a fresh transaction
    async def do(tx):
        await found.set_read_version(tx, version)
        out = await found.get(tx, b"nonexistent")
        assert out is None

    await found.transactional(db, do)


@pytest.mark.asyncio
async def test_watch():
    db = await open()

    key = b"watch_test_key"

    # Set initial value
    await found.transactional(db, found.set, key, b"initial")

    # Register the watch (synchronous C call) on a fresh transaction
    tx = found.base.make_transaction(db, snapshot=False)
    watch_future = await found.watch(tx, key)  # activates on commit
    await found.commit(tx)  # watch now monitors external changes

    # Concurrently modify the key from another transaction
    async def modify():
        await asyncio.sleep(0.05)
        await found.transactional(db, found.set, key, b"modified")

    modify_task = asyncio.create_task(modify())

    # Both the watch and the modification should complete
    await asyncio.gather(
        asyncio.wait_for(watch_future, timeout=5.0),
        modify_task,
    )


@pytest.mark.asyncio
async def test_clear_single_key():
    db = await open()

    async def setup(tx):
        await found.set(tx, b"clearme", b"value")

    await found.transactional(db, setup)

    async def verify_exists(tx):
        return await found.get(tx, b"clearme")

    out = await found.transactional(db, verify_exists)
    assert out == b"value"

    async def do_clear(tx):
        await found.clear(tx, b"clearme")

    await found.transactional(db, do_clear)

    out = await found.transactional(db, verify_exists)
    assert out is None


@pytest.mark.asyncio
async def test_atomic_add():
    db = await open()
    import struct

    key = b"counter"

    async def setup(tx):
        await found.set(tx, key, struct.pack("<q", 0))

    await found.transactional(db, setup)

    async def do_add(tx):
        await found.add(tx, key, struct.pack("<q", 5))

    await found.transactional(db, do_add)

    async def check(tx):
        raw = await found.get(tx, key)
        return struct.unpack("<q", raw)[0]

    out = await found.transactional(db, check)
    assert out == 5


def test_next_prefix_all_ff():
    with pytest.raises(ValueError):
        found.next_prefix(b"\xff")

    with pytest.raises(ValueError):
        found.next_prefix(b"\xff\xff\xff")


@pytest.mark.asyncio
async def test_peace_search_store():
    from found.ext import pstore

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


@pytest.mark.asyncio
async def test_append_if_fits():
    db = await open()

    key = b"append_test"

    async def setup(tx):
        await found.set(tx, key, b"hello")

    await found.transactional(db, setup)

    async def do_append(tx):
        await found.append_if_fits(tx, key, b" world")

    await found.transactional(db, do_append)

    async def check(tx):
        return await found.get(tx, key)

    out = await found.transactional(db, check)
    assert out == b"hello world"


@pytest.mark.asyncio
async def test_compare_and_clear():
    db = await open()

    key = b"cac_test"

    # Set key, then compare_and_clear with matching value — key should be gone
    async def setup(tx):
        await found.set(tx, key, b"match")

    await found.transactional(db, setup)

    async def do_clear_match(tx):
        await found.compare_and_clear(tx, key, b"match")

    await found.transactional(db, do_clear_match)

    async def check(tx):
        return await found.get(tx, key)

    out = await found.transactional(db, check)
    assert out is None

    # Set key, then compare_and_clear with non-matching value — key should remain
    await found.transactional(db, setup)

    async def do_clear_no_match(tx):
        await found.compare_and_clear(tx, key, b"nope")

    await found.transactional(db, do_clear_no_match)

    out = await found.transactional(db, check)
    assert out == b"match"


def test_get_client_version():
    import re

    version = found.get_client_version()
    assert isinstance(version, str)
    assert re.search(r"\d+\.\d+", version), f"unexpected version string: {version!r}"


@pytest.mark.asyncio
async def test_get_addresses_for_key():
    db = await open()

    key = b"addr_test"

    # Write a key so storage servers have it
    await found.transactional(db, found.set, key, b"value")

    async def do_get_addresses(tx):
        return await found.get_addresses_for_key(tx, key)

    out = await found.transactional(db, do_get_addresses)
    assert isinstance(out, list)
    for addr in out:
        assert isinstance(addr, str)


@pytest.mark.asyncio
async def test_database_set_option():
    db = await open()
    # FDB_DB_OPTION_TRANSACTION_TIMEOUT = 500
    import struct

    found.database_set_option(db, 500, struct.pack("<q", 5000))


def test_error_predicate():
    # error code 1020 = not_committed, should be retryable
    assert found.error_predicate(found.ERROR_PREDICATE_RETRYABLE, 1020) is True
    # error code 1021 = commit_unknown_result, retryable and maybe_committed
    assert found.error_predicate(found.ERROR_PREDICATE_RETRYABLE, 1021) is True
    assert found.error_predicate(found.ERROR_PREDICATE_MAYBE_COMMITTED, 1021) is True
    # error code 2000 is not retryable
    assert found.error_predicate(found.ERROR_PREDICATE_RETRYABLE, 2000) is False


# vnstore tests


v = nstore.v


@pytest.mark.asyncio
async def test_vnstore_empty():
    ntest = vnstore.make("test-name", ["subspace-42"], ["uid", "key", "value"])
    assert ntest


@pytest.mark.asyncio
async def test_vnstore_query_zero():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    for i in range(10):
        expected = uuid4()

        async def subject_query(tx):
            out = await vnstore.query(tx, ntest, (nstore.v("subject"), "title", "hypermove.fr"))
            out = await found.all(out)
            return out

        out = await found.transactional(db, subject_query)

        assert not out

        change = await found.transactional(db, vnstore.change_create, ntest)

        async def prepare(tx):
            vnstore.change_continue(tx, ntest, change)
            await vnstore.add(tx, ntest, expected, "title", "hypermove")
            await vnstore.change_apply(tx, ntest, change)

        await found.transactional(db, prepare)

        async def subject_query(tx):
            out = await vnstore.query(tx, ntest, (nstore.v("subject"), "title", "hypermove"))
            out = await found.all(out)
            return out

        out = await found.transactional(db, subject_query)

        assert out[0]["subject"] == expected

        # delete hypermove

        change = await found.transactional(db, vnstore.change_create, ntest)

        async def delete_hypermove(tx):
            vnstore.change_continue(tx, ntest, change)
            await vnstore.remove(tx, ntest, expected, "title", "hypermove")
            await vnstore.change_apply(tx, ntest, change)

        await found.transactional(db, delete_hypermove)

        out = await found.transactional(db, subject_query)

        assert not out


@pytest.mark.asyncio
async def test_vnstore_query():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])
    euid = uuid4()

    for i in range(10):
        change = await found.transactional(db, vnstore.change_create, ntest)
        expected = "Fractal queries for the win"

        async def prepare(tx):
            vnstore.change_continue(tx, ntest, change)
            await vnstore.add(tx, ntest, euid, "title", expected)
            await vnstore.add(tx, ntest, euid, "slug", "fractal-queries")
            await vnstore.add(
                tx,
                ntest,
                euid,
                "body",
                "fractal architecture help ease cognitive performance",
            )
            uid = uuid4()
            await vnstore.add(tx, ntest, uid, "title", "A case for inspecting values at runtime")
            await vnstore.add(tx, ntest, uid, "slug", "runtime-inspection")
            await vnstore.add(
                tx,
                ntest,
                uid,
                "body",
                "Runtime inspection help just-in-time user defined compilation",
            )
            await vnstore.change_apply(tx, ntest, change)

        await found.transactional(db, prepare)

        async def query_title_by_slug(tx):
            out = await vnstore.query(
                tx,
                ntest,
                (nstore.v("subject"), "slug", "fractal-queries"),
                (nstore.v("subject"), "title", nstore.v("title")),
            )
            out = await found.all(out)
            return out

        change = await found.transactional(db, vnstore.change_create, ntest)

        async def delete_expected(tx):
            vnstore.change_continue(tx, ntest, change)
            await vnstore.remove(tx, ntest, euid, "title", expected)
            await vnstore.change_apply(tx, ntest, change)

        await found.transactional(db, delete_expected)

        out = await found.transactional(db, query_title_by_slug)

        assert not out


@pytest.mark.asyncio
async def test_vnstore_change_list():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    c1 = await found.transactional(db, vnstore.change_create, ntest)
    c2 = await found.transactional(db, vnstore.change_create, ntest)

    changes = await found.transactional(db, vnstore.change_list, ntest)
    uids = [c["uid"] for c in changes]
    assert c1 in uids
    assert c2 in uids


@pytest.mark.asyncio
async def test_vnstore_change_message():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    changeid = await found.transactional(db, vnstore.change_create, ntest)

    async def set_msg(tx):
        await vnstore.change_message(tx, ntest, changeid, "hello world")

    await found.transactional(db, set_msg)

    out = await found.transactional(db, vnstore.change_get, ntest, changeid)
    assert out["message"] == "hello world"


@pytest.mark.asyncio
async def test_vnstore_change_changes():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    changeid = await found.transactional(db, vnstore.change_create, ntest)

    async def do_add(tx):
        vnstore.change_continue(tx, ntest, changeid)
        await vnstore.add(tx, ntest, "subj1", "key1", "val1")
        await vnstore.add(tx, ntest, "subj2", "key2", "val2")

    await found.transactional(db, do_add)

    out = await found.transactional(db, vnstore.change_changes, ntest, changeid)
    assert len(out) == 2


@pytest.mark.asyncio
async def test_vnstore_where():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    uid1 = uuid4()

    changeid = await found.transactional(db, vnstore.change_create, ntest)

    async def setup(tx):
        vnstore.change_continue(tx, ntest, changeid)
        await vnstore.add(tx, ntest, uid1, "title", "hello")
        await vnstore.add(tx, ntest, uid1, "tag", "world")
        await vnstore.change_apply(tx, ntest, changeid)

    await found.transactional(db, setup)

    async def do_query(tx):
        seed = vnstore.select(tx, ntest, v("uid"), "title", "hello")
        out = await found.all(vnstore.where(tx, ntest, seed, v("uid"), "tag", v("tag")))
        return out

    out = await found.transactional(db, do_query)
    assert len(out) == 1
    assert out[0]["tag"] == "world"


@pytest.mark.asyncio
async def test_vnstore_change_apply_twice():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    changeid = await found.transactional(db, vnstore.change_create, ntest)

    async def do_apply(tx):
        await vnstore.change_apply(tx, ntest, changeid)

    await found.transactional(db, do_apply)

    # Get significance after first apply
    out1 = await found.transactional(db, vnstore.change_get, ntest, changeid)
    sig1 = out1["significance"]
    assert sig1 is not None

    # Apply again — should be a no-op (significance unchanged)
    await found.transactional(db, do_apply)

    out2 = await found.transactional(db, vnstore.change_get, ntest, changeid)
    sig2 = out2["significance"]
    assert sig1 == sig2


@pytest.mark.asyncio
async def test_vnstore_change_get_nonexistent():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    out = await found.transactional(db, vnstore.change_get, ntest, uuid4())
    assert out is None


def test_vnstore_pk(capsys):
    result = vnstore.pk("a", "b", "c")
    assert result == "c"
    captured = capsys.readouterr()
    assert "('a', 'b', 'c')" in captured.out


@pytest.mark.asyncio
async def test_vnstore_get_not_implemented():
    with pytest.raises(NotImplementedError):
        await vnstore.get(None)


@pytest.mark.asyncio
async def test_vnstore_remove_nonexistent():
    db = await open()
    ntest = vnstore.make("test-name", [42], ["uid", "key", "value"])

    changeid = await found.transactional(db, vnstore.change_create, ntest)

    async def do_remove(tx):
        vnstore.change_continue(tx, ntest, changeid)
        result = await vnstore.remove(tx, ntest, "no-such-uid", "no-key", "no-val")
        return result

    out = await found.transactional(db, do_remove)
    assert out is False
