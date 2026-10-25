"""Independent PR43 source-only and adversarial model gate; no native collection."""
import ast
from collections import Counter
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
ADAPTER=(ROOT/'commissioning/native_scm_diagnostic.py').read_text(encoding='utf8')
CLASSIFIER=(ROOT/'commissioning/process_identity.py').read_text(encoding='utf8')
BUCKETS=('BOTH_FAILED','REGISTRY_ONLY_FAILED','SCM_ONLY_FAILED','NEITHER_FAILED','NOT_EVALUATED')

def model(pairs):
    out=Counter({k:0 for k in BUCKETS})
    for registry,scm,complete in pairs:
        if complete is not True:
            out['NOT_EVALUATED']+=1
            continue
        a=type(registry) is int and registry==32
        b=type(scm) is int and scm==32
        out['NEITHER_FAILED' if a and b else 'SCM_ONLY_FAILED' if a else 'REGISTRY_ONLY_FAILED' if b else 'BOTH_FAILED']+=1
    return dict(out)

class SCMOracle(unittest.TestCase):
    def test_same_marginals_different_cooccurrence(self):
        same=[(16,16,True)]+[(32,32,True)]*4
        split=[(16,32,True),(32,16,True)]+[(32,32,True)]*3
        self.assertEqual(model(same)['BOTH_FAILED'],1)
        self.assertEqual(model(split)['BOTH_FAILED'],0)
        self.assertEqual(model(split)['REGISTRY_ONLY_FAILED'],1)
        self.assertEqual(model(split)['SCM_ONLY_FAILED'],1)
    def test_exact_type_rejects_coercions(self):
        for x in (True,32.0,'32',16,0x120,None):
            self.assertEqual(model([(x,32,True)])['REGISTRY_ONLY_FAILED'],1)
            self.assertEqual(model([(32,x,True)])['SCM_ONLY_FAILED'],1)
    def test_invalid_lifetime_does_not_create_identity(self):
        self.assertIn("require(item['pid']==row['pid'],'LIFETIME_BINDING_INVALID')",ADAPTER)
        self.assertIn("require(all(t==times[0] for t in times),'LIFETIME_BINDING_INVALID')",ADAPTER)
        self.assertIn("require(row==by_id[row['pid']]['process'])",ADAPTER)
    def test_no_new_privileged_native_operations(self):
        for forbidden in ('SeDebugPrivilege','AdjustTokenPrivileges','OpenProcessToken','SetServiceStatus','RegSetValue','WriteProcessMemory'):
            self.assertNotIn(forbidden,ADAPTER)
    def test_unknown_not_neither(self):
        self.assertEqual(model([(32,32,False)])['NOT_EVALUATED'],1)
    def test_per_member_projection_source(self):
        tree=ast.parse(ADAPTER)
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='config_checks')
        src=ast.get_source_segment(ADAPTER,fn)
        self.assertIn('for service in services:',src)
        self.assertIn('identity.service_host_configuration_checks(service,c,roots)',src)
        for k in BUCKETS:self.assertIn(k,ADAPTER)
        self.assertIn("proof['services_'+phase+'_complete']",src)
    def test_no_new_classifier_path(self):
        self.assertIn("status='FAIL_CLOSED'",ADAPTER)
        self.assertIn("authorization='NONE'",ADAPTER)
        self.assertNotIn('def classify_missing(',ADAPTER)
        self.assertIn("type(config.get('service_type')) is int and config.get('service_type')==32",CLASSIFIER)
        self.assertIn("type(svc.get('service_type')) is int and svc.get('service_type')==32",CLASSIFIER)
    def test_snapshot_binding_guards(self):
        for token in ("LIFETIME_BINDING_INVALID","PROCESS_SNAPSHOT_BINDING_INVALID","source_binding(args.expected_sha,args.expected_tree)"):
            self.assertIn(token,ADAPTER)

if __name__=='__main__':unittest.main()
