"""Fail-closed offline JUnit publication profile; never echo untrusted content."""
import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

class StrictBuilder(ET.TreeBuilder):
    def doctype(self, *args):
        raise ValueError("DTD")
    def comment(self, *args):
        raise ValueError("COMMENT")
    def pi(self, *args):
        raise ValueError("PI")

ALLOWED = {
    "testsuites": {"name", "tests", "errors", "failures", "skipped", "time"},
    "testsuite": {"name", "tests", "errors", "failures", "skipped", "time", "timestamp"},
    "testcase": {"name", "classname", "time"},
}
def inspect_file(path):
    try:
        if path.is_symlink() or not path.is_file():
            return False
        with path.open("rb") as stream:
            data = stream.read(8 * 1024 * 1024 + 1)
        if not 0 < len(data) <= 8 * 1024 * 1024:
            return False
        root = ET.fromstring(data, parser=ET.XMLParser(target=StrictBuilder()))
        if root.tag not in ("testsuites", "testsuite"):
            return False
        cases = []
        def visit(node):
            if node.tag == "testsuites":
                if set(node.attrib) - ALLOWED["testsuites"] or not list(node):
                    return False
                return all(child.tag == "testsuite" and visit(child) for child in node)
            if node.tag == "testsuite":
                if set(node.attrib) - ALLOWED["testsuite"]:
                    return False
                own = [c for c in node if c.tag == "testcase"]
                nested = [c for c in node if c.tag == "testsuite"]
                if len(own) + len(nested) != len(node):
                    return False
                if any(not visit(c) for c in own + nested):
                    return False
                count = sum(1 for _ in node.iter("testcase"))
                return count > 0 and node.get("tests") == str(count)
            if node.tag == "testcase":
                if set(node.attrib) - ALLOWED["testcase"] or len(node):
                    return False
                if not node.get("name") or not node.get("classname"):
                    return False
                cases.append((node.get("classname"), node.get("name")))
                return True
            return False
        if not visit(root):
            return False
        if any((n.text or "").strip() or (n.tail or "").strip() for n in root.iter()):
            return False
        return bool(cases) and len(cases) == len(set(cases))
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
