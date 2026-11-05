"""The hash-pinned dependency lock must retain committed bytes on Windows."""
import os
from pathlib import Path
import subprocess
import tempfile


def test_dependency_lock_survives_real_autocrlf_checkout():
    root=Path(__file__).resolve().parents[1]
    expected=subprocess.check_output(['git','--no-replace-objects','-C',str(root),'cat-file','blob','HEAD:requirements.lock'])
    with tempfile.TemporaryDirectory(prefix='mission3-meta-autocrlf-') as temp:
        repo=Path(temp)
        def git(*args):return subprocess.check_output(['git','-c','core.hooksPath='+os.devnull,'-C',str(repo),*args],stderr=subprocess.PIPE)
        git('init');git('config','core.autocrlf','false')
        if (root/'.gitattributes').exists():(repo/'.gitattributes').write_bytes((root/'.gitattributes').read_bytes())
        target=repo/'requirements.lock';target.write_bytes(expected)
        git('add','.');git('-c','user.name=Lab','-c','user.email=lab@example.invalid','commit','-m','lock bytes')
        git('config','core.autocrlf','true');target.unlink();git('checkout','HEAD','--','requirements.lock')
        assert target.read_bytes()==expected,'Windows autocrlf altered hash-pinned dependency lock'
