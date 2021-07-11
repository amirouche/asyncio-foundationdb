import asyncio
from uuid import uuid4

import pytest
from fdb.tuple import SingleFloat

import found
import found.base


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
        found.clear_range(tx, b"", b"\xff")

    await found.transactional(db, purge)

    return db


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
        found.set(tx, b"test", b"test")
        out = await found.get(tx, b"test")
        # check
        assert out == b"test"

    # exec
    await found.transactional(db, test1)


async def aiolist(aiogenerator):
    out = []
    async for item in aiogenerator:
        out.append(item)
    return out


@pytest.mark.asyncio
async def test_query():
    # prepare
    db = await open()

    async def set(tx):
        for number in range(10):
            found.set(tx, found.pack((number,)), found.pack((str(number),)))

    await found.transactional(db, set)

    async def query(tx):
        out = found.query(tx, found.pack((1,)), found.pack((8,)))
        out = await aiolist(out)
        return out

    out = await found.transactional(db, query)
    for (key, value), index in zip(out, range(10)[1:-1]):
        assert found.unpack(key)[0] == index
        assert found.unpack(value)[0] == str(index)


@pytest.mark.asyncio
async def test_next_prefix():
    # prepare
    db = await open()

    prefix_zero = b"\x00"
    prefix_one = b"\x01"

    # exec
    async def test(tx):
        found.set(tx, prefix_zero + b"\x01", found.pack((1,)))
        found.set(tx, prefix_zero + b"\x02", found.pack((2,)))
        found.set(tx, prefix_zero + b"\x03", found.pack((3,)))
        found.set(tx, prefix_one + b"\x42", found.pack((42,)))

    await found.transactional(db, test)

    # check
    async def query0(tx):
        everything = found.query(tx, b'', b'\xFF')
        everything = await aiolist(everything)
        assert len(everything) == 4

    await found.transactional(db, query0)

    # check
    async def query1(tx):
        everything = found.query(tx, prefix_zero, found.next_prefix(prefix_zero))
        everything = await aiolist(everything)
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


# Ntore tests


# @pytest.mark.asyncio
# async def test_nstore_empty():
#     db = await open()
#     from found.nstore import NStore

#     nstore = NStore("test-name", [42], ("subject", "predicate", "object"))


# @pytest.mark.asyncio
# async def test_simple_single_item_db_subject_lookup():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     expected = uuid4()
#     await foundiplestore.add(db, expected, "title", "hyper.dev")

#     @found.foundansactional
#     async def query(found):
#         out = await aiolist(foundiplestore.select(found, var("subject"), "title", "hyper.dev"))
#         return out
#     out = await query(db)

#     out = out[0]["subject"]
#     assert out == expected


# @pytest.mark.asyncio
# async def test_ask_rm_and_ask():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     expected = uuid4()
#     await foundiplestore.add(db, expected, "title", "hyper.dev")
#     out = await foundiplestore.ask(db, expected, "title", "hyper.dev")
#     assert out
#     await foundiplestore.remove(db, expected, "title", "hyper.dev")
#     out = await foundiplestore.ask(db, expected, "title", "hyper.dev")
#     assert not out


# @pytest.mark.asyncio
# async def test_simple_multiple_items_db_subject_lookup():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     expected = uuid4()
#     await foundiplestore.add(db, expected, "title", "hyper.dev")
#     await foundiplestore.add(db, uuid4(), "title", "blog.copernic.com")
#     await foundiplestore.add(db, uuid4(), "title", "julien.danjou.info")

#     @found.foundansactional
#     async def query(found):
#         out = await aiolist(foundiplestore.select(found, var("subject"), "title", "hyper.dev"))
#         return out

#     out = await query(db)
#     out = out[0]["subject"]
#     assert out == expected


# @pytest.mark.asyncio
# async def test_complex():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     hyperdev = uuid4()
#     await foundiplestore.add(db, hyperdev, "title", "hyper.dev")
#     await foundiplestore.add(db, hyperdev, "keyword", "scheme")
#     await foundiplestore.add(db, hyperdev, "keyword", "hacker")
#     copernic = uuid4()
#     await foundiplestore.add(db, copernic, "title", "blog.copernic.com")
#     await foundiplestore.add(db, copernic, "keyword", "corporate")
#     julien = uuid4()
#     await foundiplestore.add(db, julien, "title", "julien.danjou.info")
#     await foundiplestore.add(db, julien, "keyword", "python")
#     await foundiplestore.add(db, julien, "keyword", "hacker")

#     @found.foundansactional
#     async def query(found):
#         seed = foundiplestore.select(found, var("identifier"), "keyword", "hacker")
#         out = await aiolist(foundiplestore.where(
#             found, seed, var("identifier"), "title", var("blog")
#         ))
#         return out

#     out = await query(db)
#     out = sorted([x["blog"] for x in out])
#     assert out == ["hyper.dev", "julien.danjou.info"]


# @pytest.mark.asyncio
# async def test_seed_subject_variable():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     hyperdev = uuid4()
#     await foundiplestore.add(db, hyperdev, "title", "hyper.dev")
#     await foundiplestore.add(db, hyperdev, "keyword", "scheme")
#     await foundiplestore.add(db, hyperdev, "keyword", "hacker")

#     copernic = uuid4()
#     await foundiplestore.add(db, copernic, "title", "copernic.space")
#     await foundiplestore.add(db, copernic, "keyword", "corporate")

#     hypersocial = uuid4()
#     await foundiplestore.add(db, hypersocial, "title", "hypersocial.space")
#     await foundiplestore.add(db, hypersocial, "keyword", "python")
#     await foundiplestore.add(db, hypersocial, "keyword", "hacker")

#     @found.foundansactional
#     async def query(found):
#         out = await aiolist(foundiplestore.select(found, var("subject"), "keyword", "corporate"))
#         return out

#     out = await query(db)
#     out = out[0]["subject"]

#     assert out == copernic


# @pytest.mark.asyncio
# async def test_seed_subject_lookup():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     hyperdev = uuid4()
#     await foundiplestore.add(db, hyperdev, "title", "hyper.dev")
#     await foundiplestore.add(db, hyperdev, "keyword", "scheme")
#     await foundiplestore.add(db, hyperdev, "keyword", "hacker")

#     copernic = uuid4()
#     await foundiplestore.add(db, copernic, "title", "blog.copernic.com")
#     await foundiplestore.add(db, copernic, "keyword", "corporate")

#     hypersocial = uuid4()
#     await foundiplestore.add(db, hypersocial, "title", "hypersocial.space")
#     await foundiplestore.add(db, hypersocial, "keyword", "python")
#     await foundiplestore.add(db, hypersocial, "keyword", "hacker")

#     @found.foundansactional
#     async def query(found):
#         out = await aiolist(foundiplestore.select(found, copernic, var("key"), var("value")))
#         return out

#     out = await query(db)
#     out = [dict(x) for x in out]

#     expected = [
#         {"key": "keyword", "value": "corporate"},
#         {"key": "title", "value": "blog.copernic.com"},
#     ]
#     assert out == expected


# @pytest.mark.asyncio
# async def test_seed_object_variable():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     hyperdev = uuid4()
#     await foundiplestore.add(db, hyperdev, "title", "hyper.dev")
#     await foundiplestore.add(db, hyperdev, "keyword", "scheme")
#     await foundiplestore.add(db, hyperdev, "keyword", "hacker")

#     copernic = uuid4()
#     await foundiplestore.add(db, copernic, "title", "blog.copernic.com")
#     await foundiplestore.add(db, copernic, "keyword", "corporate")

#     hypersocial = uuid4()
#     await foundiplestore.add(db, hypersocial, "title", "hypersocial.space")
#     await foundiplestore.add(db, hypersocial, "keyword", "python")
#     await foundiplestore.add(db, hypersocial, "keyword", "hacker")

#     @found.foundansactional
#     async def query(found):
#         out = await aiolist(foundiplestore.select(found, hyperdev, "title", var("title")))
#         return out

#     out = await query(db)
#     out = out[0]["title"]
#     assert out == "hyper.dev"


# @pytest.mark.asyncio
# async def test_subject_variable():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     # prepare
#     hyperdev = uuid4()
#     await foundiplestore.add(db, hyperdev, "title", "hyper.dev")
#     await foundiplestore.add(db, hyperdev, "keyword", "scheme")
#     await foundiplestore.add(db, hyperdev, "keyword", "hacker")
#     post1 = uuid4()
#     await foundiplestore.add(db, post1, "blog", hyperdev)
#     await foundiplestore.add(db, post1, "title", "hoply is awesome")
#     post2 = uuid4()
#     await foundiplestore.add(db, post2, "blog", hyperdev)
#     await foundiplestore.add(db, post2, "title", "hoply foundiple store")

#     # exec, fetch all blog title from hyper.dev

#     @found.foundansactional
#     async def query(found):
#         query = foundiplestore.select(found, var("blog"), "title", "hyper.dev")
#         query = foundiplestore.where(found, query, var("post"), "blog", var("blog"))
#         out = await aiolist(foundiplestore.where(found, query, var("post"), "title", var("title")))
#         return out

#     out = await query(db)
#     out = sorted([x["title"] for x in out])
#     assert out == ["hoply is awesome", "hoply foundiple store"]


# @pytest.mark.asyncio
# async def test_query():
#     db = await open()
#     from found.nstore import NStore
#     from found.nstore import var

#     foundiplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

#     # prepare
#     hyperdev = uuid4()
#     await foundiplestore.add(db, hyperdev, "title", "hyper.dev")
#     await foundiplestore.add(db, hyperdev, "keyword", "scheme")
#     await foundiplestore.add(db, hyperdev, "keyword", "hacker")
#     post1 = uuid4()
#     await foundiplestore.add(db, post1, "blog", hyperdev)
#     await foundiplestore.add(db, post1, "title", "hoply is awesome")
#     post2 = uuid4()
#     await foundiplestore.add(db, post2, "blog", hyperdev)
#     await foundiplestore.add(db, post2, "title", "hoply foundiple store")

#     # exec, fetch all blog title from hyper.dev

#     @found.foundansactional
#     async def query(found):
#         query = [
#             [var("blog"), "title", "hyper.dev"],
#             [var("post"), "blog", var("blog")],
#             [var("post"), "title", var("title")],
#         ]
#         out = await aiolist(foundiplestore.query(found, *query))
#         return out

#     out = await query(db)
#     out = sorted([x["title"] for x in out])
#     assert out == ["hoply is awesome", "hoply foundiple store"]
