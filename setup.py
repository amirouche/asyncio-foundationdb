#!/usr/bin/env python

import os
import sys

from setuptools import setup, find_packages

os.chdir(os.path.dirname(sys.argv[0]) or ".")

from found import VERSION


setup(
    name="python-found",
    version=VERSION,
    description="asyncio drivers for FoundationDB",
    url="https://github.com/amirouche/found/",
    author="Amirouche BOUBEKKI",
    author_email="amirouche.boubekki@gmail.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    install_requires=["cffi>=1.0.0", "async_generator"],
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["./found/build_found.py:ffi"],
)
