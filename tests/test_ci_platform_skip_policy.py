"""Source-collected skip policy must agree with platform-only test markers."""
import hashlib
import json
from types import SimpleNamespace
import pytest
from scripts.integration_synthetic_boundary import pytest_collection_finish

@pytest.mark.parametrize('platform,scope,allowed', [('win32','full',True),('linux','full',False),('win32','synthetic',False)])
def test_windows_posix_filename_case_skip_is_narrow(monkeypatch,tmp_path,platform,scope,allowed):
    name='test_untracked_index_record_spoof_cannot_replace_removed_index_entry'
    nodeid='tests/test_headless_service.py::'+name
    output=tmp_path/'identities.json'
    monkeypatch.setenv('META_ANALYSE_SYNTHETIC_IDENTITIES',str(output))
    monkeypatch.setenv('META_ANALYSE_CI_IDENTITY_SCOPE',scope)
    monkeypatch.setattr('sys.platform',platform)
    monkeypatch.setattr('subprocess.check_output',lambda *a,**kw:'a'*40)
    pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid=nodeid,name=name)]))
    manifest=json.loads(output.read_text())
    digest='case_'+hashlib.sha256((json.dumps(['tests.test_headless_service',name],separators=(',',':'))+'\n').encode()).hexdigest()
    assert manifest['identities']==[digest]
    assert manifest['allowed_skips']==([digest] if allowed else [])
