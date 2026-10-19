"""Fail audit if mandatory PostgreSQL cases disappeared or skipped."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('junit')
parser.add_argument('--output', default='junit-proof.json')
args = parser.parse_args()
cases = list(ET.parse(args.junit).iter('testcase'))
assert len(cases) >= 500, f'insufficient baseline collection: {len(cases)}'
assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
allowed = {'test_failed_pip_install_never_reports_success_or_creates_launcher'}
skipped = [c.attrib for c in cases if c.find('skipped') is not None]
assert all(c['name'] in allowed for c in skipped), skipped
storage = [c for c in cases if c.get('classname', '').endswith('test_storage_ingestion_postgres')]
assert len(storage) == 9, f'expected 9 storage PostgreSQL cases, found {len(storage)}'
assert not any(c.find('skipped') is not None for c in storage)
proof = dict(total=len(cases), skipped=skipped, required_postgres_executed=len(storage), status='PASS')
Path(args.output).write_text(json.dumps(proof, indent=2))
print(json.dumps(proof, indent=2))
