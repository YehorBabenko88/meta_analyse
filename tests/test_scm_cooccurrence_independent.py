"""Independent, synthetic-only SCM co-occurrence contract tests. No ADMINIT access."""
import ast
from collections import Counter
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'commissioning'/'process_identity.py'
ADAPTER=ROOT/'commissioning'/'native_scm_diagnostic.py'

def aggregate(pairs):
    """Diagnostic model: correlate predicates within one member, not marginal totals."""
    out=Counter()
    for registry,scm in pairs:
        if type(registry) is not int or registry!=32:
            r=False
        else:r=True
        if type(scm) is not int or scm!=32:
            s=False
        else:s=True
        out['BOTH_PASS' if r and s else 'REGISTRY_ONLY_FAIL' if not r and s else
            'SCM_ONLY_FAIL' if r and not s else 'BOTH_FAIL']+=1
    return dict(out)

class IndependentContracts(unittest.TestCase):
    def test_marginals_do_not_prove_same_member(self):
        one=[(16,16),(32,32),(32,32),(32,32),(32,32)]
        separate=[(16,32),(32,16),(32,32),(32,32),(32,32)]
        for pairs in (one,separate):
            self.assertEqual(sum(type(r) is not int or r!=32 for r,_ in pairs),1)
            self.assertEqual(sum(type(s) is not int or s!=32 for _,s in pairs),1)
        self.assertEqual(aggregate(one)['BOTH_FAIL'],1)
        self.assertEqual(aggregate(separate)['REGISTRY_ONLY_FAIL'],1)
        self.assertEqual(aggregate(separate)['SCM_ONLY_FAIL'],1)
    def test_exact_int32_and_no_mask_or_numeric_coercion(self):
        for wrong in (True,32.0,'32',16,0x120,None,-1):
            self.assertEqual(aggregate([(wrong,32)]),{'REGISTRY_ONLY_FAIL':1})
            self.assertEqual(aggregate([(32,wrong)]),{'SCM_ONLY_FAIL':1})
        self.assertEqual(aggregate([(32,32)]),{'BOTH_PASS':1})
    def test_shared_host_members_are_independent(self):
        # Two members can have the same PID/host while different type outcomes.
        self.assertEqual(aggregate([(16,32),(32,16)]),
                         {'REGISTRY_ONLY_FAIL':1,'SCM_ONLY_FAIL':1})
    def test_projection_source_has_no_admission_or_persistence(self):
        src=ADAPTER.read_text(encoding='utf8')
        tree=ast.parse(src)
        names={n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        self.assertIn('project',names)
        self.assertIn('source_binding',names)
        self.assertNotIn('classify_missing',names)
        self.assertNotIn('save_private',names)
        self.assertIn("status='FAIL_CLOSED'",src)
        self.assertIn("authorization='NONE'",src)
    def test_original_exact_type_predicates_remain(self):
        src=SOURCE.read_text(encoding='utf8')
        self.assertIn("type(config.get('service_type')) is int and config.get('service_type')==32",src)
        self.assertIn("type(svc.get('service_type')) is int and svc.get('service_type')==32",src)
    def test_no_raw_rare_member_identifiers_in_aggregate(self):
        out=aggregate([(16,32),(32,16)])
        self.assertFalse(any(k in repr(out) for k in ('KeyIso','SamSs','VaultSvc','DoSvc','wscsvc','pid','path')))
    def test_wrong_pid_or_creation_requires_rejection_in_existing_adapter(self):
        src=ADAPTER.read_text(encoding='utf8')
        self.assertIn("require(service['pid']==row['pid'],'LIFETIME_BINDING_INVALID')",src)
        self.assertIn("require(item['pid']==row['pid'],'LIFETIME_BINDING_INVALID')",src)
        self.assertIn("require(all(t==times[0] for t in times),'LIFETIME_BINDING_INVALID')",src)

if __name__=='__main__':unittest.main()
