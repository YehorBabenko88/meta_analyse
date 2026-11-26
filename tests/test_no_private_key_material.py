"""F2 (unified-system#156): no TLS/private-key material in the tree or in built distributions."""
import io
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import check_no_private_key_material as checker  # noqa: E402

SUFFIXES = ('*.key', '*.pem', '*.p12', '*.pfx', '*.csr', '*.srl', '*.der', '*.crt', '*.cer', '*.jks', '*.keystore')
# Built at runtime so this file never contains a literal PEM header.
DASH = '-' * 5
PRIVATE = (DASH + 'BEGIN ' + 'PRIVATE KEY' + DASH + '\nZmFrZQ==\n' + DASH + 'END ' + 'PRIVATE KEY' + DASH + '\n').encode()
CERT = (DASH + 'BEGIN ' + 'CERTIFICATE' + DASH + '\nZmFrZQ==\n' + DASH + 'END ' + 'CERTIFICATE' + DASH + '\n').encode()


def _wheel(path, members):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def _sdist(path, members):
    with tarfile.open(path, 'w:gz') as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_tracked_tree_has_no_private_key_material():
    findings, members = checker.check_tree(ROOT)
    assert members > 100
    assert findings == []


def test_removed_tls_loopback_fixtures_are_not_tracked():
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', 'docs/commissioning_evidence_v3/tls-loopback'], text=True).split()
    assert tracked, 'historical tls-loopback logs/scripts must remain'
    for name in ('ca', 'good', 'self', 'wrong'):
        for suffix in ('.key', '.pem'):
            assert f'docs/commissioning_evidence_v3/tls-loopback/{name}{suffix}' not in tracked


def test_wheel_package_sources_have_no_key_material():
    for path in (ROOT / 'src').rglob('*'):
        if path.is_file():
            assert checker.offending(path.name, path.read_bytes()) == [], path


def test_packaging_configuration_excludes_key_material():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    setuptools = project['tool']['setuptools']
    assert setuptools['packages']['find']['where'] == ['src']
    assert set(SUFFIXES) <= set(setuptools['exclude-package-data']['*'])
    manifest = (ROOT / 'MANIFEST.in').read_text().splitlines()
    assert 'prune docs' in manifest
    excluded = next(line for line in manifest if line.startswith('global-exclude ')).split()[1:]
    assert set(SUFFIXES) <= set(excluded)
    ignored = (ROOT / '.gitignore').read_text().splitlines()
    assert {'*.key', '*.p12', '*.pfx', '*.srl'} <= set(ignored)


def test_checker_rejects_key_material_in_built_wheel_and_sdist(tmp_path):
    dirty = tmp_path / 'dirty'
    dirty.mkdir()
    _wheel(dirty / 'meta_analyse-0.1.0-py3-none-any.whl', {
        'meta_analyse/__init__.py': b'',
        'meta_analyse/fixture.key': b'opaque',
        'meta_analyse/data/blob.txt': PRIVATE,
    })
    _sdist(dirty / 'meta_analyse-0.1.0.tar.gz', {
        'meta_analyse-0.1.0/pyproject.toml': b'[project]\n',
        'meta_analyse-0.1.0/docs/tls-loopback/good.pem': CERT,
    })
    findings, members = checker.check_dist(dirty, True, True)
    assert members == 5
    assert sorted(findings) == [
        'meta_analyse-0.1.0-py3-none-any.whl!meta_analyse/data/blob.txt: pem-marker',
        'meta_analyse-0.1.0-py3-none-any.whl!meta_analyse/fixture.key: suffix',
        'meta_analyse-0.1.0.tar.gz!meta_analyse-0.1.0/docs/tls-loopback/good.pem: suffix,pem-marker',
    ]
    assert checker.main(['--dist', str(dirty), '--require-wheel', '--require-sdist']) == 1


def test_checker_accepts_clean_distributions_and_refuses_missing_ones(tmp_path):
    clean = tmp_path / 'clean'
    clean.mkdir()
    _wheel(clean / 'meta_analyse-0.1.0-py3-none-any.whl', {'meta_analyse/__init__.py': b'"""ok"""\n'})
    _sdist(clean / 'meta_analyse-0.1.0.tar.gz', {'meta_analyse-0.1.0/README.md': b'ok\n'})
    assert checker.main(['--dist', str(clean), '--require-wheel', '--require-sdist']) == 0
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert checker.main(['--dist', str(empty)]) == 2
    only_wheel = tmp_path / 'only-wheel'
    only_wheel.mkdir()
    _wheel(only_wheel / 'meta_analyse-0.1.0-py3-none-any.whl', {'meta_analyse/__init__.py': b''})
    assert checker.main(['--dist', str(only_wheel), '--require-wheel', '--require-sdist']) == 2


def test_checker_rejects_oversized_wheel_member_without_extracting(tmp_path):
    dirty = tmp_path / 'large-wheel'
    dirty.mkdir()
    _wheel(dirty / 'meta_analyse-0.1.0-py3-none-any.whl', {
        'meta_analyse/oversized.bin': b'x' * (checker.MAX_MEMBER_BYTES + 1),
    })
    assert checker.main(['--dist', str(dirty)]) == 2


def test_checker_rejects_archive_symlinks(tmp_path):
    dirty = tmp_path / 'links'
    dirty.mkdir()
    with tarfile.open(dirty / 'meta_analyse-0.1.0.tar.gz', 'w:gz') as archive:
        link = tarfile.TarInfo('meta_analyse-0.1.0/docs/external')
        link.type = tarfile.SYMTYPE
        link.linkname = '../../external'
        archive.addfile(link)
    assert checker.main(['--dist', str(dirty)]) == 2


def test_checker_rejects_symlink_in_wheel(tmp_path):
    dirty = tmp_path / 'wheel-link'
    dirty.mkdir()
    with zipfile.ZipFile(dirty / 'meta_analyse-0.1.0-py3-none-any.whl', 'w') as archive:
        link = zipfile.ZipInfo('meta_analyse/external')
        link.create_system = 3
        link.external_attr = (0o120777 << 16)
        archive.writestr(link, '../../external')
    assert checker.main(['--dist', str(dirty)]) == 2


def test_checker_rejects_oversized_sdist_member(tmp_path):
    dirty = tmp_path / 'large-sdist'
    dirty.mkdir()
    _sdist(dirty / 'meta_analyse-0.1.0.tar.gz', {
        'meta_analyse-0.1.0/large.bin': b'x' * (checker.MAX_MEMBER_BYTES + 1),
    })
    assert checker.main(['--dist', str(dirty)]) == 2
