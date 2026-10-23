"""Tiny synthetic XML/parser/output witnesses, no external entity access."""
import importlib.util,json,subprocess,sys
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/verify_ci_audit_artifact_contents.py'
spec=importlib.util.spec_from_file_location('gate',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def cells(tmp_path):
    result={}
    for event,platform in m.CELLS:
        root=tmp_path/(event+'-'+platform);root.mkdir()
        (root/'source-sha.json').write_text(json.dumps(dict(sha='a'*40,expected_sha='a'*40,tree_sha='b'*40,event=event,event_sha='a'*40)))
        (root/'ci-audit.xml').write_text('<testsuites name="synthetic"><testsuite name="synthetic-identity" tests="1" errors="0" failures="0" skipped="0"><testcase classname="tests.test_control" name="test_control" /></testsuite></testsuites>')
        result[event,platform]=root
    return result

@pytest.mark.parametrize('kind',['comment','pi','doctype','internal_entity'])
def test_unprojected_parser_constructs_are_blocked(tmp_path,kind):
    value=cells(tmp_path);xml=value['push','windows']/'ci-audit.xml'
    text=xml.read_text()
    if kind=='comment':text=text.replace('<testcase','<!-- PRIVATE_SENTINEL_COMMENT --><testcase')
    if kind=='pi':text='<?synthetic PRIVATE_SENTINEL_PI?>'+text
    if kind=='doctype':text='<!DOCTYPE testsuites>'+text
    if kind=='internal_entity':text='<!DOCTYPE testsuites [<!ENTITY identity "test_control">]>'+text.replace('name="test_control"','name="&identity;"')
    xml.write_text(text)
    with pytest.raises((ValueError,m.ET.ParseError)):m.verify(value,'a'*40,'b'*40,1)

def test_cli_does_not_echo_malformed_raw_counter(tmp_path):
    value=cells(tmp_path);xml=value['push','windows']/'ci-audit.xml'
    xml.write_text(xml.read_text().replace('tests="1"','tests="PRIVATE_SENTINEL_RAW_COUNTER"'))
    args=[sys.executable,str(SCRIPT),'--sha','a'*40,'--tree','b'*40,'--minimum','1']
    for (event,platform),directory in value.items():args+=['--'+event.replace('_','-')+'-'+platform,str(directory)]
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode==1
    assert 'PRIVATE_SENTINEL_RAW_COUNTER' not in result.stdout+result.stderr

def test_cli_does_not_echo_filesystem_path_on_error(tmp_path):
    # An input directory missing after enumeration is modeled
    # through a subprocess import and an OSError containing a synthetic marker.
    code="import importlib.util,sys;spec=importlib.util.spec_from_file_location('g',sys.argv[1]);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.verify=lambda *a:(_ for _ in ()).throw(OSError('PRIVATE_SENTINEL_PATH'));sys.argv=['gate','--sha','a'*40,'--tree','b'*40]+sum(([ '--'+e.replace('_','-')+'-'+o, 'synthetic'] for e,o in g.CELLS),[]);sys.exit(g.main())"
    result=subprocess.run([sys.executable,'-c',code,str(SCRIPT)],capture_output=True,text=True)
    assert result.returncode==1 and 'PRIVATE_SENTINEL_PATH' not in result.stdout+result.stderr

@pytest.mark.parametrize('kind',['bad_xml','bad_json','nonfinite_json','bad_utf8','source_oversize',
    'xml_oversize','counter_leading_zero','counter_underscore','minimum_too_high','bool_minimum'])
def test_malformed_and_bounded_inputs(tmp_path,kind):
    value=cells(tmp_path);directory=value['push','windows'];minimum=1
    source=directory/'source-sha.json';xml=directory/'ci-audit.xml'
    if kind=='bad_xml':xml.write_text('<testsuites>')
    elif kind=='bad_json':source.write_text('{')
    elif kind=='nonfinite_json':source.write_text('NaN')
    elif kind=='bad_utf8':source.write_bytes(b'\xff')
    elif kind=='source_oversize':source.write_bytes(b' '*(8192+1))
    elif kind=='xml_oversize':xml.write_bytes(b' '*(8*1024*1024+1))
    elif kind=='counter_leading_zero':xml.write_text(xml.read_text().replace('tests="1"','tests="01"'))
    elif kind=='counter_underscore':xml.write_text(xml.read_text().replace('tests="1"','tests="0_1"'))
    elif kind=='minimum_too_high':minimum=2
    elif kind=='bool_minimum':minimum=True
    with pytest.raises((ValueError,OSError,m.ET.ParseError)):m.verify(value,'a'*40,'b'*40,minimum)

@pytest.mark.parametrize('filename',['source-sha.json','ci-audit.xml'])
def test_file_symlink_is_blocked(tmp_path,filename):
    value=cells(tmp_path);target=value['push','windows']/filename
    original=tmp_path/filename;target.rename(original)
    try:target.symlink_to(original)
    except OSError as exc:
        if getattr(exc,'winerror',None)==1314:pytest.skip('Windows symlink privilege unavailable')
        raise
    with pytest.raises(ValueError):m.verify(value,'a'*40,'b'*40,1)

def test_declared_external_entity_is_rejected_without_read(tmp_path):
    value=cells(tmp_path);directory=value['push','windows'];xml=directory/'ci-audit.xml'
    sentinel=tmp_path/'synthetic-sentinel';sentinel.write_text('SYNTHETIC_ONLY')
    xml.write_text('<!DOCTYPE testsuites [<!ENTITY x SYSTEM "'+sentinel.as_uri()+'">]>'+xml.read_text())
    with pytest.raises(ValueError,match='JUNIT_DTD_FORBIDDEN'):m.verify(value,'a'*40,'b'*40,1)

def test_actual_read_is_bounded_not_stat_size(monkeypatch,tmp_path):
    class Stream:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):
            assert n==33
            return b'x'*33
    monkeypatch.setattr(Path,'open',lambda *a,**k:Stream())
    with pytest.raises(ValueError,match='ARTIFACT_SIZE_INVALID'):m.read_limited(tmp_path/'synthetic',32)

def test_deep_json_cli_returns_explicit_refusal_without_traceback(tmp_path):
    value=cells(tmp_path)
    (value['push','windows']/'source-sha.json').write_text('['*3500+'0'+']'*3500)
    args=[sys.executable,str(SCRIPT),'--sha','a'*40,'--tree','b'*40,'--minimum','1']
    for (event,platform),directory in value.items():args+=['--'+event.replace('_','-')+'-'+platform,str(directory)]
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode==1 and result.stderr.strip()=='CONTENT_GATE_BLOCKED: INVALID_CONTENT_OR_IO'
