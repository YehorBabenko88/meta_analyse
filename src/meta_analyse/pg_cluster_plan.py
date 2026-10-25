"""Pure PlanOnly guard for an isolated PostgreSQL commissioning cluster.

No process invocation, network access, filesystem writes, or DB connections.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PureWindowsPath


class PlanRefused(ValueError):
    pass


@dataclass(frozen=True)
class ClusterPlan:
    data_directory: str
    role: str
    database: str
    port: int = 55480
    host: str = "127.0.0.1"


def plan_only(plan: ClusterPlan, *, localappdata: str, existing_data_directories: tuple[str, ...] = ()) -> dict:
    if not isinstance(plan, ClusterPlan):
        raise PlanRefused("INVALID_PLAN")
    if type(plan.port) is not int or plan.port != 55480 or plan.host != "127.0.0.1":
        raise PlanRefused("RESERVED_PORT_OR_HOST")
    if (not isinstance(plan.role, str) or not plan.role.startswith("meta_commission_")
            or plan.role == "meta_commission_bootstrap" or plan.database != plan.role
            or not all(c.isascii() and (c.islower() or c.isdigit() or c == "_") for c in plan.role)):
        raise PlanRefused("INVALID_DEDICATED_ROLE")
    if not isinstance(localappdata, str) or not isinstance(plan.data_directory, str):
        raise PlanRefused("INVALID_DIRECTORY")
    root = PureWindowsPath(localappdata) / "MetaAnalyseCommissioning"
    data = PureWindowsPath(plan.data_directory)
    def key(p):
        return str(p).casefold().rstrip("\\")
    root_key, data_key = key(root), key(data)
    if (not root.is_absolute() or not data.is_absolute()
            or not data_key.startswith(root_key + "\\")
            or ".." in data.parts or ":" in str(data)[2:]
            or any(key(PureWindowsPath(x)) == data_key
                   or data_key.startswith(key(PureWindowsPath(x)) + "\\")
                   or key(PureWindowsPath(x)).startswith(data_key + "\\")
                   for x in existing_data_directories)):
        raise PlanRefused("DATA_DIRECTORY_NOT_ISOLATED")
    return {
        "mode": "PLAN_ONLY",
        "host": plan.host,
        "port": plan.port,
        "database": plan.database,
        "role": plan.role,
        "data_directory": str(data),
        "actions_executed": 0,
        "requires_g0": True,
        "requires_g1": True,
        "rollback": "STOP_NEW_CLUSTER_ONLY_AFTER_EXACT_PGDATA_OWNERSHIP_ATTESTATION",
    }
