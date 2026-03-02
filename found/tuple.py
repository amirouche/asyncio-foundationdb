# found/tuple.py — native tuple layer for found
#
# The lexode encode/decode core (pack, unpack, next_prefix and helpers) is
# reproduced verbatim from:
#   https://github.com/amirouche/lexode  (lexode 0.3.0)
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018-2022 Amirouche Boubekki <amirouche@hyper.dev>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.
#

import struct
import uuid as _uuid_mod

__all__ = [
    "pack",
    "unpack",
    "next_prefix",
    "Versionstamp",
    "pack_with_versionstamp",
    "has_incomplete_versionstamp",
    # type-code constants (re-exported for introspection)
    "NULL_CODE",
    "BYTES_CODE",
    "FALSE_CODE",
    "TRUE_CODE",
    "INTEGER_NEGATIVE_CODE",
    "INTEGER_ZERO",
    "INTEGER_POSITIVE_CODE",
    "STRING_CODE",
    "NESTED_CODE",
    "DOUBLE_CODE",
    "VERSIONSTAMP_CODE",
    "UUID_CODE",
]

# ---------------------------------------------------------------------------
# Type codes (lexode-compatible)
# ---------------------------------------------------------------------------

NULL_CODE = 0x00
BYTES_CODE = 0x01
FALSE_CODE = 0x02
TRUE_CODE = 0x03
INTEGER_NEGATIVE_CODE = 0x04
INTEGER_ZERO = 0x05
INTEGER_POSITIVE_CODE = 0x06
STRING_CODE = 0x07
NESTED_CODE = 0x08
DOUBLE_CODE = 0x09
# One above lexode's highest code; used for Versionstamp values.
VERSIONSTAMP_CODE = 0x0A
# UUID (16 raw bytes, big-endian / RFC 4122 byte order)
UUID_CODE = 0x0B

INTEGER_MAX = struct.unpack(">Q", b"\xff" * 8)[0]

_size_limits = tuple((1 << (i * 8)) - 1 for i in range(9))

# ---------------------------------------------------------------------------
# Versionstamp
# ---------------------------------------------------------------------------

_INCOMPLETE_TR_VERSION = b"\xff" * 10


class Versionstamp:
    """10-byte transaction version + 2-byte user version (total 12 bytes).

    An *incomplete* versionstamp (tr_version=None) is a placeholder; FDB fills
    in the actual transaction version when the key is committed via
    set_versionstamped_key / set_versionstamped_value.
    """

    __slots__ = ("tr_version", "user_version")

    def __init__(self, tr_version=None, user_version=0):
        self.tr_version = tr_version  # bytes[10] or None if incomplete
        self.user_version = user_version

    @classmethod
    def incomplete(cls, user_version=0):
        return cls(None, user_version)

    def is_complete(self):
        return self.tr_version is not None

    def to_bytes(self):
        tr = self.tr_version if self.tr_version is not None else _INCOMPLETE_TR_VERSION
        return tr + struct.pack(">H", self.user_version)

    @classmethod
    def from_bytes(cls, data, start=0):
        tr = data[start : start + 10]
        uv = struct.unpack(">H", data[start + 10 : start + 12])[0]
        return cls(None if tr == _INCOMPLETE_TR_VERSION else tr, uv)

    def completed(self, new_tr_version):
        return Versionstamp(new_tr_version, self.user_version)

    def __eq__(self, other):
        return isinstance(other, Versionstamp) and self.to_bytes() == other.to_bytes()

    def __hash__(self):
        return hash(self.to_bytes())

    def __repr__(self):
        return f"Versionstamp(tr_version={self.tr_version!r}, user_version={self.user_version})"


# ---------------------------------------------------------------------------
# Helpers (inlined from lexode)
# ---------------------------------------------------------------------------


def _find_terminator(v, pos):
    """Find the start of the next terminator [\\x00]![\\xff] or the end of v."""
    while True:
        pos = v.find(b"\x00", pos)
        if pos < 0:
            return len(v)
        if pos + 1 == len(v) or v[pos + 1 : pos + 2] != b"\xff":
            return pos
        pos += 2


def _float_adjust(v, encode):
    """Adjust IEEE 754 bytes for lexicographic ordering."""
    if encode and v[0] & 0x80 != 0x00:
        return bytes(x ^ 0xFF for x in v)
    elif not encode and v[0] & 0x80 != 0x80:
        return bytes(x ^ 0xFF for x in v)
    else:
        return bytes((v[0] ^ 0x80,)) + v[1:]


# ---------------------------------------------------------------------------
# Decoder (inlined from lexode + Versionstamp extension)
# ---------------------------------------------------------------------------


def _decode(v, pos):
    code = v[pos]
    if code == NULL_CODE:
        return None, pos + 1
    elif code == BYTES_CODE:
        end = _find_terminator(v, pos + 1)
        return v[pos + 1 : end].replace(b"\x00\xFF", b"\x00"), end + 1
    elif code == STRING_CODE:
        end = _find_terminator(v, pos + 1)
        return v[pos + 1 : end].replace(b"\x00\xFF", b"\x00").decode("utf-8"), end + 1
    elif code == INTEGER_ZERO:
        return 0, pos + 1
    elif code == INTEGER_NEGATIVE_CODE:
        end = pos + 1 + 8
        value = struct.unpack(">Q", v[pos + 1 : end])[0] - INTEGER_MAX
        return value, end
    elif code == INTEGER_POSITIVE_CODE:
        end = pos + 1 + 8
        value = struct.unpack(">Q", v[pos + 1 : end])[0]
        return value, end
    elif code == FALSE_CODE:
        return False, pos + 1
    elif code == TRUE_CODE:
        return True, pos + 1
    elif code == DOUBLE_CODE:
        return (
            struct.unpack(">d", _float_adjust(v[pos + 1 : pos + 9], False))[0],
            pos + 9,
        )
    elif code == NESTED_CODE:
        ret = []
        end_pos = pos + 1
        while end_pos < len(v):
            if v[end_pos] == 0x00:
                if end_pos + 1 < len(v) and v[end_pos + 1] == 0xFF:
                    ret.append(None)
                    end_pos += 2
                else:
                    break
            else:
                val, end_pos = _decode(v, end_pos)
                ret.append(val)
        return tuple(ret), end_pos + 1
    elif code == VERSIONSTAMP_CODE:
        vs = Versionstamp.from_bytes(v, pos + 1)
        return vs, pos + 13  # 1 code + 12 bytes (10 tr_version + 2 user_version)
    elif code == UUID_CODE:
        return _uuid_mod.UUID(bytes=bytes(v[pos + 1 : pos + 17])), pos + 17
    else:
        raise ValueError("Unknown data type from database: " + repr(v))


# ---------------------------------------------------------------------------
# Encoder (inlined from lexode + Versionstamp extension)
# ---------------------------------------------------------------------------


def _encode(value, nested=False):
    if value is None:
        if nested:
            return bytes((NULL_CODE, 0xFF))
        else:
            return bytes((NULL_CODE,))
    elif isinstance(value, bool):
        if value:
            return bytes((TRUE_CODE,))
        else:
            return bytes((FALSE_CODE,))
    elif isinstance(value, Versionstamp):
        return bytes((VERSIONSTAMP_CODE,)) + value.to_bytes()
    elif isinstance(value, _uuid_mod.UUID):
        return bytes((UUID_CODE,)) + value.bytes
    elif isinstance(value, bytes):
        return bytes((BYTES_CODE,)) + value.replace(b"\x00", b"\x00\xFF") + b"\x00"
    elif isinstance(value, str):
        return (
            bytes((STRING_CODE,))
            + value.encode("utf-8").replace(b"\x00", b"\x00\xFF")
            + b"\x00"
        )
    elif value == 0:
        return bytes((INTEGER_ZERO,))
    elif isinstance(value, int):
        if value > 0:
            return bytes((INTEGER_POSITIVE_CODE,)) + struct.pack(">Q", value)
        else:
            value = INTEGER_MAX + value
            return bytes((INTEGER_NEGATIVE_CODE,)) + struct.pack(">Q", value)
    elif isinstance(value, float):
        return bytes((DOUBLE_CODE,)) + _float_adjust(struct.pack(">d", value), True)
    elif isinstance(value, (tuple, list)):
        child_bytes = list(map(lambda x: _encode(x, True), value))
        return b"".join([bytes((NESTED_CODE,))] + child_bytes + [bytes((0x00,))])
    else:
        raise ValueError("Unsupported data type: {}".format(type(value)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def pack(t):
    """Pack a tuple of values into a lexicographically ordered byte string."""
    return b"".join(_encode(x) for x in t)


def unpack(key):
    """Unpack a byte string produced by pack() back into a tuple."""
    pos = 0
    res = []
    while pos < len(key):
        r, pos = _decode(key, pos)
        res.append(r)
    return tuple(res)


def next_prefix(x):
    """Return the smallest bytes sequence that does not start with x."""
    x = x.rstrip(b"\xff")
    return x[:-1] + bytes((x[-1] + 1,))


def has_incomplete_versionstamp(t):
    """Return True if tuple t contains an incomplete Versionstamp at any depth."""
    for item in t:
        if isinstance(item, Versionstamp) and not item.is_complete():
            return True
        if isinstance(item, (tuple, list)) and has_incomplete_versionstamp(item):
            return True
    return False


def pack_with_versionstamp(t, prefix=None):
    """Pack a tuple that contains exactly one incomplete Versionstamp.

    Returns the packed bytes with a 4-byte little-endian offset appended at the
    end, pointing to the start of the 10-byte transaction version field within
    the key.  Pass the result to set_versionstamped_key / set_versionstamped_value
    (FDB API >= 520 convention).
    """
    if not has_incomplete_versionstamp(t):
        raise ValueError("No incomplete versionstamp in tuple")
    pre = prefix if prefix else b""
    chunks = [pre]
    vs_pos = -1
    cur = len(pre)
    for item in t:
        chunk = _encode(item)
        if isinstance(item, Versionstamp) and not item.is_complete():
            # vs_pos points to where the 10-byte tr_version starts:
            # cur (start of this item) + 1 (type code byte)
            vs_pos = cur + 1
        chunks.append(chunk)
        cur += len(chunk)
    if vs_pos < 0:
        raise ValueError("Incomplete versionstamp not found during encoding")
    result = b"".join(chunks)
    return result + struct.pack("<I", vs_pos)  # 4-byte LE offset (API >= 520)
