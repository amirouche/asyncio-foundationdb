import logging
from uuid import uuid4

from immutables import Map

from found import fdb


log = logging.getLogger(__name__)


class SparkyException(Exception):
    pass


PREFIX_DATA = b'\x00'
PREFIX_UUID = b'\x01'


class var:

    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<var %r>' % self.name


def bind(pattern, triple, binding):
    for target, value in zip(pattern, triple):
        if isinstance(target, var):
            try:
                bound = binding[target.name]
            except KeyError:
                binding = binding.set(target.name, value)
                continue
            else:
                if bound == value:
                    continue
                else:
                    return None
        else:
            if target == value:
                continue
            else:
                return None
    return binding


class Sparky:

    __slots__ = ('_prefix',)

    def __init__(self, prefix):
        self._prefix = prefix

    @fdb.transactional
    async def _random_uid(self, tr):
        uid = uuid4()
        key = fdb.pack((self._prefix, PREFIX_UUID, uid))
        value = await tr.get(key)
        if value is None:
            tr.set(key, b'')
            return uid
        raise SparkyException('Unlikely Error!')

    @fdb.transactional
    async def all(self, tr):
        start = fdb.pack((self._prefix, PREFIX_DATA))
        end = fdb.strinc(start)
        msg = "fetching everything between start=%r and end=%r"
        log.debug(msg, start, end)
        out = []
        items = await tr.range(start, end)
        for key, _ in items:
            _, _, subject, predicate, object = fdb.unpack(key)
            out.append((subject, predicate, object))
        return out

    @fdb.transactional
    async def add(self, tr, *triples):
        for triple in triples:
            subject, predicate, object = triple
            key = fdb.pack((self._prefix, PREFIX_DATA, subject, predicate, object))
            tr.set(key, b'')

    @fdb.transactional
    async def remove(self, tr, *triples):
        for triple in triples:
            key = fdb.pack((self._prefix, PREFIX_DATA, *triple))
            tr.clear(key)

    @fdb.transactional
    async def where(self, tr, pattern, *patterns):
        seed = []
        triples = await self.all(tr)
        # poor man do-while
        for triple in triples:
            binding = bind(pattern, triple, Map())
            if binding is not None:
                seed.append(binding)
        bindings = seed
        # while
        for pattern in patterns:  # one
            next_bindings = []
            for binding in bindings:  # two
                triples = await self.all(tr)
                for triple in triples:  # three
                    new = bind(pattern, triple, binding)
                    if new is not None:
                        next_bindings.append(new)
            bindings = next_bindings
        return bindings
