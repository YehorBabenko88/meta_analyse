"""Reject private key / TLS fixture material in the tracked tree and built distributions.

Usage:
  python scripts/check_no_private_key_material.py --git-tree REPO
  python scripts/check_no_private_key_material.py --dist DIR [--require-wheel] [--require-sdist]

Every member of every wheel (.whl) and sdist (.tar.gz) is inspected. A member is
rejected when its name has a key/certificate suffix or its bytes contain a PEM
private-key, certificate or CSR header. Exit code 0 = clean, 1 = material found,
2 = usage/input error. Only member names are printed, never contents.
"""
import argparse
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

FORBIDDEN_SUFFIXES = ('.key', '.pem', '.p12', '.pfx', '.csr', '.srl', '.der', '.crt', '.cer', '.jks', '.keystore')
_DASH = b'-' * 5
MARKERS = tuple(_DASH + b'BEGIN ' + label + _DASH for label in (
    b'PRIVATE KEY', b'RSA PRIVATE KEY', b'EC PRIVATE KEY', b'DSA PRIVATE KEY',
    b'ENCRYPTED PRIVATE KEY', b'OPENSSH PRIVATE KEY', b'CERTIFICATE', b'CERTIFICATE REQUEST'))


def offending(name, data):
    reasons = []
    if name.lower().endswith(FORBIDDEN_SUFFIXES):
        reasons.append('suffix')
    if any(marker in data for marker in MARKERS):
        reasons.append('pem-marker')
    return reasons


def scan_wheel(path):
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                yield info.filename, archive.read(info)


def scan_sdist(path):
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive.getmembers():
            if member.isfile():
                yield member.name, archive.extractfile(member).read()


def scan_git_tree(repo):
    names = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z'])
    for raw in names.split(b'\0'):
        if not raw:
            continue
        name = raw.decode('utf-8', 'surrogateescape')
        path = Path(repo) / name
        if path.is_file() and not path.is_symlink():
            yield name, path.read_bytes()


def check_dist(directory, require_wheel, require_sdist):
    directory = Path(directory)
    wheels = sorted(directory.glob('*.whl'))
    sdists = sorted(directory.glob('*.tar.gz'))
    if (require_wheel and not wheels) or (require_sdist and not sdists) or not (wheels or sdists):
        raise ValueError('expected distributions missing in ' + str(directory))
    findings, members = [], 0
    for path, scanner in [(w, scan_wheel) for w in wheels] + [(s, scan_sdist) for s in sdists]:
        for name, data in scanner(path):
            members += 1
            reasons = offending(name, data)
            if reasons:
                findings.append(f'{path.name}!{name}: {",".join(reasons)}')
    return findings, members


def check_tree(repo):
    findings, members = [], 0
    for name, data in scan_git_tree(repo):
        members += 1
        reasons = offending(name, data)
        if reasons:
            findings.append(f'{name}: {",".join(reasons)}')
    return findings, members


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--git-tree')
    group.add_argument('--dist')
    parser.add_argument('--require-wheel', action='store_true')
    parser.add_argument('--require-sdist', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.dist:
            findings, members = check_dist(args.dist, args.require_wheel, args.require_sdist)
        else:
            findings, members = check_tree(args.git_tree)
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print('KEY_MATERIAL_CHECK_UNAVAILABLE: ' + type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 2
    if members == 0:
        print('KEY_MATERIAL_CHECK_UNAVAILABLE: no members inspected', file=sys.stderr)
        return 2
    for finding in findings:
        print('PRIVATE_KEY_MATERIAL_FOUND ' + finding)
    print(f'inspected={members} findings={len(findings)}')
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
