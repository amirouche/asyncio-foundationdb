#
# Copyright (C) 2015-2021  Amirouche Boubekki <amirouche@hyper.dev>
#
# https://github.com/amirouche/found/
#
import itertools
from math import factorial
from collections import namedtuple

import found
from found.base import FoundException

from immutables import Map


def pk(*args):
    print(*args)
    return args[-1]


# Compute the minimal set of indices required to bind any n-pattern in
# one hop.
#
# Based on https://stackoverflow.com/a/55148433/140837


def bc(n, k):
    """Binomial coefficient"""
    return factorial(n) // factorial(k) // factorial(n - k) if k < n else 0


def stringify(iterable):
    return "".join(str(x) for x in iterable)


def combinations(tab):
    out = []
    for i in range(1, len(tab) + 1):
        out.extend(stringify(x) for x in itertools.combinations(tab, i))
    assert len(out) == 2 ** len(tab) - 1
    return out


def ok(solutions, tab):
    """Check that SOLUTIONS of TAB is a correct solution"""
    cx = combinations(tab)

    for combination in cx:
        pcx = ["".join(x) for x in itertools.permutations(combination)]
        # check for existing solution
        for solution in solutions:
            if any(solution.startswith(p) for p in pcx):
                # yeah, there is an existing solution
                break
        else:
            raise Exception("failed with combination={}".format(combination))
    else:
        return True
    return False


def _compute_indices(n):
    tab = list(range(n))
    cx = list(itertools.combinations(tab, n // 2))
    for c in cx:
        L = [(i, i in c) for i in tab]
        A = []
        B = []
        while True:
            for i in range(len(L) - 1):
                if (not L[i][1]) and L[i + 1][1]:
                    A.append(L[i + 1][0])
                    B.append(L[i][0])
                    L.remove((L[i + 1][0], True))
                    L.remove((L[i][0], False))
                    break
            else:
                break
        l = [i for (i, _) in L]  # noqa
        yield tuple(A + l + B)


# helpers


def take(iterator, count):
    for _ in range(count):
        out = next(iterator)
        yield out


def drop(iterator, count):
    for _ in range(count):
        next(iterator)
    yield from iterator


class NStoreException(FoundException):
    pass


Variable = var = namedtuple('Variable', ('name',))


def is_permutation_prefix(combination, index):
    index = stringify(index)
    out = any(
        index.startswith(stringify(x)) for x in itertools.permutations(combination)
    )
    return out


_NStore = namedtuple('NStore', ('name', 'prefix', 'n', 'indices'))


def make(name, prefix, n):
    return _NStore(name, tuple(prefix), n, list(_compute_indices(n)))


def add(tx, nstore, *items, value=b''):
    assert len(items) == nstore.n, "invalid item count"
    for subspace, index in enumerate(nstore.indices):
        permutation = list(items[i] for i in index)
        key = tuple(nstore.prefix) + (subspace,) + tuple(permutation)
        found.set(tx, found.pack(key), value)


def remove(tx, nstore, *items):
    assert len(items) == nstore.n, "invalid item count"
    for subspace, index in enumerate(nstore.indices):
        permutation = list(items[i] for i in index)
        key = nstore.prefix + (subspace,) + tuple(permutation)
        found.clear(tx, found.pack(tuple(key)))


async def get(tx, nstore, *items):
    assert len(items) == nstore.n, "invalid item count"
    subspace = 0
    key = nstore.prefix + (subspace,) + tuple(items)
    out = await found.get(tx, found.pack(tuple(key)))
    out = None if out is None else out
    return out


async def select(tx, nstore, *pattern, seed=Map()):  # seed is immutable
    """Yields bindings that match PATTERN"""
    assert len(pattern) == nstore.n, "invalid item count"
    variable = tuple(isinstance(x, Variable) for x in pattern)
    # find the first index suitable for the query
    combination = tuple(x for x in range(nstore.n) if not variable[x])
    for subspace, index in enumerate(nstore.indices):
        if is_permutation_prefix(combination, index):
            break
    else:
        raise NStoreException("Oops!")
    # `index` variable holds the permutation suitable for the
    # query. `subspace` is the "prefix" of that index.
    prefix = list(pattern[i] for i in index if not isinstance(pattern[i], Variable))
    prefix = list(nstore.prefix) + [subspace] + prefix
    start = found.pack(tuple(prefix))
    end = found.next_prefix(start)
    async for key, _ in found.query(tx, start, end):
        items = found.unpack(key)[len(nstore.prefix) + 1:]
        # re-order the items
        items = tuple(items[index.index(i)] for i in range(nstore.n))
        bindings = seed
        for i, item in enumerate(pattern):
            if isinstance(item, Variable):
                bindings = bindings.set(item.name, items[i])
        yield bindings


async def where(tx, nstore, iterator, *pattern):
    assert len(pattern) == nstore.n, "invalid item count"

    async for bindings in iterator:
        # bind PATTERN against BINDINGS
        bound = []
        for item in pattern:
            # if ITEM is variable try to bind
            if isinstance(item, Variable):
                try:
                    value = bindings[item.name]
                except KeyError:
                    # no bindings
                    bound.append(item)
                else:
                    # pick the value in bindings
                    bound.append(value)
            else:
                # otherwise keep item as is
                bound.append(item)
        # hey!
        out = select(tx, nstore, *bound, seed=bindings)
        async for binding in out:
            yield binding


def query(tx, nstore, pattern, *patterns):
    out = select(tx, nstore, *pattern)
    for pattern in patterns:
        out = where(tx, nstore, out, *pattern)
    return out
