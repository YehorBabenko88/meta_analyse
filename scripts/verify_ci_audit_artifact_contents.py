#!/usr/bin/env python3
"""Offline, fail-closed content gate for four *extracted* CI-audit artifacts.

Does not fetch GitHub metadata or grant native/physical authorization.
Supply directories downloaded from authenticated exact-run GitHub artifacts;
run/job/attempt authenticity must be independently verified first.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
CASES = re.compile(r"tests\.test_[a-z0-9_]+\Z")
NAME = re.compile(r"test_[a-z0-9_]+(?:\[sha256:[0-9a-f]{64}\])?\Z")
CELLS = (("push", "windows"), ("push", "ubuntu"),
         ("pull_request", "windows"), ("pull_request", "ubuntu"))

def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("DUPLICATE_JSON_KEY")
        value[key] = item
    return value

def reject_constant(_):
    raise ValueError("NONFINITE_JSON")

def verify_cell(directory, sha, tree, event, minimum):
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("MISSING_OR_SYMLINK_ARTIFACT_DIRECTORY")
    expected = {"ci-audit.xml", "source-sha.json"}
    actual = {p.name for p in directory.iterdir()}
    if actual != expected or any(not p.is_file() or p.is_symlink() for p in directory.iterdir()):
        raise ValueError("ARTIFACT_FILE_INVENTORY_MISMATCH")
    source = directory / "source-sha.json"
    junit = directory / "ci-audit.xml"
    if source.stat().st_size > 8192 or not (0 < junit.stat().st_size <= 8 * 1024 * 1024):
        raise ValueError("ARTIFACT_SIZE_INVALID")
    data = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)
    if type(data) is not dict or set(data) != {"sha", "expected_sha", "event", "event_sha", "tree_sha"}:
        raise ValueError("SOURCE_SCHEMA_INVALID")
    if data["sha"] != sha or data["expected_sha"] != sha or data["tree_sha"] != tree or data["event"] != event:
        raise ValueError("SOURCE_BINDING_INVALID")
    if type(data["event_sha"]) is not str or not SHA.fullmatch(data["event_sha"]):
        raise ValueError("EVENT_SHA_INVALID")
    if event == "push" and data["event_sha"] != sha:
        raise ValueError("PUSH_EVENT_SHA_MISMATCH")
    root = ET.parse(junit).getroot()
    if root.tag != "testsuites" or root.attrib != {"name": "synthetic"} or len(root) != 1:
        raise ValueError("JUNIT_ROOT_INVALID")
    suite = root[0]
    if suite.tag != "testsuite" or set(suite.attrib) != {"name", "tests", "errors", "failures", "skipped"} or suite.get("name") != "synthetic-identity":
        raise ValueError("JUNIT_SUITE_INVALID")
    cases = list(suite)
    if len(cases) < minimum or len(cases) != int(suite.get("tests")):
        raise ValueError("JUNIT_COUNT_INVALID")
    if any(suite.get(k) != "0" for k in ("errors", "failures", "skipped")):
        raise ValueError("JUNIT_NONPASS_COUNT")
    identities = set()
    for case in cases:
        if case.tag != "testcase" or set(case.attrib) != {"classname", "name"} or len(case):
            raise ValueError("JUNIT_CASE_INVALID")
        cls, name = case.get("classname"), case.get("name")
        if not CASES.fullmatch(cls) or not NAME.fullmatch(name):
            raise ValueError("JUNIT_IDENTITY_INVALID")
        if (cls, name) in identities:
            raise ValueError("JUNIT_DUPLICATE_IDENTITY")
        identities.add((cls, name))
    if any((n.text or "").strip() or (n.tail or "").strip() for n in root.iter()):
        raise ValueError("JUNIT_UNPROJECTED_CONTENT")
    return identities

def verify(cells, sha, tree, minimum):
    if not SHA.fullmatch(sha) or not SHA.fullmatch(tree) or type(minimum) is not int or minimum < 1:
        raise ValueError("INVALID_EXPECTATIONS")
    if set(cells) != set(CELLS):
        raise ValueError("MISSING_MATRIX_CELL")
    identities = None
    for event, os_name in CELLS:
        current = verify_cell(Path(cells[(event, os_name)]), sha, tree, event, minimum)
        if identities is not None and current != identities:
            raise ValueError("MATRIX_IDENTITY_MISMATCH")
        identities = current
    return len(identities)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sha", required=True)
    p.add_argument("--tree", required=True)
    p.add_argument("--minimum", type=int, default=83)
    for event, os_name in CELLS:
        p.add_argument("--" + event.replace("_", "-") + "-" + os_name, type=Path, required=True)
    a = p.parse_args()
    cells = {(event, os_name): getattr(a, event + "_" + os_name) for event, os_name in CELLS}
    try:
        count = verify(cells, a.sha, a.tree, a.minimum)
    except (ValueError, OSError, ET.ParseError, TypeError, OverflowError) as exc:
        print("CONTENT_GATE_BLOCKED: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"verdict": "CONTENT_PASS_ONLY", "sha": a.sha, "tree": a.tree,
                      "cells": len(CELLS), "identities": count,
                      "authorization": "NONE"}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
