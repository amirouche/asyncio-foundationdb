import asyncio
import logging
import pytest
from uuid import uuid4

from fdb.tuple import SingleFloat

import found
from found import base


found.api_version(630)


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
    base._loop = loop

    db = await found.open()
    # clean database
    tr = db._create_transaction()
    tr.clear_range(b"", b"\xff")
    await tr._commit()

    return db


@pytest.mark.asyncio
async def test_get():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    out = await tr.get(b"test")
    # check
    assert out is None

    # exec
    tr.set(b"test", b"test")
    out = await tr.get(b"test")
    # check
    assert out == b"test"


async def aiolist(aiogenerator):
    out = []
    async for item in aiogenerator:
        out.append(item)
    return out


@pytest.mark.asyncio
async def test_range():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    for number in range(10):
        tr.set(found.pack((number,)), found.pack((str(number),)))
    await tr._commit()

    tr = db._create_transaction()
    out = tr.range(found.pack((1,)), found.pack((8,)))
    out = await aiolist(out)
    await tr._commit()

    # check
    assert out
    for (key, value), index in zip(out, range(10)[1:-1]):
        assert found.unpack(key)[0] == index
        assert found.unpack(value)[0] == str(index)


@pytest.mark.asyncio
async def test_strinc_range():
    # prepare
    db = await open()
    tr = db._create_transaction()

    # exec
    prefix_zero = b"\x00"
    tr.set(prefix_zero + b"\x01", found.pack((1,)))
    tr.set(prefix_zero + b"\x02", found.pack((2,)))
    tr.set(prefix_zero + b"\x03", found.pack((3,)))
    prefix_one = b"\x01"
    tr.set(prefix_one + b"\x42", found.pack((42,)))
    await tr._commit()

    # check
    tr = db._create_transaction()
    everything = tr.range(None, None)
    everything = await aiolist(everything)
    await tr._commit()
    assert len(everything) == 4

    # check
    tr = db._create_transaction()
    everything = tr.range(prefix_zero, found.strinc(prefix_zero))
    everything = await aiolist(everything)
    await tr._commit()
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_read_version():
    # prepare
    db = await open()

    # exec
    tr = db._create_transaction()
    out = await tr.read_version()
    await tr._commit()

    # check
    assert out


@pytest.mark.asyncio
async def test_startswith():
    # prepare
    db = await open()

    # exec
    tr = db._create_transaction()
    prefix_zero = b"\x00"
    tr.set(prefix_zero + b"\x01", found.pack((1,)))
    tr.set(prefix_zero + b"\x02", found.pack((2,)))
    tr.set(prefix_zero + b"\x03", found.pack((3,)))
    prefix_one = b"\x01"
    tr.set(prefix_one + b"\x42", found.pack((42,)))
    await tr._commit()

    # check
    tr = db._create_transaction()
    everything = tr.range(None, None)
    everything = await aiolist(everything)
    await tr._commit()
    assert len(everything) == 4

    # check
    tr = db._create_transaction()
    everything = tr.range_startswith(prefix_zero)
    everything = await aiolist(everything)
    await tr._commit()
    assert len(everything) == 3


@pytest.mark.asyncio
async def test_transactional():
    @found.transactional
    async def deep(tr):
        out = await tr.get(b"\x00")
        return out

    @found.transactional
    async def txn(tr):
        tr.set(b"\x00", b"\x00")
        out = await deep(tr)
        return out

    # check
    db = await open()
    out = await txn(db)

    # check
    assert out == b"\x00"


# Sparky tests


@pytest.mark.asyncio
async def test_nstore_empty():
    db = await open()
    from found.nstore import NStore

    nstore = NStore("test-name", [42], ("subject", "predicate", "object"))


@pytest.mark.asyncio
async def test_simple_single_item_db_subject_lookup():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    expected = uuid4()
    await triplestore.add(db, expected, "title", "hyper.dev")

    @found.transactional
    async def query(tr):
        out = await aiolist(triplestore.select(tr, var("subject"), "title", "hyper.dev"))
        return out
    out = await query(db)

    out = out[0]["subject"]
    assert out == expected


@pytest.mark.asyncio
async def test_ask_rm_and_ask():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    expected = uuid4()
    await triplestore.add(db, expected, "title", "hyper.dev")
    out = await triplestore.ask(db, expected, "title", "hyper.dev")
    assert out
    await triplestore.remove(db, expected, "title", "hyper.dev")
    out = await triplestore.ask(db, expected, "title", "hyper.dev")
    assert not out


@pytest.mark.asyncio
async def test_simple_multiple_items_db_subject_lookup():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    expected = uuid4()
    await triplestore.add(db, expected, "title", "hyper.dev")
    await triplestore.add(db, uuid4(), "title", "blog.copernic.com")
    await triplestore.add(db, uuid4(), "title", "julien.danjou.info")

    @found.transactional
    async def query(tr):
        out = await aiolist(triplestore.select(tr, var("subject"), "title", "hyper.dev"))
        return out

    out = await query(db)
    out = out[0]["subject"]
    assert out == expected


@pytest.mark.asyncio
async def test_complex():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")
    copernic = uuid4()
    await triplestore.add(db, copernic, "title", "blog.copernic.com")
    await triplestore.add(db, copernic, "keyword", "corporate")
    julien = uuid4()
    await triplestore.add(db, julien, "title", "julien.danjou.info")
    await triplestore.add(db, julien, "keyword", "python")
    await triplestore.add(db, julien, "keyword", "hacker")

    @found.transactional
    async def query(tr):
        seed = triplestore.select(tr, var("identifier"), "keyword", "hacker")
        out = await aiolist(triplestore.where(
            tr, seed, var("identifier"), "title", var("blog")
        ))
        return out

    out = await query(db)
    out = sorted([x["blog"] for x in out])
    assert out == ["hyper.dev", "julien.danjou.info"]


@pytest.mark.asyncio
async def test_seed_subject_variable():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")

    copernic = uuid4()
    await triplestore.add(db, copernic, "title", "copernic.space")
    await triplestore.add(db, copernic, "keyword", "corporate")

    hypersocial = uuid4()
    await triplestore.add(db, hypersocial, "title", "hypersocial.space")
    await triplestore.add(db, hypersocial, "keyword", "python")
    await triplestore.add(db, hypersocial, "keyword", "hacker")

    @found.transactional
    async def query(tr):
        out = await aiolist(triplestore.select(tr, var("subject"), "keyword", "corporate"))
        return out

    out = await query(db)
    out = out[0]["subject"]

    assert out == copernic


@pytest.mark.asyncio
async def test_seed_subject_lookup():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")

    copernic = uuid4()
    await triplestore.add(db, copernic, "title", "blog.copernic.com")
    await triplestore.add(db, copernic, "keyword", "corporate")

    hypersocial = uuid4()
    await triplestore.add(db, hypersocial, "title", "hypersocial.space")
    await triplestore.add(db, hypersocial, "keyword", "python")
    await triplestore.add(db, hypersocial, "keyword", "hacker")

    @found.transactional
    async def query(tr):
        out = await aiolist(triplestore.select(tr, copernic, var("key"), var("value")))
        return out

    out = await query(db)
    out = [dict(x) for x in out]

    expected = [
        {"key": "keyword", "value": "corporate"},
        {"key": "title", "value": "blog.copernic.com"},
    ]
    assert out == expected


@pytest.mark.asyncio
async def test_seed_object_variable():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")

    copernic = uuid4()
    await triplestore.add(db, copernic, "title", "blog.copernic.com")
    await triplestore.add(db, copernic, "keyword", "corporate")

    hypersocial = uuid4()
    await triplestore.add(db, hypersocial, "title", "hypersocial.space")
    await triplestore.add(db, hypersocial, "keyword", "python")
    await triplestore.add(db, hypersocial, "keyword", "hacker")

    @found.transactional
    async def query(tr):
        out = await aiolist(triplestore.select(tr, hyperdev, "title", var("title")))
        return out

    out = await query(db)
    out = out[0]["title"]
    assert out == "hyper.dev"


@pytest.mark.asyncio
async def test_subject_variable():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    # prepare
    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")
    post1 = uuid4()
    await triplestore.add(db, post1, "blog", hyperdev)
    await triplestore.add(db, post1, "title", "hoply is awesome")
    post2 = uuid4()
    await triplestore.add(db, post2, "blog", hyperdev)
    await triplestore.add(db, post2, "title", "hoply triple store")

    # exec, fetch all blog title from hyper.dev

    @found.transactional
    async def query(tr):
        query = triplestore.select(tr, var("blog"), "title", "hyper.dev")
        query = triplestore.where(tr, query, var("post"), "blog", var("blog"))
        out = await aiolist(triplestore.where(tr, query, var("post"), "title", var("title")))
        return out

    out = await query(db)
    out = sorted([x["title"] for x in out])
    assert out == ["hoply is awesome", "hoply triple store"]


@pytest.mark.asyncio
async def test_query():
    db = await open()
    from found.nstore import NStore
    from found.nstore import var

    triplestore = NStore("test-name", [42], ("subject", "predicate", "object"))

    # prepare
    hyperdev = uuid4()
    await triplestore.add(db, hyperdev, "title", "hyper.dev")
    await triplestore.add(db, hyperdev, "keyword", "scheme")
    await triplestore.add(db, hyperdev, "keyword", "hacker")
    post1 = uuid4()
    await triplestore.add(db, post1, "blog", hyperdev)
    await triplestore.add(db, post1, "title", "hoply is awesome")
    post2 = uuid4()
    await triplestore.add(db, post2, "blog", hyperdev)
    await triplestore.add(db, post2, "title", "hoply triple store")

    # exec, fetch all blog title from hyper.dev

    @found.transactional
    async def query(tr):
        query = [
            [var("blog"), "title", "hyper.dev"],
            [var("post"), "blog", var("blog")],
            [var("post"), "title", var("title")],
        ]
        out = await aiolist(triplestore.query(tr, *query))
        return out

    out = await query(db)
    out = sorted([x["title"] for x in out])
    assert out == ["hoply is awesome", "hoply triple store"]
