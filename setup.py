#!/usr/bin/env python

import os
import sys

from setuptools import setup, find_packages


os.chdir(os.path.dirname(sys.argv[0]) or ".")


setup(
    name="asyncio-foundationdb",
    version='0.7.0',
    description="asyncio drivers for FoundationDB",
    long_description=open("README.rst", "rt").read(),
    url="https://github.com/amirouche/asyncio-foundationdb/",
    author="Amirouche BOUBEKKI",
    author_email="amirouche.boubekki@gmail.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    package_data={'found': ['*.h']},
    install_requires=[
        "cffi>=1.0.0",
        "foundationdb",
        "immutables==0.6",
        "six==1.11.0"
    ],
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["./found/build_found.py:ffi"],
)
