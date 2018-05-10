import faulthandler
import pytest
from found import v510 as fdb


faulthandler.enable()


@pytest.mark.asyncio
async def test_smoke():
    async def wrapper():
        db = await fdb.open()
        tx = db._create_transaction()
        tx.set(b'key', b'value')
        await tx.commit()

        tx = db._create_transaction()
        out = await tx.get(b'key')
        await tx.commit()
        return out

    out = await wrapper()
    assert out[:] == b'value'
