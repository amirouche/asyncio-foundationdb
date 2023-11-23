# Copyright (C) 2020-2023 Amirouche A. Boubekki
#
# https://github.com/amirouche/asyncio-foundationdb
#
import asyncio
from collections import namedtuple
from uuid import UUID, uuid4

import fdb
import fdb.tuple
import pytest
from immutables import Map
from uuid_extensions import uuid7

import found
from found import nstore
from found.base import FoundException

_VNStore = namedtuple("VNStore", "name subspace items changes tuples")


class VNStoreException(FoundException):
    pass


def make(name, subspace, items):
    assert isinstance(subspace, (tuple, list))
    assert isinstance(items, (tuple, list))
    name = name
    subspace = subspace
    items = list(items)
    # A change can have two key:
    #
    # - "message": that is a small description of the change
    #
    # - "significance": once the change is applied, it has an
    #    history significance VersionStamp that allows to order
    #    the changes.
    #
    changes = nstore.make(
        "{}-changes".format(name), subspace + ["changes"], len(("uid", "key", "value"))
    )
    # self.tuples contains the tuples associated with the change
    # identifier (changeid+alive?) store the change that created
    # or removed the tuple. `not alive?` is dead.
    tuples = nstore.make(
        "{}-tuples".format(name),
        subspace + ["tuples"],
        len(items + ["changeid+alive?"]),
    )
    vnstore = _VNStore(name, subspace, items, changes, tuples)
    return vnstore


async def change_create(tr, vnstore):
    tr.vars["vnstore_changeid"] = changeid = uuid4()
    # With significance as `None` the change is invisible to
    # VNStore.ask.
    await nstore.add(tr, vnstore.changes, changeid, "significance", None)
    await nstore.add(tr, vnstore.changes, changeid, "message", None)
    return changeid


def change_continue(tr, vnstore, changeid):
    tr.vars["_vnstore_changeid"] = changeid


async def change_message(tr, vnstore, changeid, message):
    # Remove existing message if any
    async for binding in nstore.query(
        tr, vnstore.changes, changeid, "message", nstore.var("message")
    ):
        nstore.remove(tr, vnstore.changes, changeid, "message", binding["message"])
    await nstore.add(tr, vnstore.changes, changeid, "message", message)


def pk(*args):
    print(args)
    return args[-1]


async def change_apply(tr, vnstore, changeid):
    # apply change by settings a verionstamp
    await nstore.remove(tr, vnstore.changes, changeid, "significance", None)
    significance = uuid7()
    await nstore.add(tr, vnstore.changes, changeid, "significance", significance)


async def ask(tr, vnstore, *items):
    assert len(items) == len(vnstore.items), "Incorrect count of ITEMS"
    # Complexity is O(n), where n is the number of times the exact
    # same ITEMS were added and deleted.  In pratice, n=0, n=1 or
    # n=2, and of course it always possible that it is more...
    items = list(items)
    items.append(nstore.v("changeid+alive?"))
    bindings = nstore.query(tr, vnstore.tuples, items)
    ok = False
    # TODO: use asyncio.gather insted the block for binding in bindings;
    # smallest versoinstamp is b'\x00' * 10
    significance_max = UUID(int=0)
    async for binding in bindings:
        changeid, is_alive = binding["changeid+alive?"]
        # TODO: Cache significance in the transaction
        significance = nstore.query(
            tr, vnstore.changes, (changeid, "significance", nstore.var("significance"))
        )
        significance = await found.all(significance)
        significance = significance[0]["significance"]
        if (significance is not None) and (significance > significance_max):
            significance_max = significance
            ok = is_alive
    return ok


async def get(tr, *items):
    # TODO: ask, but return the value
    raise NotImplementedError


async def add(tr, vnstore, *items, value=b""):
    # TODO: add support for the value
    assert len(items) == len(vnstore.items)
    assert tr.vars["_vnstore_changeid"]
    items = list(items) + [(tr.vars["_vnstore_changeid"], True)]
    await nstore.add(tr, vnstore.tuples, *items, value=value)
    return True


async def remove(tr, vnstore, *items):
    assert len(items) == len(vnstore.items)
    if not await ask(tr, vnstore, *items):
        # ITEMS does not exists, nothing to do.
        return False
    # Delete it
    items = list(items) + [(tr.vars["_vnstore_changeid"], False)]
    await nstore.add(tr, vnstore.tuples, *items)
    return True


async def select(tr, vnstore, *pattern, seed=Map()):  # seed is immutable
    """Yields bindings that match PATTERN"""
    assert len(pattern) == len(vnstore.items), "invalid item count"

    # TODO: validate that pattern does not have variables named
    # `alive?` or `changeid`.

    def bind(pattern, binding):
        for item in pattern:
            if isinstance(item, nstore.Variable):
                yield binding[item.name]
            else:
                yield item

    # The complexity really depends on the pattern.  A pattern
    # only made of variables will scan the whole database.  In
    # practice, the user will seldom do time traveling queries, so
    # it should rarely hit this code path.
    query = pattern
    pattern = list(pattern) + [nstore.v("changeid+alive?")]
    bindings = nstore.select(tr, vnstore.tuples, *pattern, seed=seed)
    async for binding in bindings:
        if not binding["changeid+alive?"][1]:
            # The associated tuple is dead, so the bindings are
            # not valid in all cases.
            continue

        x = tuple(bind(query, binding))
        alive = await ask(tr, vnstore, *x)
        if not alive:
            continue

        binding = binding.delete("changeid+alive?")
        yield binding


async def where(tr, vnstore, iterator, *pattern):
    assert len(pattern) == len(vnstore.items), "invalid item count"

    async for bindings in iterator:
        # bind PATTERN against BINDINGS
        bound = []
        for item in pattern:
            # if ITEM is variable try to bind
            if isinstance(item, v):
                try:
                    value = bindings[item.name]
                except KeyError:
                    # no bindings
                    bound.append(item)
                else:
                    # pick the value from bindings
                    bound.append(value)
            else:
                # otherwise keep item as is
                bound.append(item)
        # hey!
        async for item in select(tr, vnstore, *bound, seed=bindings):
            yield item


async def query(tx, nstore, pattern, *patterns):
    out = select(tx, nstore, *pattern)
    for pattern in patterns:
        out = where(tx, nstore, out, *pattern)
    return out


async def open():
    # XXX: hack around the fact that the loop is cached in found
    loop = asyncio.get_event_loop()
    found.base._loop = loop

    db = await found.open()

    async def purge(tx):
        await found.clear(tx, b"", b"\xff")

    await found.transactional(db, purge)

    return db


v = nstore.v


@pytest.mark.asyncio
async def test_noop():
    assert True


@pytest.mark.asyncio
async def test_empty():
    ntest = make("test-name", ["subspace-42"], ["uid", "key", "value"])
    assert ntest


@pytest.mark.asyncio
async def test_query_zero():
    db = await open()
    ntest = make("test-name", [42], ["uid", "key", "value"])

    for i in range(10):
        expected = uuid4()

        async def subject_query(tx):
            out = await query(tx, ntest, (nstore.v("subject"), "title", "hypermove.fr"))
            out = await found.all(out)
            return out

        out = await found.transactional(db, subject_query)

        assert not out

        change = await found.transactional(db, change_create, ntest)

        async def prepare(tx):
            change_continue(tx, ntest, change)
            await add(tx, ntest, expected, "title", "hypermove")
            await change_apply(tx, ntest, change)

        await found.transactional(db, prepare)

        async def subject_query(tx):
            out = await query(tx, ntest, (nstore.v("subject"), "title", "hypermove"))
            out = await found.all(out)
            return out

        out = await found.transactional(db, subject_query)

        assert out[0]["subject"] == expected

        # delete hypermove

        change = await found.transactional(db, change_create, ntest)

        async def delete_hypermove(tx):
            change_continue(tx, ntest, change)
            await remove(tx, ntest, expected, "title", "hypermove")
            await change_apply(tx, ntest, change)

        await found.transactional(db, delete_hypermove)

        out = await found.transactional(db, subject_query)

        assert not out


@pytest.mark.asyncio
async def test_query():
    db = await open()
    ntest = make("test-name", [42], ["uid", "key", "value"])
    euid = uuid4()

    for i in range(10):
        change = await found.transactional(db, change_create, ntest)
        expected = "Fractal queries for the win"

        async def prepare(tx):
            change_continue(tx, ntest, change)
            await add(tx, ntest, euid, "title", expected)
            await add(tx, ntest, euid, "slug", "fractal-queries")
            await add(
                tx,
                ntest,
                euid,
                "body",
                "fractal architecture help ease cognitive performance",
            )
            uid = uuid4()
            await add(
                tx, ntest, uid, "title", "A case for inspecting values at runtime"
            )
            await add(tx, ntest, uid, "slug", "runtime-inspection")
            await add(
                tx,
                ntest,
                uid,
                "body",
                "Runtime inspection help just-in-time user defined compilation",
            )
            await change_apply(tx, ntest, change)

        await found.transactional(db, prepare)

        async def query_title_by_slug(tx):
            out = await query(
                tx,
                ntest,
                (nstore.v("subject"), "slug", "fractal-queries"),
                (nstore.v("subject"), "title", nstore.v("title")),
            )
            out = await found.all(out)
            out = out

            return out

        change = await found.transactional(db, change_create, ntest)

        async def delete_expected(tx):
            change_continue(tx, ntest, change)
            await remove(tx, ntest, euid, "title", expected)
            await change_apply(tx, ntest, change)

        await found.transactional(db, delete_expected)

        out = await found.transactional(db, query_title_by_slug)

        assert not out
