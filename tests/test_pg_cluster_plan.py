"""Pure offline PlanOnly checks; never touch a PostgreSQL cluster."""
import pytest
from meta_analyse.pg_cluster_plan import ClusterPlan, PlanRefused, plan_only

ROOT = r"C:\Users\Administrator\AppData\Local"
NEW = ROOT + r"\MetaAnalyseCommissioning\session_001\pgdata"


def plan(**changes):
    args = dict(data_directory=NEW, role="meta_commission_test",
                database="meta_commission_test")
    args.update(changes)
    return ClusterPlan(**args)


def test_plan_only_has_no_actions_and_requires_gates():
    result = plan_only(plan(), localappdata=ROOT)
    assert result["mode"] == "PLAN_ONLY"
    assert result["actions_executed"] == 0
    assert result["requires_g0"] and result["requires_g1"]


@pytest.mark.parametrize("bad", [
    {"port": 5432}, {"port": 5433}, {"host": "0.0.0.0"},
    {"host": "::1"}, {"database": "postgres"}, {"role": "postgres"},
    {"role": "meta_commission_bootstrap"},
])
def test_invalid_plan_refused(bad):
    with pytest.raises(PlanRefused):
        plan_only(plan(**bad), localappdata=ROOT)


@pytest.mark.parametrize("path", [
    r"C:\Program Files\PostgreSQL\18\data",
    r"C:\Users\Administrator\AppData\Local\MetaAnalyseCommissioningElsewhere\pgdata",
    ROOT + r"\MetaAnalyseCommissioning\..\unsafe",
])
def test_unsafe_directory_refused(path):
    with pytest.raises(PlanRefused):
        plan_only(plan(data_directory=path), localappdata=ROOT)


def test_existing_pgdata_collision_refused():
    with pytest.raises(PlanRefused):
        plan_only(plan(), localappdata=ROOT,
                  existing_data_directories=(NEW,))
    with pytest.raises(PlanRefused):
        plan_only(plan(), localappdata=ROOT,
                  existing_data_directories=(ROOT + r"\MetaAnalyseCommissioning",))
