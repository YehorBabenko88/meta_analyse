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
    a = p.parse_args()
    root = ET.parse(a.xml).getroot()
    cases = list(root.iter("testcase"))
    names = [f"{c.get('classname', '')}.{c.get('name', '')}" for c in cases]
    failures = [c for c in cases if any(c.find(t) is not None for t in ("failure", "error"))]
    skipped = [c for c in cases if c.find("skipped") is not None]
    missing = [pattern for pattern in a.require if not any(pattern in name for name in names)]
    print(f"collected={len(cases)} skipped={len(skipped)} failed={len(failures)}")
    for case in skipped:
        print(f"SKIP: {case.get('classname')}.{case.get('name')}: {case.find('skipped').get('message')}")
    for pattern in missing:
        print(f"MISSING REQUIRED: {pattern}", file=sys.stderr)
    unexpected = [c for c in skipped if not any(token in f"{c.get('classname', '')}.{c.get('name', '')}" for token in a.allow_skip)]
    if len(cases) < a.minimum or unexpected or failures or missing:
        sys.exit(1)

if __name__ == "__main__":
    main()
