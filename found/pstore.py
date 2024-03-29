#
# found/pstore.py
#
# This source file is part of the asyncio-foundationdb open source project
#
# Copyright 2021 Amirouche Boubekki <amirouche@hyper.dev>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import asyncio
import os
import random
from collections import Counter, namedtuple
from operator import itemgetter
from uuid import uuid4

import zstandard as zstd

import found
from found import nstore


class PStoreException(found.BaseFoundException):
    pass


try:
    FOUND_PSTORE_SAMPLE_COUNT = int(os.environ["FOUND_PSTORE_SAMPLE_COUNT"])
except (KeyError, ValueError):
    FOUND_PSTORE_SAMPLE_COUNT = 1337


PSTORE_SUFFIX_TOKENS = [b"\x01"]
PSTORE_SUFFIX_INDEX = [b"\x02"]
PSTORE_SUFFIX_COUNTERS = [b"\x03"]

PStore = namedtuple(
    "PStore", ("name", "tokens", "prefix_index", "prefix_counters", "pool")
)


def make(name, prefix):
    prefix = list(prefix)
    prefix_tokens = tuple(prefix + PSTORE_SUFFIX_TOKENS)
    tokens = nstore.make("{}/token".format(name), prefix_tokens, 2)
    out = PStore(
        name,
        # Use nstore with n=2 to be able to go from a string token to an uid,
        # and back from an uid to a token string.
        tokens,
        # TODO: Replace with a multi-dict (mstore) dedicated store.
        # The value is always empty.
        tuple(prefix + PSTORE_SUFFIX_INDEX),
        # That will map bag uid to a counter serialized to json and
        # compressed with zstd. It is a good old key-value store.
        tuple(prefix + PSTORE_SUFFIX_COUNTERS),
        None,
    )
    return out


async def index(tx, store, docuid, counter):
    # translate keys that are string tokens, into uuid4 bytes with
    # store.tokens
    tokens = dict()
    for string, count in counter.items():
        query = nstore.select(tx, store.tokens, string, nstore.var("uid"))
        try:
            uid = await query.__anext__()
        except StopAsyncIteration:
            uid = uuid4()
            await nstore.add(tx, store.tokens, string, uid)
        else:
            uid = uid["uid"]
        tokens[uid] = count

    # store tokens to use later during search for filtering
    await found.set(
        tx,
        found.pack((store.prefix_counters, docuid)),
        zstd.compress(found.pack(tuple(tokens.items()))),
    )

    # store tokens keys for candidate selection
    for token in tokens:
        await found.set(tx, found.pack((store.prefix_index, token, docuid)), b"")


async def _keywords_to_token(tx, tokens, keyword):
    query = nstore.select(tx, tokens, keyword, nstore.var("uid"))
    try:
        uid = await query.__anext__()
    except StopAsyncIteration:
        return None
    else:
        uid = uid["uid"]
        return uid


async def _token_to_size(tx, prefix_index, token):
    key = found.pack((prefix_index, token))
    out = await found.estimated_size_bytes(tx, key, found.next_prefix(key))
    return out


async def _prepare(tx, prefix, candidates, keywords):
    for candidate in candidates:
        out = await found.get(tx, found.pack((prefix, candidate)))
        yield (candidate, keywords, out)


def _score(args):
    candidate, keywords, counter = args
    counter = dict(found.unpack(zstd.decompress(counter)))
    score = 0
    for keyword in keywords:
        try:
            count = counter[keyword]
        except KeyError:
            return None
        else:
            score += count
    return (candidate, score)


def _filter(hits):
    def wrapped(args):
        if args is not None:
            candidate, score = args
            hits[candidate] = score

    return wrapped


async def massage(tx, store, candidate, keywords, hits):
    score = 0
    counter = await found.get(tx, found.pack((store.prefix_counters, candidate)))
    # TODO: replace the dictionary and the following for loop with
    # a single iteration over the counter, using zigzag algorithm.
    counter = dict(found.unpack(zstd.decompress(counter)))
    for keyword in keywords:
        try:
            count = counter[keyword]
        except KeyError:
            return None
        else:
            score += count
    hits[candidate] = score


async def search(tx, store, keywords, limit=13):
    coroutines = (_keywords_to_token(tx, store.tokens, keyword) for keyword in keywords)
    keywords = await asyncio.gather(*coroutines)
    # If a keyword is not present in store.tokens, then there is no
    # document associated with it, hence there is no document that
    # match that keyword, hence no document that has all the requested
    # keywords. Return an empty counter.
    if any(keyword is None for keyword in keywords):
        return list()

    # Select seed token
    coroutines = (_token_to_size(tx, store.prefix_index, token) for token in keywords)
    sizes = await asyncio.gather(*coroutines)
    _, seed = min(zip(sizes, keywords), key=itemgetter(0))

    # Select candidates
    candidates = []
    key = found.pack((store.prefix_index, seed))
    query = found.query(tx, key, found.next_prefix(key))

    async for key, _ in query:
        _, _, uid = found.unpack(key)
        candidates.append(uid)

    # XXX: 500 was empirically discovered, to make it so that the
    #      search takes less than 1 second or so.
    if len(candidates) >= FOUND_PSTORE_SAMPLE_COUNT:
        candidates = random.sample(candidates, FOUND_PSTORE_SAMPLE_COUNT)

    # score, filter and construct hits aka. massage
    hits = Counter()

    coroutines = (massage(tx, store, c, keywords, hits) for c in candidates)
    await asyncio.gather(*coroutines)

    out = hits.most_common(limit)

    return out
