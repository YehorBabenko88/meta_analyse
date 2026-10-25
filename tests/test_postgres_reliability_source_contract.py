"""Pure source-level reliability contracts: no PostgreSQL connection or host probes."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "meta_analyse"


def test_archive_batch_checkpoint_share_transaction_scope():
    tree = ast.parse((SOURCE / "archive_db_import.py").read_text(encoding="utf-8"))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name == "import_verified_archive")
    flush = next(node for node in ast.walk(fn)
                 if isinstance(node, ast.FunctionDef) and node.name == "flush")
    contexts = [node for node in ast.walk(flush) if isinstance(node, ast.With)]
    assert any(any(isinstance(item.context_expr, ast.Call)
                   and isinstance(item.context_expr.func, ast.Attribute)
                   and item.context_expr.func.attr == "transaction"
                   for item in block.items) for block in contexts)
    sql = "\n".join(node.value for node in ast.walk(flush)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str))
    assert "INSERT INTO meta_analyse.historical_trades" in sql
    assert "UPDATE meta_analyse.archive_import_checkpoints" in sql


def test_drain_shields_worker_and_reads_result_after_completion():
    tree = ast.parse((SOURCE / "write_drain.py").read_text(encoding="utf-8"))
    fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
              and node.name == "drain_thread_write")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    assert any(isinstance(n.func, ast.Attribute)
               and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "asyncio"
               and n.func.attr == "shield" for n in calls)
    assert any(isinstance(n.func, ast.Attribute)
               and n.func.attr == "result" for n in calls)


def test_history_reader_never_claims_verified_coverage():
    source = (SOURCE / "flow_history_storage.py").read_text(encoding="utf-8")
    assert 'status: str = "UNVERIFIED"' in source
    assert "limit + 1" in source
    assert "truncated = len(rows) > limit" in source
