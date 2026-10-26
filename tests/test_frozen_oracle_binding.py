import pytest
from scripts import frozen_pr39_oracle as frozen


def test_frozen39_golden_source_has_both_immutable_hashes():
    raw=frozen.load_bytes();assert frozen.validate(raw)==raw

@pytest.mark.parametrize('bad',[None,'source',b'',b'private',b'\xef\xbb\xbf'])
def test_frozen39_invalid_bytes_never_fall_back(bad):
    with pytest.raises(ValueError,match='^FROZEN_PR39_SOURCE_INVALID$'):frozen.validate(bad)


def test_frozen39_one_byte_mutation_is_rejected():
    raw=frozen.load_bytes()
    with pytest.raises(ValueError):frozen.validate(raw[:-1]+bytes([raw[-1]^1]))
