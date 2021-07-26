#
# found/eavstore.py
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
from collections import namedtuple
from uuid import uuid4

import found


EAVStore = namedtuple('EAVStore', ('name', 'prefix_data', 'prefix_index'))

EAVSTORE_SUFFIX_DATA = [b'\x01']
EAVSTORE_SUFFIX_INDEX = [b'\x02']


def make(name, prefix):
    out = EAVStore(
        name,
        tuple(list(prefix) + EAVSTORE_SUFFIX_DATA),
        tuple(list(prefix) + EAVSTORE_SUFFIX_INDEX),
    )
    return out


def create(tx, eavstore, dict, uid=None):
    uid = uuid4() if uid is None else uid
    for key, value in dict.items():
        key = found.pack((eavstore.prefix_data, uid, key))
        found.set(tx, key, found.pack((value,)))

    for key, value in dict.items():
        key = found.pack((eavstore.prefix_index, key, value, uid))
        found.set(tx, key, b'')

    return uid


async def get(tx, eavstore, uid):
    out = dict()
    key = found.pack((eavstore.prefix_data, uid))
    async for key, value in found.query(tx, key, found.next_prefix(key)):
        prefix, _, key = found.unpack(key)
        out[key] = found.unpack(value)[0]
    return out


def remove(tx, eavstore, uid):
    dict = get(tx, eavstore, uid)
    for key, value in dict.items():
        key = tuple((eavstore.prefix_index, key))
        found.clear(tx, key)
    key = found.pack((eavstore.prefix_data, uid))
    found.clear(tx, key, found.next_prefix(key))


def update(tx, eavstore, uid, dict):
    remove(tx, eavstore, uid)
    create(tx, eavstore, dict, uid)


async def query(tx, eavstore, key, value):
    key = found.pack((eavstore.prefix_index, key, value))
    async for key, _ in found.query(tx, key, found.next_prefix(key)):
        _, _, _, uid = found.unpack(key)
        yield uid
