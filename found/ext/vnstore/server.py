"""ASGI server for the versioned N-tuple store."""

# Copyright (C) 2020-2023 Amirouche A. Boubekki
#
# https://github.com/amirouche/asyncio-foundationdb
#
import asyncio
from urllib.parse import parse_qs as parse_query_string
from uuid import UUID

from jinja2 import Environment, PackageLoader, select_autoescape
from loguru import logger as log

import found
from found.ext import nstore
from found.ext.vnstore import (
    add,
    change_apply,
    change_changes,
    change_continue,
    change_create,
    change_get,
    change_list,
    change_message,
    make,
    query,
    remove,
)


def fromstring(value):
    value = value.strip()
    if value == "_":
        from uuid import uuid4

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


async def jinja(state, template, context):
    template = await asyncio.to_thread(state["jinja"].get_template, template)
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
    """Read and return the entire body from an incoming ASGI message."""
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


async def with_change(send, state, change_hex, fn):
    """Validate change_hex, look up the change, then call fn(change, out)."""
    if len(change_hex) != 32:
        await reply_bad_request(send, "Invalid change: {}".format(change_hex))
        return
    change = UUID(hex=change_hex)
    out = await found.transactional(state["database"], change_get, state["store"], change)
    if not out:
        await reply_bad_request(send, "No such change: {}".format(change.hex))
        return
    await fn(change, out)


async def server(scope, receive, send):
    log.debug("ASGI scope: {}", scope)

    if scope["type"] == "lifespan":
        message = await receive()  # lifespan.startup
        assert message["type"] == "lifespan.startup"
        state = scope["state"]
        state["jinja"] = Environment(
            loader=PackageLoader("found.ext.vnstore"),
            autoescape=select_autoescape(),
        )
        state["database"] = await found.open()
        state["store"] = make(
            "found.vnstore:server", ["found.vnstore:server"], ["uid", "key", "value"]
        )
        log.debug("Application server lifespan init: done.")
        await send({"type": "lifespan.startup.complete"})
        await receive()  # lifespan.shutdown
        await send({"type": "lifespan.shutdown.complete"})
        return

    if scope["type"] == "websocket":
        log.warning("websocket connection rejected")
        return

    path = scope["path"]
    method = scope["method"]
    state = scope["state"]

    log.debug("Trying to match: {}", [method, path])

    # Do not use match to support old CPython.
    # TODO: consider pampy.

    if path == "/" and method == "GET":
        html = await jinja(state, "index.html", dict())
        await reply_html(send, html)
        return

    if path == "/history/" and method == "GET":
        changes = await found.transactional(state["database"], change_list, state["store"])
        html = await jinja(state, "history-list.html", dict(changes=changes))
        await reply_html(send, html)
        return

    if path == "/history/change/" and method == "GET":
        html = await jinja(state, "history-change.html", dict())
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
            uid = await change_create(tr, state["store"])
            await change_message(tr, state["store"], uid, description)
            return uid

        change = await found.transactional(state["database"], do)

        await reply_redirect(send, "/history/u/{}/".format(change.hex))
        return

    components = path.split("/")

    if path.startswith("/history/u/") and len(components) == 5 and method == "GET":

        async def handle_detail(change, out):
            changes = await found.transactional(
                state["database"], change_changes, state["store"], change
            )
            out["changes"] = changes
            out["tostring"] = tostring
            html = await jinja(state, "history-detail.html", out)
            await reply_html(send, html)

        await with_change(send, state, components[3], handle_detail)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "add"
        and len(components) == 6
        and method == "GET"
    ):

        async def handle_add_get(change, out):
            changes = await found.transactional(
                state["database"], change_changes, state["store"], change
            )
            out["changes"] = changes
            out["tostring"] = tostring
            html = await jinja(state, "history-detail-add.html", out)
            await reply_html(send, html)

        await with_change(send, state, components[3], handle_add_get)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "add"
        and len(components) == 6
        and method == "POST"
    ):
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

        async def handle_add_post(change, out):
            async def do(tr):
                inner_out = await change_get(tr, state["store"], change)
                if inner_out is None:
                    return False
                change_continue(tr, state["store"], change)
                await add(tr, state["store"], uid, key, value)
                return True

            result = await found.transactional(state["database"], do)
            if not result:
                await reply_bad_request(send, "Invalid change identifier.")
                return
            await reply_redirect(send, "/history/u/{}/".format(change.hex))

        await with_change(send, state, components[3], handle_add_post)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "remove"
        and len(components) == 6
        and method == "GET"
    ):

        async def handle_remove_get(change, out):
            changes = await found.transactional(
                state["database"], change_changes, state["store"], change
            )
            out["changes"] = changes
            out["tostring"] = tostring
            html = await jinja(state, "history-detail-remove.html", out)
            await reply_html(send, html)

        await with_change(send, state, components[3], handle_remove_get)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "remove"
        and len(components) == 6
        and method == "POST"
    ):
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

        async def handle_remove_post(change, out):
            async def do(tr):
                inner_out = await change_get(tr, state["store"], change)
                if inner_out is None:
                    return False
                change_continue(tr, state["store"], change)
                await remove(tr, state["store"], uid, key, value)
                return True

            result = await found.transactional(state["database"], do)
            if not result:
                await reply_bad_request(send, "Invalid change identifier.")
                return
            await reply_redirect(send, "/history/u/{}/".format(change.hex))

        await with_change(send, state, components[3], handle_remove_post)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "apply"
        and len(components) == 6
        and method == "GET"
    ):

        async def handle_apply_get(change, out):
            changes = await found.transactional(
                state["database"], change_changes, state["store"], change
            )
            out["changes"] = changes
            out["tostring"] = tostring
            html = await jinja(state, "history-detail-apply.html", out)
            await reply_html(send, html)

        await with_change(send, state, components[3], handle_apply_get)
        return

    if (
        path.startswith("/history/u/")
        and components[-2] == "apply"
        and len(components) == 6
        and method == "POST"
    ):

        async def handle_apply_post(change, out):
            await found.transactional(state["database"], change_apply, state["store"], change)
            await reply_redirect(send, "/history/u/{}/".format(change.hex))

        await with_change(send, state, components[3], handle_apply_post)
        return

    if path == "/navigate/" and method == "GET":
        body = scope["query_string"].decode("utf8")
        try:
            body = parse_query_string(body)
        except Exception:
            await reply_bad_request(send, "Invalid form format")
            return

        uid = body.get("uid", [""])[0]
        key = body.get("key", [""])[0]
        value = body.get("value", [""])[0]

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
            out = await query(tx, state["store"], (uid, key, value))
            out = await found.all(found.limit(out, 42))
            return out

        if uidx == "":
            uidx = nstore.var("uid")
        if keyx == "":
            keyx = nstore.var("key")
        if valuex == "":
            valuex = nstore.var("value")

        out = await found.transactional(state["database"], do, uidx, keyx, valuex)
        html = await jinja(
            state,
            "navigate.html",
            dict(
                changes=out,
                uid=uid,
                key=key,
                value=value,
                tostring=tostring,
                isinstance=isinstance,
                UUID=UUID,
            ),
        )
        await reply_html(send, html)
        return

    await not_found(send)


def main():
    import uvicorn

    uvicorn.run(
        "found.ext.vnstore.server:server",
        host="127.0.0.1",
        port=8000,
        lifespan="on",
    )
