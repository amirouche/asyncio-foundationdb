import os
from cffi import FFI


ffi = FFI()
with open(os.path.join(os.path.dirname(__file__), "fdb_c.h")) as f:
    ffi.set_source("found._fdb", f.read(), libraries=["fdb_c"])


# TODO: replace fdb_c2.h with what it is, what it's useful for
with open(os.path.join(os.path.dirname(__file__), "fdb_c2.h")) as f:
    ffi.cdef(f.read())


if __name__ == "__main__":
    ffi.compile(verbose=True)
