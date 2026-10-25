"""Fail-closed, metadata-free public CI evidence projection.

Directory checks bound ordinary races; hostile concurrent directory writers require
an isolated runner workspace. No raw path or diagnostic payload is published.
"""
import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import xml.etree.ElementTree as ET

LIMIT = 8 * 1024 * 1024
SOURCE_KEYS = {'sha', 'expected_sha', 'tree_sha', 'event', 'event_sha'}

def need(ok):
    if not ok:
        raise ValueError('PUBLIC_EVIDENCE_REJECTED')

def safe_path(path):
    path = Path(path)
    need('..' not in path.parts)
    path = path.absolute()
    for item in [*reversed(path.parents), path]:
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400))
    return path

def read(path):
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_size <= LIMIT)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need((before.st_dev, before.st_ino) == (info.st_dev, info.st_ino))
        data = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
    need(len(data) <= LIMIT and (info.st_size, info.st_mtime_ns) == (after.st_size, after.st_mtime_ns))
    safe_path(path)
    need((path.lstat().st_dev, path.lstat().st_ino) == (info.st_dev, info.st_ino))
    return data

def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()

def decode(data):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out)
            out[key] = value
        return out
    def nonfinite(_):
        raise ValueError('PUBLIC_EVIDENCE_REJECTED')
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=nonfinite)

def source_check(source):
    need(isinstance(source, dict) and set(source) == SOURCE_KEYS)
    need(all(isinstance(v, str) and v for v in source.values()))
    for key in ('sha', 'expected_sha', 'tree_sha', 'event_sha'):
        need(re.fullmatch('[0-9a-f]{40}', source[key]) is not None)
    need(source['sha'] == source['expected_sha'])
    need(source['event'] in ('pull_request', 'push', 'workflow_dispatch', 'schedule', 'merge_group'))

def provenance(source):
    source_check(source)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip()
    need(head == source['sha'] and tree == source['tree_sha'])
    need(os.environ.get('GITHUB_SHA') == source['event_sha'])
    need(os.environ.get('GITHUB_EVENT_NAME') == source['event'])
    if source['event'] == 'pull_request':
        event = decode(read(os.environ['GITHUB_EVENT_PATH']))
        need(event['pull_request']['head']['sha'] == head)
    else:
        need(source['event_sha'] == head)
    result = dict(sha=head, tree=tree, event=source['event'], event_sha=source['event_sha'])
    for key, env in [('run_id', 'GITHUB_RUN_ID'), ('run_attempt', 'GITHUB_RUN_ATTEMPT'), ('job', 'GITHUB_JOB')]:
        value = os.environ.get(env, '')
        need(re.fullmatch('[A-Za-z0-9_-]{1,128}' if key == 'job' else '[1-9][0-9]*', value) is not None)
        result[key] = value
    return result

class NoDeclarations(ET.TreeBuilder):
    def doctype(self, *args):
        need(False)

    def comment(self, *args):
        need(False)

    def pi(self, *args):
        need(False)


def parse(data):
    # Only UTF-8 XML is accepted, so alternate encodings cannot hide declarations.
    text = data.decode('utf-8-sig')
    need('\x00' not in text)
    need(not re.search(r'<!|<\?(?!xml\s)', text, re.I))
    root = ET.fromstring(text, parser=ET.XMLParser(target=NoDeclarations()))
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        need(depth <= 64)
        stack.extend((child, depth + 1) for child in node)
    return root

def cases_from(node):
    if node.tag == 'testcase':
        need(bool(node.get('name')) and bool(node.get('classname')))
        need(all(c.tag in ('failure', 'error', 'skipped', 'properties', 'system-out', 'system-err') for c in node))
        need(sum(c.tag in ('failure', 'error', 'skipped') for c in node) <= 1)
        for child in node:
            need(not any(n.tag in ('testcase', 'testsuite', 'testsuites', 'failure', 'error', 'skipped') for n in child.iter() if n is not child))
        return [node]
    need(node.tag in ('testsuite', 'testsuites'))
    result = []
    for child in node:
        if child.tag in ('testsuite', 'testcase'):
            need(node.tag == 'testsuite' or child.tag == 'testsuite')
            result.extend(cases_from(child))
        else:
            need(child.tag in ('properties', 'system-out', 'system-err'))
            need(not any(n.tag in ('testcase', 'testsuite', 'testsuites', 'failure', 'error', 'skipped') for n in child.iter()))
    counts = counters(result)
    for key, value in counts.items():
        if key in node.attrib:
            need(node.get(key) == str(value))
    return result

def counters(cases):
    return dict(tests=len(cases), failures=sum(c.find('failure') is not None for c in cases), errors=sum(c.find('error') is not None for c in cases), skipped=sum(c.find('skipped') is not None for c in cases))

def project(data, seen):
    root = parse(data)
    need(root.tag in ('testsuite', 'testsuites'))
    cases = cases_from(root)
    need(bool(cases))
    outer = ET.Element('testsuites', name='public-ci', **{k: str(v) for k, v in counters(cases).items()})
    out = ET.SubElement(outer, 'testsuite', name='public-ci', **{k: str(v) for k, v in counters(cases).items()})
    for case in cases:
        pair = (case.get('classname'), case.get('name'))
        digest = hashlib.sha256(json_bytes(pair)).hexdigest()
        need(digest not in seen)
        seen.add(digest)
        clean = ET.SubElement(out, 'testcase', classname='public.tests', name='case_' + digest)
        for status in ('failure', 'error', 'skipped'):
            if case.find(status) is not None:
                ET.SubElement(clean, status, message='Details omitted')
    return ET.tostring(outer, encoding='utf-8', xml_declaration=True)

def validate_junit(data, seen):
    root = parse(data)
    need(root.tag == 'testsuites' and len(root) == 1)
    need(data == ET.tostring(root, encoding='utf-8', xml_declaration=True))
    need(root.tag == 'testsuites' and root.attrib == dict(name='public-ci', **{k: str(v) for k, v in counters(list(root[0])).items()}) and len(root) == 1 and not root.text and not root.tail)
    root = root[0]
    need(root.tag == 'testsuite' and set(root.attrib) == {'name', 'tests', 'errors', 'failures', 'skipped'} and root.get('name') == 'public-ci')
    need(len(root) > 0)
    for case in root:
        need(case.tag == 'testcase' and set(case.attrib) == {'classname', 'name'})
        need(case.get('classname') == 'public.tests' and re.fullmatch('case_[0-9a-f]{64}', case.get('name', '')))
        need(case.get('name') not in seen)
        seen.add(case.get('name'))
        need(not case.text and not case.tail and len(case) <= 1)
        for status in case:
            need(status.tag in ('failure', 'error', 'skipped') and status.attrib == {'message': 'Details omitted'})
            need(not status.text and not status.tail and len(status) == 0)
    need(not root.text and not root.tail)
    need(root.attrib == dict(name='public-ci', **{k: str(v) for k, v in counters(list(root)).items()}))

def validate(directory):
    directory = safe_path(directory)
    need(directory.is_dir())
    manifest = decode(read(directory / 'manifest.json'))
    need(set(manifest) == {'schema_version', 'source', 'provenance', 'inputs', 'files'} and type(manifest['schema_version']) is int and manifest['schema_version'] == 1)
    source = decode(read(directory / 'source-sha.json'))
    source_check(source)
    need(source == manifest['source'] and provenance(source) == manifest['provenance'])
    files = manifest['files']
    inputs = manifest['inputs']
    need(isinstance(inputs, dict) and set(inputs) == {'junit', 'mutations', 'postgres'})
    need(all(isinstance(v, list) for v in inputs.values()) and len(inputs['junit']) > 0)
    need(all(isinstance(h, str) and re.fullmatch('[0-9a-f]{64}', h) for v in inputs.values() for h in v))
    need(isinstance(files, dict) and set(files) == {'source-sha.json'} | {f'junit-{i:03d}.xml' for i in range(len(inputs['junit']))} | {f'mutations-{i:03d}.json' for i in range(len(inputs['mutations']))} | {f'postgres-{i:03d}.json' for i in range(len(inputs['postgres']))})
    need({p.name for p in directory.iterdir()} == set(files) | {'manifest.json'})
    seen = set()
    for name, digest in files.items():
        data = read(directory / name)
        need(hashlib.sha256(data).hexdigest() == digest)
        if name.endswith('.xml'):
            validate_junit(data, set())
        elif name.startswith('mutations-'):
            need(mutation_bytes(data) == data)
        elif name.startswith('postgres-'):
            need(postgres_bytes(data) == data)
    return manifest

def mutation_bytes(data):
    # Validate the exact bounded bytes in an exclusive temporary file.
    try:
        from scripts.project_synthetic_artifacts import validate_mutations
    except ModuleNotFoundError:
        from project_synthetic_artifacts import validate_mutations
    fd, name = tempfile.mkstemp(suffix='.json')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        validate_mutations(Path(name))
        value = decode(data)
        need(value.get('survived', 0) == 0 and value.get('inapplicable', 0) == 0)
        return json_bytes(value)
    finally:
        os.unlink(name)

def postgres_bytes(data):
    value = decode(data)
    need(isinstance(value, dict))
    if set(value) == {'server_version'}:
        need(type(value['server_version']) is int and 180000 <= value['server_version'] < 190000)
    else:
        need(value == dict(url='https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip', sha256='E2246BA91D22345BC3D017586C09EDE52D9DF180B1EEB480F050445F1CAD84E2', binary_version='postgres (PostgreSQL) 18.6', scope='disposable GitHub runner only'))
    return json_bytes(value)

def publish(output, source_path, inputs, mutations=(), postgres_versions=()):
    output = safe_path(output)
    need(not output.exists() and output.parent.is_dir() and bool(inputs))
    canonical_inputs = [str(safe_path(path)).casefold() if os.name == 'nt' else str(safe_path(path)) for path in inputs]
    need(len(canonical_inputs) == len(set(canonical_inputs)))
    source = decode(read(source_path))
    receipt = provenance(source)
    stage = Path(tempfile.mkdtemp(prefix='.' + output.name + '-', dir=output.parent))
    try:
        files = {'source-sha.json': json_bytes(source)}
        hashes = []
        seen = set()
        for index, path in enumerate(inputs):
            data = read(path)
            hashes.append(hashlib.sha256(data).hexdigest())
            files[f'junit-{index:03d}.xml'] = project(data, set())
        mutation_hashes = []
        for index, path in enumerate(mutations):
            data = read(path)
            mutation_hashes.append(hashlib.sha256(data).hexdigest())
            files[f'mutations-{index:03d}.json'] = mutation_bytes(data)
        postgres_hashes = []
        for index, path in enumerate(postgres_versions):
            data = read(path)
            postgres_hashes.append(hashlib.sha256(data).hexdigest())
            files[f'postgres-{index:03d}.json'] = postgres_bytes(data)
        manifest = dict(schema_version=1, source=source, provenance=receipt, inputs=dict(junit=hashes, mutations=mutation_hashes, postgres=postgres_hashes), files={k: hashlib.sha256(v).hexdigest() for k, v in files.items()})
        for name, data in files.items():
            (stage / name).write_bytes(data)
        (stage / 'manifest.json').write_bytes(json_bytes(manifest))
        validate(stage)
        safe_path(output)
        need(not output.exists())
        # Windows rename refuses existing targets; POSIX empty-directory replacement
        # is excluded by the isolated-workspace concurrent-writer precondition.
        os.rename(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--source')
    parser.add_argument('--junit', action='append', default=[])
    parser.add_argument('--junit-glob', action='append', default=[])
    parser.add_argument('--validate')
    parser.add_argument('--mutations', action='append', default=[])
    parser.add_argument('--postgres-version', action='append', default=[])
    args = parser.parse_args()
    if args.validate:
        need(not (args.output or args.source or args.junit or args.junit_glob or args.mutations or args.postgres_version))
        validate(args.validate)
    else:
        need(args.output and args.source)
        inputs = list(args.junit)
        for pattern in args.junit_glob:
            need('..' not in Path(pattern).parts)
            matches = sorted(glob.glob(pattern))
            need(bool(matches))
            inputs.extend(matches)
        publish(args.output, args.source, inputs, args.mutations, args.postgres_version)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, ET.ParseError, UnicodeError, RecursionError, KeyError, TypeError, subprocess.SubprocessError):
        import sys
        print('BLOCKED: public CI evidence rejected', file=sys.stderr)
        raise SystemExit(1)

