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

from found._fdb import lib
import fdb


__VERSION__ = (0, 10, 0)

MAX_SIZE_TRANSACTION = 10 ** 7
MAX_SIZE_KEY = 10 ** 4
MAX_SIZE_VALUE = 10 ** 5


HEADER_VERSION = VERSION = 630


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

from found.base import BaseFoundException  # noqa
from found.base import FoundException  # noqa
from found.base import next_prefix  # noqa
from found.base import STREAMING_MODE_WANT_ALL  # noqa
from found.base import STREAMING_MODE_ITERATOR  # noqa
from found.base import STREAMING_MODE_EXACT  # noqa
from found.base import STREAMING_MODE_SMALL  # noqa
from found.base import STREAMING_MODE_MEDIUM  # noqa
from found.base import STREAMING_MODE_LARGE  # noqa
from found.base import STREAMING_MODE_SERIAL  # noqa
from found.base import read_version  # noqa
from found.base import get  # noqa
from found.base import lt  # noqa
from found.base import lte  # noqa
from found.base import gt  # noqa
from found.base import gte  # noqa
from found.base import query  # noqa
from found.base import estimated_size_bytes  # noqa
from found.base import set_read_version  # noqa
from found.base import set  # noqa
from found.base import clear  # noqa
from found.base import add  # noqa
from found.base import bit_and  # noqa
from found.base import bit_or  # noqa
from found.base import bit_xor  # noqa
from found.base import max  # noqa
from found.base import byte_max  # noqa
from found.base import min  # noqa
from found.base import byte_min  # noqa
from found.base import set_versionstamped_key  # noqa
from found.base import set_versionstamped_value  # noqa
from found.base import transactional  # noqa
from found.base import open  # noqa

from fdb.tuple import pack  # noqa
from fdb.tuple import pack_with_versionstamp  # noqa
from fdb.tuple import unpack  # noqa
from fdb.tuple import has_incomplete_versionstamp  # noqa
from fdb.tuple import Versionstamp  # noqa

# TODO: from fdb.subspace_impl import Subspace  # noqa


def co(func):
    async def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
