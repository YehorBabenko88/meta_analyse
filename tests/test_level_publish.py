from datetime import datetime, timezone
from decimal import Decimal as D
from meta_analyse.core import Level
from meta_analyse.level_quality import LevelReport
from meta_analyse.level_publish import publication_decision

T=datetime(2026,1,1,tzinfo=timezone.utc)

def test_no_publication_without_verified_connection():
    report=LevelReport((Level(D("100"),"high",T,"H1"),),True,0,"ok")
    assert not publication_decision(report,connection_verified=False,instrument_verified=True).allowed

def test_no_publication_from_unverified_history():
    report=LevelReport((),False,1,"missing")
    assert not publication_decision(report,connection_verified=True,instrument_verified=True).allowed

def test_validated_levels_are_eligible_not_automatically_written():
    report=LevelReport((Level(D("100"),"high",T,"H1"),),True,0,"ok")
    decision=publication_decision(report,connection_verified=True,instrument_verified=True)
    assert decision.allowed and decision.count==1
