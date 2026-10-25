"""Read-only fake observations; no database or physical durability proof."""
from datetime import datetime, timedelta, timezone
import pytest
from meta_analyse.pg_checkpoint_witness import capture_witness, verify_witness
from meta_analyse.pg_cluster_attestation import ExpectedCluster

EXPECTED = ExpectedCluster("12345678901234567890", "meta_commission_test", "meta_commission_test")
IDENTITY = (EXPECTED.database, EXPECTED.role, 180001, "127.0.0.1", 55480, EXPECTED.system_identifier, True)
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)

class Fake:
    def __init__(self, row=(True, "0/20", "0/10", "0/10", "0/8", 1), identity=IDENTITY, error=False):
        self.row, self.identity, self.error = row, identity, error
        self.statements = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def transaction(self):
        from contextlib import nullcontext
        return nullcontext()
    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        if "pg_control_checkpoint()" in sql and self.error:
            raise PermissionError("private details")
        row = self.identity if "pg_control_system()" in sql else self.row
        class Result:
            def fetchone(self): return row
        return Result()

def capture(conn=None, **changes):
    args=dict(symbol="BTCUSDT", update_id=1, sequence=2, now=NOW)
    args.update(changes)
    return capture_witness(lambda: conn or Fake(), EXPECTED, **args)

def test_capture_then_later_checkpoint_and_flush_observed_read_only():
    first=Fake()
    result=capture(first)
    assert result.status == "PENDING"
    assert result.ticket is not None
    later=Fake((True, "0/40", "0/40", "0/40", "0/30", 1))
    assert verify_witness(lambda: later, EXPECTED, result.ticket, now=NOW+timedelta(seconds=1)).status == "OBSERVED"
    for conn in (first,later):
        assert "pg_control_system()" in conn.statements[1][0]
        for sql,params in conn.statements:
            assert sql.strip().upper().startswith(("SELECT", "SET TRANSACTION READ ONLY"))
        assert conn.statements[-1][1] == ("BTCUSDT",1,2)
    assert "BTCUSDT" not in repr(result)
    assert EXPECTED.system_identifier not in repr(result.ticket)

@pytest.mark.parametrize("row,status", [
    ((False,"0/40","0/40","0/40","0/30",1),"BLOCKED"),
    ((True,"0/40","0/10","0/40","0/30",1),"PENDING"),
    ((True,"0/40","0/40","0/10","0/8",1),"PENDING"),
    ((True,"0/40","0/40","0/40","0/10",1),"PENDING"),
    ((True,"0/40","0/40","0/40","0/30",2),"BLOCKED"),
    ((True,"0/40","0/40","0/10","0/30",1),"BLOCKED"),
])
def test_later_missing_lag_and_timeline_fail_closed(row,status):
    ticket=capture().ticket
    assert verify_witness(lambda: Fake(row),EXPECTED,ticket,now=NOW).status == status

@pytest.mark.parametrize("lsn", ["0/020", "0/gg", "0/20 ", "0/100000000", "000/20", "0/aa", None, 32, True])
def test_noncanonical_lsn_blocked(lsn):
    assert capture(Fake((True,lsn,"0/10","0/10","0/8",1))).status == "BLOCKED"

@pytest.mark.parametrize("changes", [dict(update_id=True),dict(update_id=-1),dict(sequence=2**63),dict(symbol=""),dict(symbol="private\nvalue")])
def test_invalid_row_identity_blocks_before_factory(changes):
    called=[]
    args=dict(symbol="BTCUSDT",update_id=1,sequence=2,now=NOW)
    args.update(changes)
    assert capture_witness(lambda: called.append(True),EXPECTED,**args).status == "BLOCKED"
    assert called == []

def test_wrong_cluster_and_permission_denial_block():
    assert capture(Fake(identity=("postgres",*IDENTITY[1:]))).status == "BLOCKED"
    assert capture(Fake(error=True)).status == "BLOCKED"
    ticket=capture().ticket
    assert verify_witness(lambda: Fake(error=True),EXPECTED,ticket,now=NOW).status == "BLOCKED"

@pytest.mark.parametrize("seconds", [-1,301])
def test_future_or_stale_ticket_blocks_before_factory(seconds):
    ticket=capture().ticket
    called=[]
    assert verify_witness(lambda: called.append(True),EXPECTED,ticket,now=NOW+timedelta(seconds=seconds)).status == "BLOCKED"
    assert called == []

def test_mismatched_expected_cluster_blocks_before_factory():
    ticket=capture().ticket
    other=ExpectedCluster("999",EXPECTED.database,EXPECTED.role)
    called=[]
    assert verify_witness(lambda: called.append(True),other,ticket,now=NOW).status == "BLOCKED"
    assert called == []

@pytest.mark.parametrize("row", [None, (), (True,), (1,"0/20","0/10","0/10","0/8",1), (True,"0/20","0/10","0/10","0/8",True)])
def test_malformed_observation_blocked(row):
    assert capture(Fake(row)).status == "BLOCKED"


def test_ticket_is_immutable_and_verified_cluster_is_freshly_attested():
    from dataclasses import FrozenInstanceError
    ticket=capture().ticket
    with pytest.raises(FrozenInstanceError):
        ticket.marker="0/1"
    wrong=Fake(identity=("postgres",*IDENTITY[1:]))
    result=verify_witness(lambda: wrong,EXPECTED,ticket,now=NOW)
    assert result.status == "BLOCKED"
    assert not any("pg_control_checkpoint()" in sql for sql,_ in wrong.statements)
    assert result.ticket is None


def test_ticket_expiry_boundary_and_lsn_high_word_numeric_comparison():
    ticket=capture(Fake((True,"1/0","0/FFFFFFFF","0/FFFFFFFE","0/FFFFFFFD",1))).ticket
    later=Fake((True,"1/20","1/10","1/10","1/1",1))
    assert verify_witness(lambda: later,EXPECTED,ticket,now=NOW+timedelta(seconds=300)).status == "OBSERVED"


@pytest.mark.parametrize("now", [datetime(2026,10,25),"private timestamp",False])
def test_invalid_clock_blocks_before_factory(now):
    called=[]
    assert capture_witness(lambda: called.append(True),EXPECTED,"BTCUSDT",1,2,now=now).status == "BLOCKED"
    assert called == []


def test_factory_error_suppresses_private_details():
    def failed(): raise RuntimeError("private dsn password")
    result=capture_witness(failed,EXPECTED,"BTCUSDT",1,2,now=NOW)
    assert repr(result) == "WitnessResult(status='BLOCKED')"


def test_missing_capture_row_never_returns_ticket():
    result=capture(Fake((False,"0/20","0/10","0/10","0/8",1)))
    assert result.status == "BLOCKED"
    assert result.ticket is None
