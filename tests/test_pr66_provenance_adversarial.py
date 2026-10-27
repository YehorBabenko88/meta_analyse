"""Adversarial regressions of PR66; synthetic inputs, no native execution."""
import hashlib
import json
from pathlib import Path
import pytest
from scripts import g0_access_review as gate
from test_g0_access_review import fixture,reader

def test_caller_pin_never_claims_independent_authority_approval():
    _,raw,pin=fixture()
    result=gate.verify_manifest(raw,pin,read=reader)
    assert result['provenance']=='PINNED_MANIFEST_BYTES_MATCH'
    assert result['authority_reference']=='NOT_BOUND'
    assert result['approval_authenticity']=='EXTERNAL_REVIEW_REQUIRED'

@pytest.mark.parametrize('fault',['absent','wrong_pin','wrong_bytes','wrong_reference'])
def test_authority_packet_must_be_separately_pinned_and_bound(fault):
    value,_,_=fixture();packet=b'SYNTHETIC_EXTERNAL_REFERENCE_NOT_APPROVAL'
    pin=hashlib.sha256(packet).hexdigest()
    for item in value['files']:item['authority_sha256']=pin
    if fault=='wrong_reference':value['files'][0]['authority_sha256']='f'*64
    raw=json.dumps(value).encode();digest=hashlib.sha256(raw).hexdigest()
    kw={} if fault=='absent' else dict(authority_raw=packet,
        approved_authority_digest='0'*64 if fault=='wrong_pin' else pin)
    if fault=='wrong_bytes':kw['authority_raw']=b'OTHER_PACKET'
    result=gate.verify_manifest(raw,digest,read=reader,**kw)
    assert result.get('authority_reference')!='PINNED_PACKET_MATCH'
    assert result['authorization']=='NONE' and result['readiness']=='BLOCKED'

def test_valid_authority_reference_still_requires_external_authentication():
    value,_,_=fixture();packet=b'SYNTHETIC_ONLY_AUTHORITY_PACKET'
    pin=hashlib.sha256(packet).hexdigest()
    for item in value['files']:item['authority_sha256']=pin
    raw=json.dumps(value).encode()
    result=gate.verify_manifest(raw,hashlib.sha256(raw).hexdigest(),read=reader,
        authority_raw=packet,approved_authority_digest=pin)
    assert result['authority_reference']=='PINNED_PACKET_MATCH'
    assert result['approval_authenticity']=='EXTERNAL_REVIEW_REQUIRED'
    assert result['readiness']=='BLOCKED'

def test_current_token_cli_without_authority_cannot_start_collection(tmp_path,monkeypatch,capsys):
    _,raw,pin=fixture();manifest=tmp_path/'synthetic.json';manifest.write_bytes(raw)
    calls=[]
    monkeypatch.setattr(gate,'hash_regular_file',lambda path,**_:reader(path))
    monkeypatch.setattr(gate,'collect_access',lambda:calls.append(True) or gate.project_access(None))
    assert gate.main(['--manifest',str(manifest),'--approved-manifest-sha256',pin,'--current-token'])==1
    result=json.loads(capsys.readouterr().out)
    assert calls==[] and result['access']=='UNAVAILABLE'

def test_shipped_template_is_not_an_approved_baseline():
    path=Path(__file__).resolve().parents[1]/'docs/g0-baseline/MANIFEST_NOT_APPROVED.json'
    raw=path.read_bytes();calls=[]
    result=gate.verify_manifest(raw,hashlib.sha256(raw).hexdigest(),
                                read=lambda p:calls.append(p))
    assert result['provenance']=='UNAVAILABLE' and calls==[]

@pytest.mark.parametrize('value',[None,True,1.0,{},'',b'',b'x'*(1024*1024+1)],
                         ids=['none','bool','float','object','text','empty','oversize'])
def test_malformed_authority_packet_never_binds(value):
    _,raw,pin=fixture();calls=[]
    result=gate.verify_manifest(raw,pin,read=lambda p:calls.append(p),authority_raw=value,
                                approved_authority_digest='a'*64)
    assert result['authority_reference']=='NOT_BOUND' and calls==[]
