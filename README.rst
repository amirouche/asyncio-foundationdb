asyncio-foundationdb
####################

.. image:: https://api.travis-ci.com/amirouche/asyncio-foundationdb.svg?branch=master

.. image:: https://codecov.io/gh/amirouche/found/branch/master/graph/badge.svg

asyncio drivers for foundationdb tested with CPython 3.5+

.. code:: python

	  In [1]: import found
	  In [2]: import asyncio
	  In [3]: found.api_version(600)
	  In [4]: loop = asyncio.get_event_loop()
	  In [5]: db = loop.run_until_complete(found.open())
	  In [6]: tr = db._create_transaction()
	  In [7]: loop.run_until_complete(tr.get(b'hello'))
	  In [8]: tr.set(b'hello', b'world')
	  In [9]: loop.run_until_complete(tr.get(b'hello'))
	  Out[9]: b'world'

Also ``@transactional`` is supported.

Getting started
===============

::

   pip install asyncio-foundationdb

Documentation
=============

You must read the `official python api
documentation <https://apple.github.io/foundationdb/api-python.html>`_,
it is awesome.

In general, the asyncio bindings are the same except there is
``async`` and ``await`` that must be added here and there.

Here are differences with the synchronous bindings:

- no shorthand syntax like: ``foo[b'bar']``
- You can do ``value is None`` instead of ``value == None``
- ``Transaction.get_range`` returns a list of ``(key, value)`` pairs

If something is missing it's a bug, `please fill an
issue <https://github.com/amirouche/asyncio-foundationdb/issues>`_.
