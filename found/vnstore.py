# Copyright (C) 2020-2023 Amirouche A. Boubekki
#
# https://github.com/amirouche/asyncio-foundationdb
#
import asyncio
import json
import os
import sys
from collections import namedtuple
from urllib.parse import parse_qs as parse_query_string
from uuid import UUID, uuid4

import fdb
import fdb.tuple
import pytest
from immutables import Map
from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger as log
from uuid_extensions import uuid7

import found
from found import ffw, nstore
from found.base import FoundException

_VNStore = namedtuple("VNStore", "name subspace items changes tuples names")


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
        len(items + ["changeid", "alive?"]),
    )
    vnstore = _VNStore(name, subspace, items, changes, tuples, items)
    return vnstore


async def change_create(tr, vnstore):
    tr.vars["vnstore_changeid"] = changeid = uuid4()
    # With significance as `None` the change is invisible to
    # VNStore.ask.
    await nstore.add(tr, vnstore.changes, changeid, "type", "change")
    await nstore.add(tr, vnstore.changes, changeid, "significance", None)
    await nstore.add(tr, vnstore.changes, changeid, "message", None)
    return changeid


async def change_list(tr, vnstore):
    out = []
    async for binding in nstore.query(
        tr, vnstore.changes, (nstore.var("uid"), "type", "change")
    ):
        out.append(await change_get(tr, vnstore, binding.get("uid")))
    return out


async def change_get(tr, vnstore, changeid):
    out = dict()
    async for binding in nstore.query(
        tr, vnstore.changes, (changeid, nstore.var("key"), nstore.var("value"))
    ):
        out[binding["key"]] = binding["value"]
    if out:
        out["uid"] = changeid
        return out
    else:
        return None


def change_continue(tr, vnstore, changeid):
    tr.vars["_vnstore_changeid"] = changeid


async def change_message(tr, vnstore, changeid, message):
    # Remove existing message if any
    async for binding in nstore.query(
        tr, vnstore.changes, (changeid, "message", nstore.var("message"))
    ):
        await nstore.remove(
            tr, vnstore.changes, changeid, "message", binding["message"]
        )
    await nstore.add(tr, vnstore.changes, changeid, "message", message)


async def change_changes(tr, vnstore, changeid):
    out = []
    pattern = [nstore.v(x) for x in vnstore.names]
    pattern += [changeid, nstore.v("alive?")]
    out = await found.all(nstore.query(tr, vnstore.tuples, pattern))
    return out


def pk(*args):
    print(args)
    return args[-1]


async def change_apply(tr, vnstore, changeid):
    # apply change by settings a verionstamp
    value = await nstore.get(tr, vnstore.changes, changeid, "significance", None)
    # It was already applied
    if value is None:
        log.warning('Trying to apply an already applied change: {}', changeid)
        return
    await nstore.remove(tr, vnstore.changes, changeid, "significance", None)
    significance = uuid7()
    await nstore.add(tr, vnstore.changes, changeid, "significance", significance)


async def ask(tr, vnstore, *items):
    assert len(items) == len(vnstore.items), "Incorrect count of ITEMS"
    # Complexity is O(n), where n is the number of times the exact
    # same ITEMS were added and deleted.  In pratice, n=0, n=1 or
    # n=2, and of course it always possible that it is more...
    items = list(items)
    items.append(nstore.v("changeid"))
    items.append(nstore.v("alive?"))
    bindings = nstore.query(tr, vnstore.tuples, items)
    ok = False
    # TODO: use pipelining, and use asyncio.gather the block 'for
    # binding in bindings';

    # smallest versoinstamp
    significance_max = UUID(int=0)
    async for binding in bindings:
        changeid = binding["changeid"]
        is_alive = binding["alive?"]
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
    items = list(items) + [tr.vars["_vnstore_changeid"], True]
    await nstore.add(tr, vnstore.tuples, *items, value=value)
    return True


async def remove(tr, vnstore, *items):
    assert len(items) == len(vnstore.items)
    if not await ask(tr, vnstore, *items):
        # ITEMS does not exists, nothing to do.
        return False
    # Delete it
    items = list(items) + [tr.vars["_vnstore_changeid"], False]
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
    pattern = list(pattern) + [nstore.v("changeid"), nstore.v("alive?")]
    bindings = nstore.select(tr, vnstore.tuples, *pattern, seed=seed)
    async for binding in bindings:
        if not binding["alive?"]:
            # The associated tuple is dead, so the bindings are
            # not valid in all cases.
            continue

        x = tuple(bind(query, binding))
        alive = await ask(tr, vnstore, *x)
        if not alive:
            continue

        binding = binding.delete("changeid")
        binding = binding.delete("alive?")
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


async def _test_open():
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
    db = await _test_open()
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
    db = await _test_open()
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
            return out

        change = await found.transactional(db, change_create, ntest)

        async def delete_expected(tx):
            change_continue(tx, ntest, change)
            await remove(tx, ntest, euid, "title", expected)
            await change_apply(tx, ntest, change)

        await found.transactional(db, delete_expected)

        out = await found.transactional(db, query_title_by_slug)

        assert not out


# Server

CACHE = dict()


async def jinja(template, context):
    template = await asyncio.to_thread(CACHE["jinja"].get_template, template)
    out = template.render(**context)
    return out


async def reply_bad_request(send, message):
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [
                (b"content-type", b"text/html"),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": message.encode("utf8"),
        }
    )


async def read_body(receive):
    """
    Read and return the entire body from an incoming ASGI message.
    """
    body = b""
    more_body = True

    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)

    return body


async def reply_not_found(send):
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"text/html"),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"Not found",
        }
    )


async def reply_html(send, html):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/html"),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": html.encode("utf8"),
        }
    )


async def reply_redirect(send, path):
    await send(
        {
            "type": "http.response.start",
            "status": 303,
            "headers": [
                (b"content-type", b"text/html"),
                (b"location", path.encode("utf8")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": "Redirect to: {}".format(path).encode("utf8"),
        }
    )


def fromstring(value):
    value = value.strip()
    if value == "_":
        return uuid4()
    if value == "#none":
        return None
    if value == "#true":
        return True
    if value == "#false":
        return False
    if value.startswith("#u"):
        return UUID(hex=value[2:])
    if value.startswith("#i"):
        return int(value[2:])
    if value.startswith("#f"):
        return float(value[2:])
    return value


def tostring(value):
    if value is None:
        return "<code>#none</code>"
    if value is True:
        return "<code>#true</code>"
    if value is False:
        return "<code>#false</code>"
    if isinstance(value, UUID):
        return "<code>#u{}</code>".format(value.hex.upper())
    if isinstance(value, int):
        return "<code>#i{}</code>".format(value)
    if isinstance(value, float):
        return "<code>#f{}</code>".format(value)
    if isinstance(value, str):
        return value
    raise NotImplementedError(value)

async def server(scope, receive, send):
    log.debug("ASGI scope: {}", scope)

    if scope["type"] == "lifespan":
        env = Environment(
            loader=PackageLoader("found"),
            autoescape=select_autoescape(),
        )
        CACHE["jinja"] = env
        CACHE["database"] = await found.open()
        CACHE["store"] = make(
            "found.vnstore:server", ["found.vnstore:server"], ["uid", "key", "value"]
        )
        log.debug("Application server lifespan init: done.")
        return

    if scope["type"] == "websocket":
        log.warning("websocket connection rejected")
        return

    path = scope["path"]
    method = scope["method"]

    log.debug("Trying to match: {}", [method, path])

    # Do not use match to support old CPython.
    # TODO: consider pampy.
    
    if path == "/" and method == "GET":
        html = await jinja("index.html", dict())
        await reply_html(send, html)
        return

    if path == "/history/" and method == "GET":
        changes = await found.transactional(
            CACHE["database"], change_list, CACHE["store"]
        )
        html = await jinja("history-list.html", dict(changes=changes))
        await reply_html(send, html)
        return

    if path == "/history/change/" and method == "GET":
        html = await jinja("history-change.html", dict())
        await reply_html(send, html)
        return

    if path == "/history/change/" and method == "POST":
        body = await read_body(receive)
        body = body.decode("utf8")
        try:
            description = parse_query_string(body)["description"][0]
        except KeyError:
            await reply_bad_request(send, "need a description")
            return

        description = description.strip()

        if description == "" or len(description) < 10:
            await reply_bad_request(send, "description is too short")
            return

        async def do(tr):
            uid = await change_create(tr, CACHE["store"])
            await change_message(tr, CACHE["store"], uid, description)
            return uid

        change = await found.transactional(CACHE["database"], do)

        await reply_redirect(send, "/history/u/{}/".format(change.hex))
        return

    components = path.split("/")

    if path.startswith("/history/u/") and len(components) == 5 and method == "GET":
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        changes = await found.transactional(
            CACHE["database"], change_changes, CACHE["store"], change
        )
        out["changes"] = changes
        out["tostring"] = tostring
        html = await jinja("history-detail.html", out)
        await reply_html(send, html)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "add"
        and len(components) == 6
        and method == "GET"
    ):
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        changes = await found.transactional(
            CACHE["database"], change_changes, CACHE["store"], change
        )
        out["changes"] = changes
        out["tostring"] = tostring

        html = await jinja("history-detail-add.html", out)
        await reply_html(send, html)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "add"
        and len(components) == 6
        and method == "POST"
    ):
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        body = await read_body(receive)
        body = body.decode("utf8")

        try:
            body = parse_query_string(body)
        except Exception:
            await reply_bad_request(send, "Invalid form format")
            return

        try:
            uid = fromstring(body["uid"][0])
            key = fromstring(body["key"][0])
            value = fromstring(body["value"][0])
        except Exception:
            msg = "Missing, or invalid one of: uid, key, or value"
            log.exception(msg)
            await reply_bad_request(send, msg)
            return

        async def do(tr):
            out = await change_get(tr, CACHE["store"], change)
            if out is None:
                return False
            change_continue(tr, CACHE["store"], change)
            await add(tr, CACHE["store"], uid, key, value)
            return True

        out = await found.transactional(CACHE["database"], do)
        if not out:
            await reply_bad_request(send, "Invalid change identifier.")
            return

        await reply_redirect(send, "/history/u/{}/".format(change.hex))
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "remove"
        and len(components) == 6
        and method == "GET"
    ):
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        changes = await found.transactional(
            CACHE["database"], change_changes, CACHE["store"], change
        )
        out["changes"] = changes
        out["tostring"] = tostring

        html = await jinja("history-detail-remove.html", out)
        await reply_html(send, html)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "remove"
        and len(components) == 6
        and method == "POST"
    ):
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        body = await read_body(receive)
        body = body.decode("utf8")

        try:
            body = parse_query_string(body)
        except Exception:
            await reply_bad_request(send, "Invalid form format")
            return

        try:
            uid = fromstring(body["uid"][0])
            key = fromstring(body["key"][0])
            value = fromstring(body["value"][0])
        except Exception:
            msg = "Missing, or invalid one of: uid, key, or value"
            log.exception(msg)
            await reply_bad_request(send, msg)
            return

        async def do(tr):
            out = await change_get(tr, CACHE["store"], change)
            if out is None:
                return False
            change_continue(tr, CACHE["store"], change)
            await remove(tr, CACHE["store"], uid, key, value)
            return True

        out = await found.transactional(CACHE["database"], do)
        if not out:
            await reply_bad_request(send, "Invalid change identifier.")
            return

        await reply_redirect(send, "/history/u/{}/".format(change.hex))
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "apply"
        and len(components) == 6
        and method == "GET"
    ):
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        changes = await found.transactional(
            CACHE["database"], change_changes, CACHE["store"], change
        )
        out["changes"] = changes
        out["tostring"] = tostring

        html = await jinja("history-detail-apply.html", out)
        await reply_html(send, html)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "apply"
        and len(components) == 6
        and method == "POST"
    ):
        change = components[3]
        if not len(change) == 32:
            await reply_bad_request(send, "Invalid change: {}".format(change))
            return

        change = UUID(hex=change)
        out = await found.transactional(
            CACHE["database"], change_get, CACHE["store"], change
        )
        if not out:
            await reply_bad_request(send, "No such change: {}".format(change.hex))
            return

        await found.transactional(CACHE["database"], change_apply, CACHE["store"], change)

        await reply_redirect(send, "/history/u/{}/".format(change.hex))
        return
    if path == "/navigate/" and method == "GET":
        body = scope['query_string'].decode("utf8")
        try:
            body = parse_query_string(body)
        except Exception:
            await reply_bad_request(send, "Invalid form format")
            return

        uid = body.get("uid", [''])[0]
        key = body.get("key", [''])[0]
        value = body.get("value", [''])[0]
        
        try:
            uidx = fromstring(uid)
            keyx = fromstring(key)
            valuex = fromstring(value)
        except Exception:
            msg = "Invalid query, one of: uid, key, or value"
            log.exception(msg)
            await reply_bad_request(send, msg)
            return

        async def do(tx, uid, key, value):
            out = await query(
                tx,
                CACHE['store'],
                (uid, key, value)
            )
            out = await found.all(found.limit(out, 42))
            return out

        if uidx == '':
            uidx = nstore.var('uid')
        if keyx == '':
            keyx = nstore.var('key')
        if valuex == '':
            valuex = nstore.var('value')
        
        out = await found.transactional(CACHE['database'], do, uidx, keyx, valuex)
        html = await jinja("navigate.html", dict(changes=out, uid=uid, key=key, value=value, tostring=tostring, isinstance=isinstance, UUID=UUID))
        await reply_html(send, html)
        return
    
    await not_found(send)


async def not_found(send):
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"text/html"),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"Not found",
        }
    )
