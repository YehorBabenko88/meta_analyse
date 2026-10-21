import pytest
from decimal import Decimal
from meta_analyse.flow_bridge import FlowBridge
from meta_analyse.tape_velocity import TapeSnapshot

@pytest.mark.asyncio
async def test_flow_quality_requires_both_feeds_and_goes_stale():
    bridge=FlowBridge()
    tape=TapeSnapshot(Decimal(1),Decimal(100),Decimal(100),Decimal(0),Decimal(0),True)
    await bridge.update("BTCUSDT",{"poc":"100","delta":"2","trusted":True},tape)
    assert bridge.snapshot()[0].quality=="UNVERIFIED"
    bridge.trade_observed("BTCUSDT")
    assert bridge.snapshot()[0].quality=="UNVERIFIED"
    bridge.book_observed("BTCUSDT")
    assert bridge.snapshot()[0].quality=="PROVISIONAL"
    bridge.invalidate(["BTCUSDT"])
    assert bridge.snapshot()[0].quality=="UNVERIFIED"
