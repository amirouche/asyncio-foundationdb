"""FoundationDB asyncio drivers for Python."""
#
# __init__.py
#
# This source file is part of the FoundationDB open source project
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018-2021 Amirouche Boubekki <amirouche@hyper.dev>
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

import fdb

from found._fdb import lib

__VERSION__ = (0, 13, 0)

MAX_SIZE_TRANSACTION = 10**7
MAX_SIZE_KEY = 10**4
MAX_SIZE_VALUE = 10**5


HEADER_VERSION = VERSION = 730


code = lib.fdb_select_api_version_impl(VERSION, HEADER_VERSION)
if code == 2203:
    max_supported_ver = lib.fdb_get_max_api_version()
    if HEADER_VERSION > max_supported_ver:
        msg = "This version of the FoundationDB Python binding is not supported by "
        msg += "the installed FoundationDB C library. The binding requires a library "
        msg += "that supports API version %d, but the installed library supports a "
        msg += "maximum version of %d."
        msg = msg % (HEADER_VERSION, max_supported_ver)
        raise RuntimeError(msg)
    else:
        msg = "API version %d is not supported by the installed FoundationDB C library."
        msg = msg % VERSION
        raise RuntimeError(msg)
elif code != 0:
    raise RuntimeError("FoundationDB API error ({})".format(code))


# Required to use fdb.tuple.pack and fdb.tuple.unpack
fdb._version = VERSION

# Load fdb.impl so that fdb.tuple.Versionstamp.to_bytes() can reference
# fdb.impl.Value without AttributeError.
# Workaround: PyPy lacks ctypes.pythonapi; provide a stub so fdb.impl's
# hasattr() check falls through to its built-in fallback.
import ctypes
if not hasattr(ctypes, "pythonapi"):
    ctypes.pythonapi = type("_stub", (), {})()
import fdb.impl  # noqa

from fdb.tuple import Versionstamp  # noqa
from fdb.tuple import has_incomplete_versionstamp  # noqa
from fdb.tuple import pack  # noqa
from fdb.tuple import pack_with_versionstamp  # noqa
from fdb.tuple import unpack  # noqa

from found.base import STREAMING_MODE_EXACT  # noqa
from found.base import STREAMING_MODE_ITERATOR  # noqa
from found.base import STREAMING_MODE_LARGE  # noqa
from found.base import STREAMING_MODE_MEDIUM  # noqa
from found.base import STREAMING_MODE_SERIAL  # noqa
from found.base import STREAMING_MODE_SMALL  # noqa
from found.base import STREAMING_MODE_WANT_ALL  # noqa
from found.base import BaseFoundException  # noqa
from found.base import FoundException  # noqa
from found.base import CONFLICT_RANGE_TYPE_READ  # noqa
from found.base import CONFLICT_RANGE_TYPE_WRITE  # noqa
from found.base import KeySelector  # noqa
from found.base import Transaction  # noqa
from found.base import _make_transaction  # noqa
from found.base import ERROR_PREDICATE_MAYBE_COMMITTED  # noqa
from found.base import ERROR_PREDICATE_RETRYABLE  # noqa
from found.base import ERROR_PREDICATE_RETRYABLE_NOT_COMMITTED  # noqa
from found.base import add  # noqa
from found.base import add_network_thread_completion_hook  # noqa
from found.base import append_if_fits  # noqa
from found.base import add_conflict_range  # noqa
from found.base import bit_and  # noqa
from found.base import bit_or  # noqa
from found.base import bit_xor  # noqa
from found.base import byte_max  # noqa
from found.base import byte_min  # noqa
from found.base import cancel  # noqa
from found.base import clear  # noqa
from found.base import commit  # noqa
from found.base import compare_and_clear  # noqa
from found.base import database_set_option  # noqa
from found.base import error_predicate  # noqa
from found.base import estimated_size_bytes  # noqa
from found.base import get  # noqa
from found.base import get_addresses_for_key  # noqa
from found.base import get_approximate_size  # noqa
from found.base import get_client_version  # noqa
from found.base import get_committed_version  # noqa
from found.base import get_key  # noqa
from found.base import get_range  # noqa
from found.base import get_range_split_points  # noqa
from found.base import get_versionstamp  # noqa
from found.base import gt  # noqa
from found.base import gte  # noqa
from found.base import lt  # noqa
from found.base import lte  # noqa
from found.base import max  # noqa
from found.base import min  # noqa
from found.base import network_set_option  # noqa
from found.base import next_prefix  # noqa
from found.base import on_error  # noqa
from found.base import open  # noqa
from found.base import query  # noqa
from found.base import read_version  # noqa
from found.base import reset  # noqa
from found.base import set  # noqa
from found.base import set_option  # noqa
from found.base import set_read_version  # noqa
from found.base import set_versionstamped_key  # noqa
from found.base import set_versionstamped_value  # noqa
from found.base import transactional  # noqa
from found.base import watch  # noqa

# TODO: from fdb.subspace_impl import Subspace  # noqa


def co(func):
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


async def all(aiogenerator):
    out = []
    async for item in aiogenerator:
        out.append(item)
    return out

async def limit(iterator, length):
    async for item in iterator:
        if length <= 0:
            return
        length -= 1
        yield item
