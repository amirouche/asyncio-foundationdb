import os
from cffi import FFI


ffi = FFI()
with open(os.path.join(os.path.dirname(__file__), 'fdb_c.h')) as f:
    SOURCE = f.read()

ffi.set_source("found._fdb_c", SOURCE, libraries=['fdb_c'])
ffi.cdef(SOURCE)


if __name__ == '__main__':
    ffi.compile(verbose=True)
