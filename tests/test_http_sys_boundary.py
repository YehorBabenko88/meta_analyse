"""Synthetic HTTP.sys parser refusals; never invokes netsh or host collection."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))
import host_identity as host

GOOD=('Request queue name: unnamed\n'
      '    Number of active processes attached: 1\n'
      '    Processes:\n        ID: 777, image: synthetic\n'
      '    URL groups:\n        Registered URLs:\n'
      '            HTTP://127.0.0.1:17845/\n')

@pytest.mark.parametrize('text',[
    GOOD.replace('    Processes:', '    Number of active processes attached: 2\n    Processes:'),
    GOOD.replace('    Processes:', '    Number of active processes attached: 1\n    Processes:'),
    GOOD.replace('    Number of active processes attached:', '    spoof Number of active processes attached:'),
    GOOD+'            HTTPS://+:8443/\n',
    GOOD+'            https://127.0.0.1:8443/\n',
    GOOD.replace('ID: 777,', 'ID: 0,'),
    GOOD.replace('ID: 777,', 'ID: 2147483648,'),
])
def test_http_sys_malformed_evidence_must_not_admit(text):
    with pytest.raises(ValueError):host.http_sys_owner(text,17845)

@pytest.mark.parametrize('text',[
    GOOD+GOOD,GOOD.replace('attached: 1','attached: 2'),
    GOOD.replace('    URL groups:', '        ID: 778, image: synthetic\n    URL groups:'),
    GOOD.replace('Request queue name:', 'Имя другой сущности:'),
    GOOD.replace('Number of active processes attached:', 'Произвольный локализованный заголовок:'),
    GOOD.replace('        ID: 777, image: synthetic','        777'),
    GOOD.replace('Request queue name:', '    Request queue name:'),
    GOOD.replace('HTTP://127.0.0.1:17845/','HTTP://+:17845/'),
    GOOD.replace('HTTP://127.0.0.1:17845/','HTTP://127.0.0.1:17846/'),
    '',
])
def test_http_sys_unsupported_and_ambiguous_fail_closed(text):
    with pytest.raises(ValueError):host.http_sys_owner(text,17845)

@pytest.mark.parametrize('suffix',['',' :ignored'])
def test_existing_reviewed_http_profile_positive(suffix):
    # URL trailing garbage is never a positive path.
    if suffix:
        with pytest.raises(ValueError):host.http_sys_owner(GOOD.replace('17845/','17845/'+suffix),17845)
    else:assert host.http_sys_owner(GOOD,17845)==777
