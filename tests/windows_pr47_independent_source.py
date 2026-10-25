"""Independent offline Windows/SCM source guard, no native calls or pytest conftest."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def read(path):return (ROOT/path).read_text(encoding='utf8')
class SourceGuard(unittest.TestCase):
 def test_fail_closed_diagnostic(self):
  src=read('commissioning/native_scm_diagnostic.py')
  self.assertIn("status='FAIL_CLOSED'",src)
  self.assertIn("authorization='NONE'",src)
  self.assertIn('return 1',src)
  self.assertNotIn('def classify_missing(',src)
 def test_strict_shared_host_contract(self):
  src=read('commissioning/process_identity.py')
  self.assertIn("type(config.get('service_type')) is int and config.get('service_type')==32",src)
  self.assertIn("type(svc.get('service_type')) is int and svc.get('service_type')==32",src)
  self.assertIn('def service_implementation_refusal(',src)
 def test_cooccurrence_not_evaluated(self):
  src=read('commissioning/native_scm_diagnostic.py')
  for name in ('BOTH_FAILED','REGISTRY_ONLY_FAILED','SCM_ONLY_FAILED','NEITHER_FAILED','NOT_EVALUATED'):
   self.assertIn(name,src)
  self.assertIn('for service in services:',src)
  self.assertIn("proof['services_'+phase+'_complete']",src)
 def test_pid_creation_source_binding(self):
  src=read('commissioning/native_scm_diagnostic.py')
  for x in ("LIFETIME_BINDING_INVALID","source_binding(args.expected_sha,args.expected_tree)","require(row==by_id[row['pid']]['process'])"):
   self.assertIn(x,src)
 def test_no_forced_bypass_in_g0(self):
  src=read('commissioning/adminit-g0-readonly.ps1')
  self.assertNotIn('-ExecutionPolicy Bypass',src)
 def test_no_privilege_escalation_in_diagnostic(self):
  src=read('commissioning/native_scm_diagnostic.py')
  for x in ('SeDebugPrivilege','AdjustTokenPrivileges','WriteProcessMemory','SetServiceStatus'):
   self.assertNotIn(x,src)
if __name__=='__main__':unittest.main()
