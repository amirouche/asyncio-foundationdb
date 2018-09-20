python-found
############

.. image:: https://api.travis-ci.org/amirouche/found.svg?branch=master

.. image:: https://codecov.io/gh/amirouche/found/branch/master/graph/badge.svg

asyncio drivers for foundationdb tested with CPython 3.5+

.. code:: python

    In [1]: import asyncio
    In [2]: from found import v510 as fdb
    In [3]: loop = asyncio.get_event_loop()
    In [4]: db = loop.run_until_complete(fdb.open())
    In [5]: tr = db._create_transaction()
    In [6]: loop.run_until_complete(tr.get(b'hello'))
    In [7]: tr.set(b'hello', b'world')
    In [8]: loop.run_until_complete(tr.get(b'hello'))
    Out[8]: b'world'

Also ``transactional`` is also supported.

Getting started
===============

::

   pip install python-found
