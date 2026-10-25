"""Exact final-candidate JUnit identities. No authorization or raw evidence output."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import project_public_ci_evidence as public

ERROR = 'FINAL_INTEGRATION_JUNIT_REJECTED'


def need(condition):
    if not condition:
        raise ValueError(ERROR)


def check(rawbytes, manifest, sha, tree):
    """Return case count only after exact source/identity/status validation."""
    try:
        need(type(rawbytes) is bytes and len(rawbytes) <= public.LIMIT)
        need(all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in (sha, tree)))
        need(type(manifest) is dict and set(manifest) == {'schema', 'sha', 'tree', 'identities', 'allowed_skips'})
        need(type(manifest['schema']) is int and manifest['schema'] == 1)
        need(type(manifest['sha']) is str and type(manifest['tree']) is str)
        need(manifest['sha'] == sha and manifest['tree'] == tree)
        for key in ('identities', 'allowed_skips'):
            values = manifest[key]
            need(type(values) is list)
            need(all(type(v) is str and re.fullmatch('case_[0-9a-f]{64}', v) for v in values))
            need(values == sorted(set(values)))
        expected = set(manifest['identities'])
        allowed = set(manifest['allowed_skips'])
        need(bool(expected) and allowed <= expected)
        projected = public.project(rawbytes, set())
        public.validate_junit(projected, set())
        cases = list(public.parse(projected).iter('testcase'))
        need({c.get('name') for c in cases} == expected)
        need(len(cases) == len(expected))
        need(all(c.find('failure') is None and c.find('error') is None for c in cases))
        need(all(c.get('name') in allowed for c in cases if c.find('skipped') is not None))
        return len(cases)
    except Exception:
        raise ValueError(ERROR) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xml')
    parser.add_argument('expected_json')
    args = parser.parse_args()
    try:
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True, stderr=subprocess.DEVNULL).strip()
        raw = public.read(args.xml)
        manifest = public.decode(public.read(args.expected_json))
        count = check(raw, manifest, sha, tree)
    except Exception:
        print('BLOCKED: ' + ERROR, file=sys.stderr)
        return 1
    print('PASS: exact synthetic JUnit identities=' + str(count) + '; authorization=NONE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
