"""
ffibuild.py — CFFI build script for found._fdb

Usage:
    python ffibuild.py

Environment variables (all optional):
    FDB_INCLUDE_DIR   — path to directory containing fdb_c.h
                        defaults to /usr/include or /usr/local/include
    FDB_LIB_DIR       — path to directory containing libfdb_c.so / .dylib
                        defaults to letting the linker find it on LD_LIBRARY_PATH

Why two header files?
    fdb_c.h   — passed verbatim to set_source() so the C compiler sees the
                real FDB declarations and generates correct ABI glue.
    fdb_c2.h  — passed to ffi.cdef() so CFFI knows what to expose to Python.
                This is a cleaned-up subset of fdb_c.h with all preprocessor
                directives removed (CFFI's cdef parser does not run cpp).
"""

import os
from cffi import FFI

_here = os.path.dirname(__file__)


def _read(filename):
    with open(os.path.join(_here, filename)) as f:
        return f.read()


def _build_ffi():
    ffi = FFI()

    # --- locate optional user-specified paths ---------------------------------
    include_dirs = []
    library_dirs = []

    fdb_include = os.environ.get("FDB_INCLUDE_DIR")
    if fdb_include:
        include_dirs.append(fdb_include)

    fdb_lib = os.environ.get("FDB_LIB_DIR")
    if fdb_lib:
        library_dirs.append(fdb_lib)

    # --- ABI source (real C header, seen by the C compiler) -------------------
    ffi.set_source(
        "found._fdb",
        _read("fdb_c.h"),
        libraries=["fdb_c"],
        include_dirs=include_dirs,
        library_dirs=library_dirs,
    )

    # --- API declarations (seen by CFFI's parser, no preprocessor) -----------
    ffi.cdef(_read("fdb_c2.h"))

    return ffi


ffi = _build_ffi()


def main():
    ffi.compile(verbose=True)


if __name__ == "__main__":
    main()
