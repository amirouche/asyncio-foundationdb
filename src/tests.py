import faulthandler
import pytest

from found import v510 as found


faulthandler.enable()


# @pytest.mark.asyncio
# async def test_smoke():
#     async def wrapper():
#         db = await found.open()
#         tx = db._create_transaction()
#         tx.set(b'key', b'value')
#         await tx.commit()

#         tx = db._create_transaction()
#         out = await tx.get(b'key')
#         await tx.commit()
#         return out

#     out = await wrapper()
#     assert out[:] == b'value'


def test_pack_unpack():
    value = ((1, ('abc',)), ('d', 'e', 'f'))
    assert found.unpack(found.pack(value)) == value


@pytest.mark.asyncio
async def test_range():
    db = await found.open()
    tx = db._create_transaction()
    for number in range(10):
        tx.set(found.pack((number,)), found.pack((str(number),)))
    await tx.commit()

    tx = db._create_transaction()
    out = list()
    async for item in tx.get_range(found.pack((1,)), found.pack((8,))):
        out.append(item)
    await tx.commit()

    for (key, value), index in zip(out, range(10)[1:-1]):
        assert found.unpack(key)[0] == index
        assert found.unpack(value)[0] == str(index)
