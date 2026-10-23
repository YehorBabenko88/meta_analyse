"""Fail closed on raw/host-bearing JUnit before public CI artifact publication.

This is a conservative *refusal* gate, not a sanitizer. Keep raw XML/logs
private and publish only separately projected reports where necessary.
"""
import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

FORBIDDEN = {"hostname", "host", "machine", "node", "runner", "username",
             "user", "computername", "computer", "cwd", "file", "path"}
ALLOWED_ATTRIBUTES = {
    "testsuites": {"name", "tests", "errors", "failures", "skipped", "time"},
    "testsuite": {"name", "tests", "errors", "failures", "skipped", "time", "timestamp"},
    "testcase": {"name", "classname", "time"},
}
ALLOWED_TAGS = {"testsuites", "testsuite", "testcase", "failure", "error", "skipped"}

def inspect_file(path):
    try:
        if path.is_symlink() or not path.is_file():
            return False
        with path.open("rb") as stream:
            data = stream.read(8 * 1024 * 1024 + 1)
        if not 0 < len(data) <= 8 * 1024 * 1024:
            return False
        # Refuse DTD, processing instructions and comments in this publication path.
        if b"<!DOCTYPE" in data.upper() or b"<!--" in data or b"<?" in data.replace(b"<?xml", b"", 1):
            return False
        root = ET.fromstring(data)
        if root.tag not in ("testsuites", "testsuite"):
            return False
        suites = list(root.iter("testsuite"))
        cases = list(root.iter("testcase"))
        if not suites or not cases:
            return False
        for node in root.iter():
            if node.tag not in ALLOWED_TAGS:
                return False
            if node.tag in ALLOWED_ATTRIBUTES and set(node.attrib) - ALLOWED_ATTRIBUTES[node.tag]:
                return False
            if node.tag in ("failure", "error", "skipped"):
                # Refuse raw traceback, skipped reason, message or arbitrary metadata.
                if node.attrib or (node.text or "").strip() or len(node):
                    return False
            if any(key.casefold() in FORBIDDEN for key in node.attrib):
                return False
            if (node.text or "").strip() or (node.tail or "").strip():
                return False
        if len(cases) != sum(int(s.attrib.get("tests", -1)) for s in suites if not list(s.iter("testsuite"))):
            # Nested JUnit: only leaf suites contribute counts.
            return False
        if len({(c.get("classname"), c.get("name")) for c in cases}) != len(cases):
            return False
        return True
    except (ET.ParseError, ValueError, OSError, TypeError, OverflowError, RecursionError):
        return False

def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", type=Path)
    args = p.parse_args()
    if not all(inspect_file(path) for path in args.paths):
        print("PUBLIC_JUNIT_REJECTED", file=sys.stderr)
        return 1
    print("PUBLIC_JUNIT_STRUCTURE_PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
