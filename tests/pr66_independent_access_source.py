"""Independent source-only security regression for PR66; no Win32 calls."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
ACCESS=(ROOT/'scripts/g0_windows_access.py').read_text(encoding='utf8')
REVIEW=(ROOT/'scripts/g0_access_review.py').read_text(encoding='utf8')
class Contracts(unittest.TestCase):
 def test_authority_is_not_authenticated_by_manifest(self):
  # RED condition: independent authority validation is not yet implemented.
  self.assertIn("item['authority_sha256']",REVIEW)
  self.assertIn("loader_scope='INDEPENDENT_REVIEW_REQUIRED'",REVIEW)
  self.assertNotIn("readiness='PASS'",REVIEW)
 def test_only_current_token_not_other_subjects(self):
  self.assertIn("other_subjects='NOT_EVALUATED'",REVIEW)
  self.assertIn("namespace_safety='NOT_ATTESTED'",REVIEW)
 def test_no_privilege_adjustment(self):
  self.assertNotIn('AdjustTokenPrivileges',ACCESS)
  self.assertIn('OpenThreadToken',ACCESS)
  self.assertIn('DuplicateToken',ACCESS)
 def test_native_cleanup_and_identity(self):
  for value in ('LocalFree','CloseHandle','GetFileInformationByHandle','GetSecurityInfo','AccessCheck','TokenStats'):
   self.assertIn(value,ACCESS)
 def test_no_namespace_creation(self):
  for value in ('CreateDirectoryW','SetNamedSecurityInfo','SetFileSecurity','MoveFileExW'):
   self.assertNotIn(value,ACCESS)
if __name__=='__main__':unittest.main()
