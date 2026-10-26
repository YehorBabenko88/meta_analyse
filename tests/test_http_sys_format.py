"""Format-only diagnostics: synthetic data; no actual netsh/Windows collection."""
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'commissioning'))

@pytest.fixture
def d():return importlib.import_module('http_sys_format')

@pytest.mark.parametrize('text',['', 'opaque: value\n17845\nКириллица',
    'Request queue name: synthetic\n Number of active processes attached: 1\n ID: 777, image: secret\n HTTP://127.0.0.1:17845/',
    '    Request queue name: unknown\nProcess IDs:\n 777\n',
    'Unknown localized label: private\nДругой заголовок: private\n',
    'Request queue name: spoof\nNumber of active processes attached: 999\n'])
def test_projection_never_claims_owner(d,text):
    result=d.project(text)
    assert result['ownership']=='NOT_EVALUATED' and result['format_support']=='NOT_ATTESTED'
    assert set(result)=={'ownership','format_support','line_count','colon_line_count','characters','markers','target_token'}

@pytest.mark.parametrize('bad',[None,True,12,3.2,{},[],b'private','x'*(1024*1024+1)],ids=['none','bool','int','float','mapping','list','bytes','oversized'])
def test_format_input_strict_types_and_bound(d,bad):
    with pytest.raises(ValueError):d.project(bad)

@pytest.mark.parametrize('raw',[
    r'C:\PRIVATE_PATH_SENTINEL\secret.exe', 'PRIVATE_PROCESS_SENTINEL',
    'HTTP://private-host-sentinel:17845/private-token-sentinel/',
    '777777777', 'S-1-5-21-999999999', 'private-dsn-sentinel',
    'ИмяСлужбыСекрет_SENTINEL', '\x00\x1bPRIVATE_EXCEPTION_SENTINEL',
])
def test_projection_does_not_copy_or_hash_private_values(d,raw):
    public=json.dumps(d.project('Unknown label: '+raw),ensure_ascii=True)
    assert raw not in public and 'SENTINEL' not in public and 'sentinel' not in public
    assert 'sha256' not in public and '777777777' not in public


def test_marker_shapes_preserve_indentation_without_values(d):
    a=d.project('Request queue name: secret\n Number of active processes attached: 1\n ID: 777, image: secret\n')
    b=d.project('    Request queue name: secret\n Process IDs:\n 777\n')
    assert a['markers']['queue_column_zero']=='ONE'
    assert b['markers']['queue_indented']=='ONE'
    assert b['markers']['summary_process_ids']=='ONE'
    assert a['markers']['verbose_process']=='ONE'
    assert a['ownership']==b['ownership']=='NOT_EVALUATED'

@pytest.fixture
def cli(d,monkeypatch,tmp_path):
    monkeypatch.setattr(d.host.platform,'system',lambda:'Windows')
    monkeypatch.setattr(d.host,'is_elevated',lambda:True)
    binding={'sha':'1'*40,'tree':'2'*40,'collector':{'synthetic':True}}
    monkeypatch.setattr(d,'source_binding',lambda *a:binding.copy())
    monkeypatch.setattr(d,'capture_snapshot',lambda:'opaque\nКириллица\n')
    path=tmp_path/'public.json';args=['--expected-sha','1'*40,'--expected-tree','2'*40,'--output',str(path)]
    return d,path,args


def test_cli_always_refuses_and_persists_only_public_projection(cli,capsys):
    d,path,args=cli;assert d.main(args)==1
    result=json.loads(capsys.readouterr().out);assert result==json.loads(path.read_text())
    assert result['status']=='FAIL_CLOSED' and result['authorization']=='NONE'
    assert result['projection_status']=='AVAILABLE'
    assert result['lifetime_binding']=='NOT_EVALUATED_DIAGNOSTIC_ONLY'
    assert result['source']=={'sha':'1'*40,'tree':'2'*40}

@pytest.mark.parametrize('fault',['child','source_before','source_after','malformed','collision','token'])
def test_cli_refusals_never_leak_or_authorize(cli,monkeypatch,capsys,fault):
    d,path,args=cli
    def private_error(*a):raise RuntimeError('PRIVATE_EXCEPTION_SENTINEL')
    if fault=='child':monkeypatch.setattr(d,'capture_snapshot',private_error)
    elif fault=='source_before':monkeypatch.setattr(d,'source_binding',private_error)
    elif fault=='source_after':
        n=[]
        def binding(*a):
            n.append(1)
            if len(n)>1:private_error()
            return {'sha':'1'*40,'tree':'2'*40}
        monkeypatch.setattr(d,'source_binding',binding)
    elif fault=='malformed':monkeypatch.setattr(d,'capture_snapshot',lambda:None)
    elif fault=='collision':path.write_text('EXISTING_PRIVATE_SENTINEL')
    else:monkeypatch.setattr(d.host,'is_elevated',lambda:False)
    assert d.main(args)==1
    public=capsys.readouterr();assert public.err=='' and 'SENTINEL' not in public.out
    result=json.loads(public.out);assert result['authorization']=='NONE' and result['projection_status']=='UNAVAILABLE'
    if fault=='collision':assert path.read_text()=='EXISTING_PRIVATE_SENTINEL'

@pytest.mark.parametrize('payload',[
    b'{"schema":1,"exit_code":0,"text":"safe","text":"private"}',
    b'{"schema":1,"exit_code":true,"text":"private"}',
    b'{"schema":1,"exit_code":1,"text":"private"}',
    b'{"schema":1,"exit_code":0,"text":null}',
    b'{"schema":1,"exit_code":0,"text":"private","extra":1}',
    b'{"schema":1,"exit_code":NaN,"text":"private"}',
])
def test_child_contract_invalid_never_projects(d,monkeypatch,payload):
    monkeypatch.setattr(d.host,'system_directory',lambda:Path('C:/SyntheticSystem32'))
    monkeypatch.setattr(d.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=payload,stderr=b'PRIVATE_EXCEPTION_SENTINEL'))
    with pytest.raises(ValueError):d.capture_snapshot()


def test_child_command_policy_and_source_are_fixed(d,monkeypatch):
    monkeypatch.setattr(d.host,'system_directory',lambda:Path('C:/SyntheticSystem32'))
    monkeypatch.setenv('PSExecutionPolicyPreference','Bypass')
    def run(args,**kw):
        assert args[1:4]==['-NoProfile','-NonInteractive','-File']
        assert '-ExecutionPolicy' not in args and 'Bypass' not in args
        assert Path(args[-1]).name=='http-sys-format.ps1'
        assert not any(k.lower()=='psexecutionpolicypreference' for k in kw['env'])
        assert kw['timeout']==20 and kw['capture_output'] is True
        return SimpleNamespace(returncode=0,stdout=b'{"schema":1,"exit_code":0,"text":"safe"}',stderr=b'')
    monkeypatch.setattr(d.subprocess,'run',run)
    assert d.capture_snapshot()=='safe'


def test_diagnostic_producer_has_one_explicit_read_only_command():
    source=(Path(__file__).resolve().parents[1]/'commissioning/http-sys-format.ps1').read_text(encoding='utf-8-sig')
    assert "Join-Path ([Environment]::SystemDirectory) 'netsh.exe'" in source
    assert source.count('& $netshPath http show servicestate view=requestq verbose=yes')==1
    assert 'verbose=no' not in source
    for forbidden in ('Add-Type','Get-CimInstance','Start-Process','Set-ExecutionPolicy','Out-File','Write-Host'):
        assert forbidden not in source


def test_format_projection_property_fixed_output_alphabet(d):
    from hypothesis import given,settings,strategies as st
    allowed={'ZERO','ONE','TWO_TO_FOUR','FIVE_TO_SIXTEEN','SEVENTEEN_TO_SIXTY_FOUR',
        'SIXTY_FIVE_TO_256','OVER_256','NOT_EVALUATED','NOT_ATTESTED','PRESENT','ABSENT'}
    @settings(max_examples=100,database=None)
    @given(st.text(max_size=1000))
    def check(text):
        value=d.project(text)
        def walk(v):
            if type(v) is dict:
                for x in v.values():walk(x)
            elif type(v) is str:assert v in allowed
            else:assert type(v) is bool
        walk(value)
        assert json.loads(json.dumps(value,allow_nan=False))==value
    check()
