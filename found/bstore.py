#
# found/bstore.py
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
from uuid import uuid4
from uuid import UUID
from collections import namedtuple

from hashlib import blake2b as hasher
from more_itertools import sliced

import found


class BStoreException(found.BaseFoundException):
    pass


BSTORE_SUFFIX_HASH = [b'\x01']
BSTORE_SUFFIX_BLOB = [b'\x02']

BStore = namedtuple('BStore', ('name', 'prefix_hash', 'prefix_blob',))


def make(name, prefix):
    prefix = list(prefix)
    out = BStore(name, tuple(prefix + BSTORE_SUFFIX_HASH), tuple(prefix + BSTORE_SUFFIX_BLOB))
    return out


async def get_or_create(tx, bstore, blob):
    hash = hasher(blob).digest()
    key = found.pack((bstore.prefix_hash, hash))
    maybe_uid = await found.get(tx, key)
    if maybe_uid is not None:
        return UUID(bytes=maybe_uid)
    # Otherwise create the hash entry and store the blob with a new uid
    # TODO: Use a counter and implement a garbage collector, and implement
    # bstore.delete
    uid = uuid4()
    found.set(tx, key, uid.bytes)
    for index, slice in enumerate(sliced(blob, found.MAX_SIZE_VALUE)):
        found.set(tx, found.pack((bstore.prefix_blob, uid, index)), bytes(slice))
    return uid


async def get(tx, bstore, uid):
    key = found.pack((bstore.prefix_blob, uid))
    out = b''
    async for _, value in found.query(tx, key, found.next_prefix(key)):
        out += value
    if out == b'':
        raise BStoreException('BLOB should be in database: uid={}'.format(uid))
    return out
