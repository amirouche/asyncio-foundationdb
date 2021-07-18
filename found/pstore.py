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
from uuid import uuid4
from collections import namedtuple
from collections import Counter

import found
from found import nstore

import zstandard as zstd


class PStoreException(found.BaseFoundException):
    pass


PSTORE_SUFFIX_TOKENS = [b'\x01']
PSTORE_SUFFIX_INDEX = [b'\x02']
PSTORE_SUFFIX_COUNTERS = [b'\x03']

PStore = namedtuple('PStore', ('name', 'tokens', 'prefix_index', 'prefix_counters', 'pool'))


def make(name, prefix, pool):
    prefix = list(prefix)
    prefix_tokens = tuple(prefix + PSTORE_SUFFIX_TOKENS)
    tokens = nstore.make('{}/token'.format(name), prefix_tokens, 2)
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
    )
    return out


async def index(tx, store, uid, counter):
    # translate keys that are string tokens, into uuid4 bytes with
    # store.tokens
    tokens = dict()
    for string, count in counter.items():
        query = await nstore.select(tx, store.tokens, string, nstore.var('uid'))
        try:
            uid = await query.__anext__()
        except StopAsyncIteration:
            uid = uuid4()
            nstore.add(tx, store.tokens, string, uid)
        else:
            uid = uid['uid']
        tokens[uid] = count

    # store tokens to use later during search for filtering
    found.set(
        found.pack((store.prefix_counters, uid)),
        zstd.compress(found.pack(tuple(tokens.items())))
    )

    # store tokens keys for candidate selection
    for token in tokens:
        found.set(found.pack((store.prefix_index, token, uid)), b'')


async def _keywords_to_uid(tx, tokens, keyword):
    query = await nstore.select(tx, tokens, keyword, nstore.var('uid'))
    try:
        uid = await query.__anext__()
    except StopAsyncIteration:
        return None
    else:
        uid = uid['uid']
        return uid


async def search(tx, store, keywords):
    out = Counter()
    coroutines = [_keywords_to_uid(tx, store.tokens, keyword) for keyword in keywords]
    uids = await asyncio.gather(*coroutines)
    # If a keyword is not present in store.tokens, then there is not
    # document associated with it, hence there is no document that
    # match that keyword, hence no document that has all the requested
    # keywords. Return an empty counter.
    if any(uid is None for uid in uids):
        return out
    # Select candidate
