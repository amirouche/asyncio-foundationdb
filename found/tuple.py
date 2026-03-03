# found/tuple.py — native tuple layer, encoding-compatible with the official
# FoundationDB Python binding (fdb.tuple / fdb.impl).
#
# Copyright 2013-2018 Apple Inc. and the FoundationDB project authors
# Copyright 2018-2026 Amirouche Boubekki <amirouche@hyper.dev>
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
from bisect import bisect_left

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
    "STRING_CODE",
    "NESTED_CODE",
    "NEG_INT_START",
    "INT_ZERO_CODE",
    "POS_INT_END",
    "DOUBLE_CODE",
    "FALSE_CODE",
    "TRUE_CODE",
    "UUID_CODE",
    "VERSIONSTAMP_CODE",
]

# ---------------------------------------------------------------------------
# Type codes — identical to the official FDB Python binding (fdb/tuple.py)
# ---------------------------------------------------------------------------

NULL_CODE = 0x00
BYTES_CODE = 0x01
STRING_CODE = 0x02
NESTED_CODE = 0x05
NEG_INT_START = 0x0B  # arbitrary-precision negative integer (length ^ 0xFF prefix)
INT_ZERO_CODE = 0x14  # integer zero; codes 0x0C–0x13 = negative, 0x15–0x1C = positive
POS_INT_END = 0x1D    # arbitrary-precision positive integer (length prefix)
DOUBLE_CODE = 0x21
FALSE_CODE = 0x26
TRUE_CODE = 0x27
UUID_CODE = 0x30
VERSIONSTAMP_CODE = 0x33

# _size_limits[n] = 2^(8n) - 1; used for variable-length integer encoding.
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
# Helpers
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
# Decoder
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
    elif code == INT_ZERO_CODE:
        return 0, pos + 1
    elif INT_ZERO_CODE < code < POS_INT_END:  # 0x15–0x1C: positive 1–8 byte int
        n = code - INT_ZERO_CODE
        end = pos + 1 + n
        return int.from_bytes(v[pos + 1 : end], "big"), end
    elif code == POS_INT_END:  # 0x1D: arbitrary-precision positive int
        n = v[pos + 1]
        end = pos + 2 + n
        return int.from_bytes(v[pos + 2 : end], "big"), end
    elif NEG_INT_START < code < INT_ZERO_CODE:  # 0x0C–0x13: negative 1–8 byte int
        n = INT_ZERO_CODE - code
        end = pos + 1 + n
        stored = int.from_bytes(v[pos + 1 : end], "big")
        return stored - _size_limits[n], end
    elif code == NEG_INT_START:  # 0x0B: arbitrary-precision negative int
        n = v[pos + 1] ^ 0xFF
        end = pos + 2 + n
        stored = int.from_bytes(v[pos + 2 : end], "big")
        return stored - (1 << (n * 8)) + 1, end
    elif code == DOUBLE_CODE:
        return (
            struct.unpack(">d", _float_adjust(v[pos + 1 : pos + 9], False))[0],
            pos + 9,
        )
    elif code == FALSE_CODE:
        return False, pos + 1
    elif code == TRUE_CODE:
        return True, pos + 1
    elif code == UUID_CODE:
        return _uuid_mod.UUID(bytes=bytes(v[pos + 1 : pos + 17])), pos + 17
    elif code == VERSIONSTAMP_CODE:
        vs = Versionstamp.from_bytes(v, pos + 1)
        return vs, pos + 13  # 1 code + 12 bytes (10 tr_version + 2 user_version)
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
    else:
        raise ValueError("Unknown data type from database: " + repr(v))


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------


def _encode(value, nested=False):
    if value is None:
        if nested:
            return bytes((NULL_CODE, 0xFF))
        return bytes((NULL_CODE,))
    elif isinstance(value, bool):
        return bytes((TRUE_CODE,)) if value else bytes((FALSE_CODE,))
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
    elif isinstance(value, int):
        if value == 0:
            return bytes((INT_ZERO_CODE,))
        elif value > 0:
            if value >= _size_limits[-1]:
                n = (value.bit_length() + 7) // 8
                return bytes((POS_INT_END, n)) + value.to_bytes(n, "big")
            n = bisect_left(_size_limits, value)
            return bytes((INT_ZERO_CODE + n,)) + value.to_bytes(n, "big")
        else:
            abs_val = -value
            if abs_val >= _size_limits[-1]:
                n = (abs_val.bit_length() + 7) // 8
                stored = value + (1 << (n * 8)) - 1
                return bytes((NEG_INT_START, n ^ 0xFF)) + stored.to_bytes(n, "big")
            n = bisect_left(_size_limits, abs_val)
            stored = _size_limits[n] + value
            return bytes((INT_ZERO_CODE - n,)) + stored.to_bytes(n, "big")
    elif isinstance(value, float):
        return bytes((DOUBLE_CODE,)) + _float_adjust(struct.pack(">d", value), True)
    elif isinstance(value, (tuple, list)):
        child_bytes = [_encode(x, True) for x in value]
        return b"".join([bytes((NESTED_CODE,))] + child_bytes + [b"\x00"])
    else:
        raise ValueError("Unsupported data type: {}".format(type(value)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def pack(t):
    """Pack a tuple of values into a lexicographically ordered byte string.

    Encoding is byte-for-byte compatible with the official FoundationDB Python
    binding (``fdb.tuple.pack``).
    """
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
