"""Versioned N-tuple store backed by FoundationDB."""

# Copyright (C) 2020-2023 Amirouche A. Boubekki
#
# https://github.com/amirouche/asyncio-foundationdb
#
import asyncio
import logging
from collections import namedtuple
from uuid import UUID, uuid4

from uuid_extensions import uuid7

import found
from found.base import FoundException
from found.ext import nstore

_VNStore = namedtuple("VNStore", "name subspace items changes tuples names")


class VNStoreException(FoundException):
    pass


def make(name, subspace, items):
    """Create a versioned tuple store called ``name`` with ``subspace`` and column ``items``."""
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
    """Create a new change and return its uid. Initial significance is ``None``."""
    tr.vars["vnstore_changeid"] = changeid = uuid4()
    # With significance as `None` the change is invisible to
    # VNStore.ask.
    await nstore.add(tr, vnstore.changes, changeid, "type", "change")
    await nstore.add(tr, vnstore.changes, changeid, "significance", None)
    await nstore.add(tr, vnstore.changes, changeid, "message", None)
    return changeid


async def change_list(tr, vnstore):
    """Return a list of all changes in ``vnstore``."""
    out = []
    async for binding in nstore.query(tr, vnstore.changes, (nstore.var("uid"), "type", "change")):
        out.append(await change_get(tr, vnstore, binding.get("uid")))
    return out


async def change_get(tr, vnstore, changeid):
    """Return the change as a dict, or ``None`` if it does not exist."""
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
    """Set ``changeid`` as the active change for subsequent add/remove calls."""
    tr.vars["_vnstore_changeid"] = changeid


async def change_message(tr, vnstore, changeid, message):
    """Replace the message of ``changeid`` with ``message``."""
    # Remove existing message if any
    async for binding in nstore.query(
        tr, vnstore.changes, (changeid, "message", nstore.var("message"))
    ):
        await nstore.remove(tr, vnstore.changes, changeid, "message", binding["message"])
    await nstore.add(tr, vnstore.changes, changeid, "message", message)


async def change_changes(tr, vnstore, changeid):
    """Return a list of all tuple modifications associated with ``changeid``."""
    out = []
    pattern = [nstore.var(x) for x in vnstore.names]
    pattern += [changeid, nstore.var("alive?")]
    out = await found.all(nstore.query(tr, vnstore.tuples, pattern))
    return out


def pk(*args):
    print(args)
    return args[-1]


async def change_apply(tr, vnstore, changeid):
    """Apply ``changeid``, setting its significance to a new uuid7."""
    # apply change by settings a verionstamp
    value = await nstore.get(tr, vnstore.changes, changeid, "significance", None)
    # It was already applied
    if value is None:
        logging.warning("Trying to apply an already applied change: %s", changeid)
        return
    await nstore.remove(tr, vnstore.changes, changeid, "significance", None)
    significance = uuid7()
    await nstore.add(tr, vnstore.changes, changeid, "significance", significance)


async def ask(tr, vnstore, *items):
    """Return ``True`` if ``items`` is alive in ``vnstore``."""
    assert len(items) == len(vnstore.items), "Incorrect count of ITEMS"
    # Complexity is O(n), where n is the number of times the exact
    # same ITEMS were added and deleted.  In pratice, n=0, n=1 or
    # n=2, and of course it always possible that it is more...
    items = list(items)
    items.append(nstore.var("changeid"))
    items.append(nstore.var("alive?"))
    bindings = await found.all(nstore.query(tr, vnstore.tuples, items))

    if not bindings:
        return False

    # Pipeline all significance lookups concurrently
    async def get_significance(binding):
        result = await found.all(
            nstore.query(
                tr,
                vnstore.changes,
                (binding["changeid"], "significance", nstore.var("significance")),
            )
        )
        return result[0]["significance"]

    significances = await asyncio.gather(*(get_significance(b) for b in bindings))

    ok = False
    significance_max = UUID(int=0)
    for binding, significance in zip(bindings, significances):
        if (significance is not None) and (significance > significance_max):
            significance_max = significance
            ok = binding["alive?"]
    return ok


async def get(tr, *items):
    # TODO: ask, but return the value
    raise NotImplementedError


async def add(tr, vnstore, *items, value=b""):
    """Add ``items`` to ``vnstore`` under the current active change."""
    # TODO: add support for the value
    assert len(items) == len(vnstore.items)
    assert tr.vars["_vnstore_changeid"]
    items = list(items) + [tr.vars["_vnstore_changeid"], True]
    await nstore.add(tr, vnstore.tuples, *items, value=value)
    return True


async def remove(tr, vnstore, *items):
    """Remove ``items`` from ``vnstore`` under the current active change."""
    assert len(items) == len(vnstore.items)
    if not await ask(tr, vnstore, *items):
        # ITEMS does not exists, nothing to do.
        return False
    # Delete it
    items = list(items) + [tr.vars["_vnstore_changeid"], False]
    await nstore.add(tr, vnstore.tuples, *items)
    return True


async def select(tr, vnstore, *pattern, seed=None):
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
    #
    # NB: if ask() per row becomes a bottleneck, the winning
    # pattern is to chunk candidates and asyncio.gather the
    # ask() calls across each chunk.
    query = pattern
    pattern = list(pattern) + [nstore.var("changeid"), nstore.var("alive?")]
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

        yield {k: v for k, v in binding.items() if k not in ("changeid", "alive?")}


async def where(tr, vnstore, iterator, *pattern):
    """Bind ``pattern`` against each binding from ``iterator``, yield matching bindings."""
    assert len(pattern) == len(vnstore.items), "invalid item count"

    async for bindings in iterator:
        # bind PATTERN against BINDINGS
        bound = []
        for item in pattern:
            # if ITEM is variable try to bind
            if isinstance(item, nstore.Variable):
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
    """Return bindings matching ``pattern`` and ``patterns`` by chaining select and where."""
    out = select(tx, nstore, *pattern)
    for pattern in patterns:
        out = where(tx, nstore, out, *pattern)
    return out
