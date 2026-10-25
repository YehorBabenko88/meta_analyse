"""Fail closed on missing, skipped or unexpectedly small integration test suites."""
import argparse
import sys
import xml.etree.ElementTree as ET

def main():
    p = argparse.ArgumentParser()
    p.add_argument("xml")
    p.add_argument("--minimum", type=int, required=True)
    p.add_argument("--require", action="append", default=[])
    p.add_argument("--allow-skip", action="append", default=[])
    p.add_argument("--require-exact", action="append", default=[])
    p.add_argument("--require-identity", action="append", default=[],
                   help="Required exact classname.testname, unskipped and unique")
    a = p.parse_args()
    # Reject DTD/entities rather than trusting XML parser-specific behaviour.\n    from pathlib import Path\n    raw = Path(a.xml).read_bytes()\n    if len(raw) > 32 * 1024 * 1024:\n        raise SystemExit("JUnit report exceeds 32 MiB limit")\n    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():\n        raise SystemExit("DTD and entities are forbidden in JUnit evidence")\n    root = ET.fromstring(raw)\n    if root.tag not in ("testsuite", "testsuites"):\n        raise SystemExit("Invalid JUnit root element")
    cases = list(root.iter("testcase"))
    names = [f"{c.get('classname', '')}.{c.get('name', '')}" for c in cases]
    identities = [(c.get("classname", ""), c.get("name", "")) for c in cases]
    duplicates = len(identities) - len(set(identities))
    declared = root.get("tests")
    if declared is None:
        suites = list(root.iter("testsuite"))
        if len(suites) == 1:
            declared = suites[0].get("tests")
    if declared is not None:
        try:
            count_mismatch = int(declared) != len(cases)
        except ValueError:
            count_mismatch = True
    else:
        count_mismatch = True
    failures = [c for c in cases if any(c.find(t) is not None for t in ("failure", "error"))]
    skipped = [c for c in cases if c.find("skipped") is not None]
    missing = [pattern for pattern in a.require if not any(pattern in name for name in names)]
    exact_missing = [name for name in a.require_exact if not any(c.get("name", "").split("[", 1)[0] == name for c in cases)]
    identity_missing = []
    identity_skipped = []
    for required in a.require_identity:
        matched = [c for c in cases if
                   f"{c.get('classname', '')}.{c.get('name', '').split('[', 1)[0]}" == required]
        if len(matched) != 1:
            identity_missing.append(required)
        elif matched[0].find("skipped") is not None:
            identity_skipped.append(required)
    for required in identity_missing:
        print(f"MISSING OR DUPLICATE REQUIRED IDENTITY: {required}", file=sys.stderr)
    for required in identity_skipped:
        print(f"REQUIRED IDENTITY SKIPPED: {required}", file=sys.stderr)
    print(f"collected={len(cases)} skipped={len(skipped)} failed={len(failures)}")
    for case in skipped:
        print(f"SKIP: {case.get('classname')}.{case.get('name')}: {case.find('skipped').get('message')}")
    for pattern in missing:
        print(f"MISSING REQUIRED: {pattern}", file=sys.stderr)
    unexpected = [c for c in skipped if not any(token == c.get("name", "").split("[", 1)[0] for token in a.allow_skip)]
    skipped_required = [
        name for name in a.require_exact
        if any(c.get("name", "").split("[", 1)[0] == name and c.find("skipped") is not None for c in cases)
    ]
    for name in skipped_required:
        print(f"REQUIRED TEST SKIPPED: {name}", file=sys.stderr)
    for name in exact_missing:
        print(f"MISSING EXACT TEST: {name}", file=sys.stderr)
    if duplicates:
        print(f"DUPLICATE TESTCASES: {duplicates}", file=sys.stderr)
    if count_mismatch:
        print(f"INVALID TEST COUNT: declared={declared} actual={len(cases)}", file=sys.stderr)
    if len(cases) < a.minimum or unexpected or failures or missing or exact_missing or duplicates or count_mismatch or skipped_required or identity_missing or identity_skipped:
        sys.exit(1)

if __name__ == "__main__":
    main()
