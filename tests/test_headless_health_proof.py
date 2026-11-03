"""Real Git admission followed by complete immutable health-byte proof tests."""
import os
import stat
from pathlib import Path
import subprocess
import pytest
from test_headless_service import capsule
from meta_analyse import headless_service as service


def verifier_for(capsule):
    root,env,_=capsule
    return service.SourceVerifier(root,service.Identity.from_environment(env))


def test_health_uses_no_git_after_genuine_startup_proof(capsule,monkeypatch):
    verifier=verifier_for(capsule);real=verifier.git;calls=[]
    def record(*args,**kw):calls.append(args);return real(*args,**kw)
    monkeypatch.setattr(verifier,'git',record)
    verifier.bind_health();assert len(calls)==7
    def forbidden(*args,**kw):raise AssertionError('GIT_MUST_NOT_RUN_DURING_HEALTH')
    monkeypatch.setattr(verifier,'git',forbidden)
    for _ in range(3):verifier.verify_health()
    # Scientific requests retain their authoritative Git gate.
    with pytest.raises(AssertionError,match='GIT_MUST_NOT_RUN'):verifier.verify_scientific()


@pytest.mark.parametrize('mutation',('index','HEAD','ref','object','config','alternates','untracked_code','tracked_source','new_directory','hardlink','reparse'))
def test_every_health_rejects_metadata_source_and_namespace_mutation(capsule,mutation,tmp_path):
    root,_,git=capsule;ref=root/'.git'/git('symbolic-ref','HEAD')
    obj=next(p for p in (root/'.git/objects').rglob('*') if p.is_file())
    verifier=verifier_for(capsule);verifier.bind_health();link=None
    target={'index':root/'.git/index','HEAD':root/'.git/HEAD','ref':ref,'object':obj,'config':root/'.git/config','tracked_source':root/'src/meta_analyse/core.py'}.get(mutation)
    if target is not None:
        before=target.stat();target.chmod(before.st_mode|stat.S_IWUSR)
        raw=target.read_bytes();assert raw
        target.write_bytes(bytes([raw[0]^1])+raw[1:])
        # Same-size edits with restored timestamps must still be rehashed.
        os.utime(target,ns=(before.st_atime_ns,before.st_mtime_ns));target.chmod(before.st_mode)
    elif mutation=='alternates':
        (root/'.git/objects/info/alternates').write_text(str(tmp_path))
    elif mutation=='untracked_code':(root/'src/meta_analyse/shadow.pyc').write_bytes(b'untracked')
    elif mutation=='new_directory':(root/'.git/refs/new-namespace').mkdir()
    elif mutation=='hardlink':os.link(root/'src/meta_analyse/core.py',tmp_path/'outside-hardlink')
    else:
        destination=tmp_path/'outside';destination.mkdir();link=root/'.git/refs/outside'
        if os.name=='nt':subprocess.run(['cmd','/c','mklink','/J',str(link),str(destination)],check=True,capture_output=True)
        else:link.symlink_to(destination,target_is_directory=True)
    try:
        with pytest.raises(ValueError):verifier.verify_health()
    finally:
        if link is not None:
            if os.name=='nt':link.rmdir()
            else:link.unlink()


def test_startup_interleaving_cannot_bless_mutated_metadata(capsule,monkeypatch):
    root,_,_=capsule;verifier=verifier_for(capsule);real=verifier.verify
    def interleaved():
        result=real()
        with (root/'.git/config').open('a') as stream:stream.write('\n# mutation between Git proof and cache admission\n')
        return result
    monkeypatch.setattr(verifier,'verify',interleaved)
    with pytest.raises(ValueError):verifier.bind_health()
    with pytest.raises(ValueError):verifier.verify_health()
    with pytest.raises(ValueError):verifier.bind_health()


def test_tracked_hashes_must_match_authoritative_proof(capsule,monkeypatch):
    verifier=verifier_for(capsule);real=verifier.verify
    def wrong_digest():
        head,config,raw=real();return head,config,{name:'0'*64 for name in raw}
    monkeypatch.setattr(verifier,'verify',wrong_digest)
    with pytest.raises(ValueError):verifier.bind_health()


def test_mutation_during_byte_sampling_is_rejected(capsule,monkeypatch):
    root,_,_=capsule;verifier=verifier_for(capsule);verifier.bind_health()
    original=verifier._namespace;calls=0
    def interleaved():
        nonlocal calls
        result=original();calls+=1
        if calls==1:(root/'.git/refs/during-sampling').mkdir()
        return result
    monkeypatch.setattr(verifier,'_namespace',interleaved)
    with pytest.raises(ValueError):verifier.verify_health()

def test_namespace_bounds_real_directory_depth_before_recursion(tmp_path):
    root=tmp_path/'depth';root.mkdir();leaf=root
    for _ in range(128):
        leaf=leaf/'d';leaf.mkdir()
    verifier=service.SourceVerifier(root,None)
    assert len(verifier._namespace())==129
    (leaf/'d').mkdir()
    with pytest.raises(ValueError,match='HEADLESS_SERVICE_REJECTED'):
        verifier._namespace()
