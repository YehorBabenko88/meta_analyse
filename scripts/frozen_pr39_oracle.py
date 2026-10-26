"""Exact immutable PR39 oracle bytes, independent of checkout Git depth."""
import hashlib
from pathlib import Path

COMMIT = '4a92643c00a7e4d113025e1df427d8f4850f0981'
BLOB = 'a86da9cab8850e36b9e34333788197a2261d5ddf'
SHA256 = '82771c658db45fcec88d1e50982e506dbf5e664b00c10cd3f86400a646130ea2'
FILE = Path(__file__).resolve().parents[1]/'tests/fixtures/pr39_process_identity.py.txt'


def validate(raw):
    if (type(raw) is not bytes or hashlib.sha256(raw).hexdigest()!=SHA256 or
        hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=BLOB):
        raise ValueError('FROZEN_PR39_SOURCE_INVALID')
    return raw


def load_bytes(path=FILE):
    path=Path(path)
    if path.is_symlink():raise ValueError('FROZEN_PR39_SOURCE_INVALID')
    return validate(path.read_bytes())
