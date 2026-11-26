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
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 20000
MAX_TOTAL_BYTES = 128 * 1024 * 1024
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
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('archive exceeds size bound')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError('archive exceeds member count bound')
        total_unpacked = 0
        for info in infos:
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError('archive contains symlink')
            if info.is_dir():
                continue
            total_unpacked += info.file_size
            if total_unpacked > MAX_TOTAL_BYTES:
                raise ValueError("archive exceeds total unpacked bound")
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError('archive member exceeds size bound')
            with archive.open(info) as stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) > MAX_MEMBER_BYTES:
                raise ValueError('archive member exceeds size bound')
            yield info.filename, data


def scan_sdist(path):
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('archive exceeds size bound')
    with tarfile.open(path, 'r:gz') as archive:
        count = 0
        total_unpacked = 0
        for member in archive:
            count += 1
            if count > MAX_MEMBERS:
                raise ValueError('archive exceeds member count bound')
            if member.issym() or member.islnk():
                raise ValueError('archive contains link')
            if not member.isfile():
                continue
            total_unpacked += member.size
            if total_unpacked > MAX_TOTAL_BYTES:
                raise ValueError("archive exceeds total unpacked bound")
            if member.size > MAX_MEMBER_BYTES:
                raise ValueError('archive member exceeds size bound')
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError('archive member unavailable')
            with stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) > MAX_MEMBER_BYTES:
                raise ValueError('archive member exceeds size bound')
            yield member.name, data


def scan_git_tree(repo):
    root = Path(repo).resolve(strict=True)
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z'])
    for raw in names.split(b'\0'):
        if not raw:
            continue
        name = raw.decode('utf-8', 'surrogateescape')
        path = root / name
        if path.is_symlink() or path.resolve(strict=True) != path.absolute():
            raise ValueError('tracked symlink path found')
        if not path.is_file():
            raise ValueError('tracked file missing')
        if path.stat().st_size > MAX_MEMBER_BYTES:
            raise ValueError('tracked file exceeds size bound')
        with path.open('rb') as stream:
            data = stream.read(MAX_MEMBER_BYTES + 1)
        if len(data) > MAX_MEMBER_BYTES:
            raise ValueError('tracked file exceeds size bound')
        yield name, data


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
