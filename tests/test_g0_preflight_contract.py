"""Offline, synthetic G0 record checks; no Windows tool/collector is invoked."""
import hashlib
import json
import os
from pathlib import Path

import pytest
from scripts import g0_preflight_contract as gate

SHA='a'*40
TREE='b'*40
SESSION='c'*64
NOW=1800000000


def control(mode='R0_R5'):
    roles=gate.COMMON | (gate.NATIVE if mode=='R0_R5' else set())
    source=dict(sha=SHA,tree=TREE,collector_manifest_sha256='d'*64,scripts_signed=False)
    tool=dict(sha256='e'*64,authority_sha256='f'*64,basis='AUTHENTICODE')
    baseline=dict(schema=1,source=source,tools={r:dict(tool) for r in roles})
    records=dict(schema=1,mode=mode,session=SESSION,recorded_at=NOW,
        source_before=dict(source,clean=True),source_after=dict(source,clean=True),
        tools={r:dict(tool,verification='VALID') for r in roles},
        python_version=[3,12,10],python_bits=64,powershell_version=[5,1],
        checks={k:True for k in gate.CHECKS},namespace={k:True for k in gate.NAMESPACE},
        policy=dict(machine_policy='Undefined',user_policy='Undefined',process='Undefined',
            current_user='RemoteSigned',local_machine='Restricted',effective='RemoteSigned',
            language_mode='FullLanguage',process_override_present=False,scripts_signed=False,
            script_policy_reviewed=True,motw_reviewed=True,add_type_chain_reviewed=mode=='R0_R5',
            temp_namespace_reviewed=mode=='R0_R5'))
    raw=json.dumps(baseline).encode()
    return records,raw,hashlib.sha256(raw).hexdigest()


def assess(records,raw,digest,**overrides):
    args=dict(expected_sha=SHA,expected_tree=TREE,session=SESSION,now=NOW)
    args.update(overrides)
    return gate.review(records,raw,digest,**args)


@pytest.mark.parametrize('mode',['R0_R5','HTTP_SYS_FORMAT'])
def test_consistent_records_are_only_ready_for_review_never_authorization(mode):
    report=assess(*control(mode))
    assert report['readiness']=='READY_FOR_OPERATOR_REVIEW'
    assert report['status']=='FAIL_CLOSED' and report['authorization']=='NONE'
    assert report['evidence_authenticity']=='OPERATOR_REVIEW_REQUIRED'


@pytest.mark.parametrize('role',sorted(gate.COMMON|gate.NATIVE))
@pytest.mark.parametrize('status',['UNSIGNED','INVALID','NOT_CHECKED'])
def test_every_required_tool_requires_approved_verification(role,status):
    e,b,d=control();e['tools'][role]['verification']=status
    assert assess(e,b,d)['readiness']=='BLOCKED'


def test_format_mode_rejects_malformed_unused_baseline_group():
    e,b,d=control('HTTP_SYS_FORMAT');baseline=json.loads(b)
    baseline['tools']['CSHARP_COMPILER']='PRIVATE_UNREVIEWED_VALUE'
    b=json.dumps(baseline).encode();d=hashlib.sha256(b).hexdigest()
    result=assess(e,b,d)
    assert result['readiness']=='BLOCKED'
    assert 'PRIVATE_UNREVIEWED_VALUE' not in json.dumps(result)


@pytest.mark.parametrize('role',['DOTNET_RUNTIME','NATIVE_DLLS'])
def test_format_mode_still_requires_token_api_dlls_and_powershell_clr(role):
    # Format-only avoids C# compilation/process inventory, but its elevation/
    # system-directory helpers use ctypes WinAPI and PowerShell itself uses CLR.
    e,b,d=control('HTTP_SYS_FORMAT');baseline=json.loads(b)
    e['tools'].pop(role,None);baseline['tools'].pop(role,None)
    b=json.dumps(baseline).encode();d=hashlib.sha256(b).hexdigest()
    assert assess(e,b,d)['readiness']=='BLOCKED'


@pytest.mark.parametrize('failure',['baseline_digest','source','source_clean','source_after','old',
    'future','session','tool_hash','tool_authority','unsigned','unconfirmed','missing_tool',
    'python32','python_bool','python_version','ps_version','bypass','override','process_policy',
    'policy_inconsistent','constrained','allsigned_unsigned','motw','compiler','temp',
    'existing','reparse','hardlink','writer','host','pg_isolation','missing','raw_exception','nan'])
def test_untrusted_partial_or_malformed_evidence_never_promotes(failure):
    e,b,d=control()
    if failure=='baseline_digest':d='0'*64
    elif failure=='source':e['source_before']['sha']='0'*40
    elif failure=='source_clean':e['source_before']['clean']=False
    elif failure=='source_after':e['source_after']['collector_manifest_sha256']='0'*64
    elif failure=='old':e['recorded_at']=NOW-301
    elif failure=='future':e['recorded_at']=NOW+11
    elif failure=='session':e['session']='0'*64
    elif failure in ('tool_hash','tool_authority','unsigned','unconfirmed'):
        item=e['tools']['PYTHON_EXE']
        if failure=='tool_hash':item['sha256']='0'*64
        if failure=='tool_authority':item['authority_sha256']='0'*64
        if failure=='unsigned':item['verification']='UNSIGNED'
        if failure=='unconfirmed':item['verification']='NOT_CHECKED'
    elif failure=='missing_tool':del e['tools']['GIT']
    elif failure=='python32':e['python_bits']=32
    elif failure=='python_bool':e['python_bits']=True
    elif failure=='python_version':e['python_version']=[3,13,0]
    elif failure=='ps_version':e['powershell_version']=[7,4]
    elif failure=='bypass':e['policy']['local_machine']='Bypass'
    elif failure=='override':e['policy']['process_override_present']=True
    elif failure=='process_policy':e['policy']['process']='RemoteSigned'
    elif failure=='policy_inconsistent':e['policy']['effective']='AllSigned'
    elif failure=='constrained':e['policy']['language_mode']='ConstrainedLanguage'
    elif failure=='allsigned_unsigned':e['policy'].update(current_user='AllSigned',effective='AllSigned')
    elif failure=='motw':e['policy']['motw_reviewed']=False
    elif failure=='compiler':e['policy']['add_type_chain_reviewed']=False
    elif failure=='temp':e['policy']['temp_namespace_reviewed']=False
    elif failure=='existing':e['namespace']['leaf_absent']=False
    elif failure=='reparse':e['namespace']['no_reparse']=False
    elif failure=='hardlink':e['namespace']['link_counts_reviewed']=False
    elif failure=='writer':e['namespace']['isolated_writer_scope']=False
    elif failure=='host':e['checks']['host_context']=False
    elif failure=='pg_isolation':e['checks']['postgres_5432_isolated']=False
    elif failure=='missing':del e['policy']
    elif failure=='raw_exception':e['raw_exception']='PRIVATE_TOKEN_DSN_HOST_PATH'
    elif failure=='nan':e['recorded_at']=float('nan')
    report=assess(e,b,d)
    assert report['readiness']=='BLOCKED' and report['authorization']=='NONE'
    assert 'PRIVATE_TOKEN_DSN_HOST_PATH' not in json.dumps(report)


@pytest.mark.parametrize('payload',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',b'null',b'[]'])
def test_strict_json_rejects_duplicate_nonfinite_and_outer_types(payload):
    with pytest.raises(ValueError):gate.strict_object(payload)


@pytest.mark.parametrize('alias',['same','hardlink'])
def test_exclusive_receipt_preserves_existing_evidence(tmp_path,alias):
    original=tmp_path/'existing';original.write_bytes(b'PRIVATE_EXISTING_BYTES')
    target=original
    if alias=='hardlink':target=tmp_path/'link';os.link(original,target)
    with pytest.raises((OSError,ValueError)):gate.publish_new(target,b'{}')
    assert original.read_bytes()==b'PRIVATE_EXISTING_BYTES'


def test_synthetic_symlink_mode_is_rejected(tmp_path,monkeypatch):
    import stat
    from types import SimpleNamespace
    original=Path.lstat
    def inspect(path,*args,**kwargs):
        value=original(path,*args,**kwargs)
        if path==tmp_path:return SimpleNamespace(st_mode=stat.S_IFLNK,st_file_attributes=0)
        return value
    monkeypatch.setattr(Path,'lstat',inspect)
    with pytest.raises(ValueError):gate.publish_new(tmp_path/'new.json',b'{}')
    assert not (tmp_path/'new.json').exists()


def test_receipt_is_exclusive_and_rejects_relative_output(tmp_path):
    path=tmp_path/'new.json';gate.publish_new(path,b'{}')
    assert path.read_bytes()==b'{}'
    with pytest.raises((OSError,ValueError)):gate.publish_new(path,b'changed')
    with pytest.raises(ValueError):gate.publish_new(Path('relative.json'),b'{}')


def test_synthetic_reparse_ancestor_is_rejected_before_create(tmp_path,monkeypatch):
    from types import SimpleNamespace
    original=Path.lstat
    def inspect(path,*args,**kwargs):
        value=original(path,*args,**kwargs)
        if path==tmp_path:
            return SimpleNamespace(st_mode=value.st_mode,st_file_attributes=0x400)
        return value
    monkeypatch.setattr(Path,'lstat',inspect)
    with pytest.raises(ValueError):gate.publish_new(tmp_path/'new.json',b'{}')
    assert not (tmp_path/'new.json').exists()


def test_source_signature_claim_cannot_override_approved_unsigned_source():
    e,b,d=control()
    e['policy'].update(current_user='AllSigned',effective='AllSigned',scripts_signed=True)
    assert assess(e,b,d)['readiness']=='BLOCKED'


@pytest.mark.parametrize('phase',['source_before','source_after'])
@pytest.mark.parametrize('approved,bad',[(False,0),(False,0.0),(True,1),(True,1.0)])
def test_source_signature_flags_require_exact_boolean(phase,approved,bad):
    e,b,d=control();baseline=json.loads(b)
    baseline['source']['scripts_signed']=approved
    for key in ('source_before','source_after'):e[key]['scripts_signed']=approved
    e['policy']['scripts_signed']=approved
    e[phase]['scripts_signed']=bad
    b=json.dumps(baseline).encode();d=hashlib.sha256(b).hexdigest()
    assert assess(e,b,d)['readiness']=='BLOCKED'


def test_post_create_hardlink_race_refuses_before_receipt_write(tmp_path,monkeypatch):
    original=os.open;target=tmp_path/'new.json';alias=tmp_path/'new-alias'
    def create(path,*args,**kwargs):
        fd=original(path,*args,**kwargs)
        os.link(path,alias)
        return fd
    monkeypatch.setattr(os,'open',create)
    with pytest.raises(ValueError):gate.publish_new(target,b'not-published')
    assert target.read_bytes()==alias.read_bytes()==b''


def test_namespace_change_after_create_blocks_without_touching_existing(tmp_path,monkeypatch):
    original=gate.namespace;calls=[];prior=tmp_path/'prior';prior.write_bytes(b'private-previous')
    def inspect(path):
        result=original(path);calls.append(1)
        return result if len(calls)==1 else []
    monkeypatch.setattr(gate,'namespace',inspect)
    with pytest.raises(ValueError):gate.publish_new(tmp_path/'new.json',b'not-published')
    assert prior.read_bytes()==b'private-previous' and (tmp_path/'new.json').read_bytes()==b''


def test_cli_refusal_has_no_raw_values_and_never_returns_zero(tmp_path,capsys):
    records,baseline,digest=control();records['tools']['GIT']['verification']='UNSIGNED'
    e=tmp_path/'private.json';e.write_text(json.dumps(records))
    b=tmp_path/'baseline.json';b.write_bytes(baseline);output=tmp_path/'public.json'
    args=['--records',str(e),'--baseline',str(b),'--approved-baseline-sha256',digest,
          '--expected-sha',SHA,'--expected-tree',TREE,'--session',SESSION,'--output',str(output)]
    assert gate.main(args,now=NOW)==1
    value=json.loads(output.read_text())
    assert value['readiness']=='BLOCKED' and value['authorization']=='NONE'
    assert str(tmp_path) not in capsys.readouterr().out
    before=output.read_bytes();assert gate.main(args,now=NOW)==1
    assert output.read_bytes()==before
