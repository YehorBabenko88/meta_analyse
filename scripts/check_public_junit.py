"""Fail-closed offline public JUnit profile; never echo untrusted content."""
import argparse
from pathlib import Path
import re
import stat
import sys
import xml.etree.ElementTree as ET

MAX_BYTES = 8 * 1024 * 1024
COUNTERS = ("tests", "errors", "failures", "skipped")

class StrictBuilder(ET.TreeBuilder):
    def doctype(self, *args):
        raise ValueError("DTD")
    def comment(self, *args):
        raise ValueError("COMMENT")
    def pi(self, *args):
        raise ValueError("PI")

def safe_path(path):
    """Reject links and Windows reparse points in the entire lexical path."""
    path = Path(path).absolute()
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return False
    return path.is_file()

def inspect_file(path):
    try:
        path = Path(path)
        if not safe_path(path):
            return False
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if not 0 < len(data) <= MAX_BYTES:
            return False
        root = ET.fromstring(data, parser=ET.XMLParser(target=StrictBuilder()))
        cases = set()
        def visit(node, depth=1):
            if depth > 64 or (node.text or "").strip() or (node.tail or "").strip():
                raise ValueError("CONTENT")
            if node.tag in ("testsuites", "testsuite"):
                if set(node.attrib) != {"name", *COUNTERS} or node.get("name") != "public-ci" or not len(node):
                    raise ValueError("SUITE")
                totals = [0, 0, 0, 0]
                for child in node:
                    if child.tag not in (("testsuite",) if node.tag == "testsuites" else ("testcase",)):
                        raise ValueError("CHILD")
                    values = visit(child, depth + 1)
                    totals = [a + b for a, b in zip(totals, values)]
                if any(node.get(key) != str(value) for key, value in zip(COUNTERS, totals)):
                    raise ValueError("COUNTERS")
                return totals
            if node.tag != "testcase" or set(node.attrib) != {"classname", "name"}:
                raise ValueError("CASE")
            identity = node.get("name", "")
            if node.get("classname") != "public.tests" or re.fullmatch(r"case_[0-9a-f]{64}", identity) is None or identity in cases:
                raise ValueError("IDENTITY")
            cases.add(identity)
            if len(node) > 1:
                raise ValueError("STATUS")
            totals = [1, 0, 0, 0]
            for child in node:
                if child.tag not in ("error", "failure", "skipped") or child.attrib != {"message": "Details omitted"} or len(child) or child.text or (child.tail or "").strip():
                    raise ValueError("STATUS")
                totals[{"error": 1, "failure": 2, "skipped": 3}[child.tag]] = 1
            return totals
        if root.tag not in ("testsuites", "testsuite"):
            return False
        return bool(visit(root)[0])
    except (ET.ParseError, ValueError, OSError, TypeError, OverflowError, RecursionError):
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    if not all(inspect_file(path) for path in args.paths):
        print("PUBLIC_JUNIT_REJECTED", file=sys.stderr)
        return 1
    print("PUBLIC_JUNIT_STRUCTURE_PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
