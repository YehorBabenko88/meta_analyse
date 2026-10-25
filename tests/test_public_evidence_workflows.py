"""Publication contract and isolated transaction faults; no application calls."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import pytest
from test_project_public_ci_evidence import p,receipt,raw
from test_public_junit import m as public_checker
ROOT=Path(__file__).resolve().parents[1]

def test_every_upload_is_gated_and_staging_only():
    workflows=list((ROOT/'.github/workflows').glob('*.yml'))
    uploads=0
    for path in workflows:
        text=path.read_text()
        blocks=text.split('      - uses: actions/upload-artifact@v4')[1:]
        for block in blocks:
            block=re.split(r'\n  [a-zA-Z0-9_-]+:\n',block)[0]
            uploads+=1
            assert "if: always() && steps." in block and ".outcome == 'success'" in block
            assert 'if-no-files-found: error' in block and 'path: public-evidence/' in block
            assert block.count('path:')==1
        assert 'scripts/project_public_ci_evidence.py --validate public-evidence' in text
    assert uploads==12

def test_projection_commands_stop_on_first_failure():
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        text=path.read_text()
        for block in text.split('      - name: Project isolated public evidence')[1:]:
            block=block.split('      - uses: actions/upload-artifact@v4')[0]
            assert ('shell: bash' in block and 'set -euo pipefail' in block) or ('shell: pwsh' in block and block.count('$LASTEXITCODE -ne 0')==2)

@pytest.mark.parametrize('ordinal',[1,2,3])
def test_write_fault_never_publishes_partial_set(tmp_path,receipt,monkeypatch,ordinal):
    source=raw(tmp_path,'<testsuite><testcase classname="x" name="a"/></testsuite>')
    original=Path.write_bytes;calls=[]
    def failed(path,data):
        calls.append(path)
        if len(calls)==ordinal:
            original(path,data[:1]);raise OSError('SYNTHETIC_PARTIAL')
        return original(path,data)
    monkeypatch.setattr(Path,'write_bytes',failed)
    with pytest.raises(OSError):p.publish(tmp_path/'public',receipt,[source])
    assert not (tmp_path/'public').exists() and not list(tmp_path.glob('.public-*'))

def test_rename_fault_never_publishes(tmp_path,receipt,monkeypatch):
    source=raw(tmp_path,'<testsuite><testcase classname="x" name="a"/></testsuite>')
    monkeypatch.setattr(p.os,'rename',lambda *a:(_ for _ in ()).throw(OSError('SYNTHETIC')))
    with pytest.raises(OSError):p.publish(tmp_path/'public',receipt,[source])
    assert not (tmp_path/'public').exists() and not list(tmp_path.glob('.public-*'))

@pytest.mark.parametrize('status',['failure','error','skipped'])
def test_independent_status_oracle_kills_promotion_mutants(tmp_path,receipt,monkeypatch,status):
    source=raw(tmp_path,'<testsuite><testcase classname="x" name="a"><'+status+'/></testcase></testsuite>')
    original=p.project
    def promoted(data,seen):
        root=ET.fromstring(original(data,seen))
        case=root[0][0];case.remove(case[0])
        for suite in (root,root[0]):
            for field in ('failures','errors','skipped'):suite.set(field,'0')
        return ET.tostring(root,encoding='utf-8',xml_declaration=True)
    monkeypatch.setattr(p,'project',promoted)
    p.publish(tmp_path/'public',receipt,[source])
    # An internally consistent forged PASS still fails the independent raw->public oracle.
    with pytest.raises(AssertionError):
        assert ET.parse(tmp_path/'public/junit-000.xml').getroot()[0][0].find(status) is not None

def test_empty_forged_public_xml_is_rejected():
    with pytest.raises(ValueError):p.validate_junit(b'<testsuites />',set())

def test_nonfinite_json_rejected():
    with pytest.raises(ValueError):p.decode(b'{"x":NaN}')

def test_dtd_projection_oracle_has_a_valid_positive_body(monkeypatch):
    good=b'<testsuite tests="1"><testcase classname="x" name="a"/></testsuite>'
    assert len(ET.fromstring(p.project(good,set()))[0])==1
    payload=b'<!DOCTYPE testsuite [<!ENTITY identity "a">]>'+good.replace(b'name="a"',b'name="&identity;"')
    with pytest.raises(ValueError):p.project(payload,set())
    monkeypatch.setattr(p,'parse',ET.fromstring)
    def oracle():
        with pytest.raises(ValueError):p.project(payload,set())
    with pytest.raises(pytest.fail.Exception):oracle()

def test_dtd_public_checker_oracle_has_a_valid_positive_body(tmp_path,monkeypatch):
    good=p.project(b'<testsuite><testcase classname="x" name="a"/></testsuite>',set())
    path=tmp_path/'positive.xml';path.write_bytes(good)
    assert public_checker.inspect_file(path)
    head,body=good.split(b'?>',1)
    identity=ET.fromstring(good)[0][0].get('name').encode()
    payload=head+b'?>\n<!DOCTYPE testsuites [<!ENTITY identity "'+identity+b'">]>'+body.replace(identity,b'&identity;')
    path.write_bytes(payload)
    assert not public_checker.inspect_file(path)
    monkeypatch.setattr(public_checker,'StrictBuilder',ET.TreeBuilder)
    with pytest.raises(AssertionError):assert not public_checker.inspect_file(path)
