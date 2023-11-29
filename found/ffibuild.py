import os

from cffi import FFI

ffi = FFI()
with open(os.path.join(os.path.dirname(__file__), "fdb_c.h")) as f:
    ffi.set_source(
        "found._fdb",
        f.read(),
        libraries=["fdb_c"],
        include_dirs=[
            "/nix/store/rlnbpd2m5dm09y66gcsgd8cwml3pdfdh-foundationdb-7.1.30-lib/include/"
        ],
        library_dirs=[
            "/nix/store/rlnbpd2m5dm09y66gcsgd8cwml3pdfdh-foundationdb-7.1.30-lib/lib/"
        ],
    )

# TODO: replace fdb_c2.h with what it is, what it's useful for
with open(os.path.join(os.path.dirname(__file__), "fdb_c2.h")) as f:
    ffi.cdef(f.read())


def main(*args, **kwargs):
    ffi.compile(verbose=True)


if __name__ == "__main__":
    main()
