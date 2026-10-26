"""Pure in-memory admission mutations; never execute the native collector.

Use --source to audit a frozen historical classifier. Missing mutation anchors
are reported as inapplicable, not killed; baseline negative gaps are reported.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_process_identity_acceptance import fixture, add_topology, CONTRACTS, ROOTS


def ordinary_fixture():
    row, proof = fixture()
    row['name'] = 'winlogon.exe'
    path = ROOTS['system32'] + r'\winlogon.exe'
    for key in ('native_before', 'native_after', 'signature'): proof[key]['path'] = path
    for key in ('services_before', 'services_after'): proof[key] = []
    for key in ('modules_before','modules_after','implementation_before','implementation_after','implementation_signatures'):proof.pop(key)
    return row, proof


def negative(name, tag):
    row, proof = fixture(name)
    if tag == 'empty-scm':
        proof['services_before'] = proof['services_after'] = []
    elif tag == 'duplicate-scm':
        for key in ('services_before', 'services_after'): proof[key].append(copy.deepcopy(proof[key][0]))
    elif tag == 'unsigned-host': proof['signature']['status'] = 'NotSigned'
    elif tag == 'host-hash': proof['signature']['sha256_after'] = 'b' * 64
    elif tag == 'missing-module':
        for key in ('modules_before', 'modules_after'): proof[key]['paths'] = proof[key]['paths'][:1]
    elif tag == 'unsigned-dll': proof['implementation_signatures'][name]['status'] = 'NotSigned'
    elif tag == 'native-reuse': proof['native_after']['created'] += 1
    elif tag == 'after-type': proof['services_after'][0]['pid'] = 123.0
    elif tag in ('missing-config-stage', 'missing-module-stage', 'missing-scm-stage'):
        source = {'missing-config-stage': 'implementation', 'missing-module-stage': 'modules', 'missing-scm-stage': 'services'}[tag]
        for suffix in ('before', 'after'):
            item = proof[source + '_' + suffix]
            if source == 'implementation': item = item[name]
            if source == 'services': item = item[0]
            item.pop('error_stage')
    elif tag == 'topology-conflict':
        add_topology(row, proof)
        proof['kernel_after']['created'] += 1
    elif tag == 'host-arguments':
        for suffix in ('before', 'after'):
            proof['services_' + suffix][0]['binary_path'] += ' -s Unreviewed'
            proof['implementation_' + suffix][name]['expanded_image_path'] += ' -s Unreviewed'
    elif tag == 'arbitrary-kernel':
        add_topology(row, proof)
        for key in ('native_before', 'native_after'):
            proof[key].update(path='', image_query_succeeded=False, error_stage='QUERY_IMAGE', win32_error=31)
    elif tag == 'special-mixed':
        row = dict(pid=4, name='System', parent_pid=0, session_id=0, created=row['created'])
        topology = dict(row)
        proof = dict(kernel_before=topology, kernel_after=copy.deepcopy(topology), native_before={'path': 'conflict'})
    else: raise AssertionError(tag)
    return row, proof


MUTATIONS = [
    ('empty-scm', "if known_service_image and not services:", 'if False:'),
    ('duplicate-scm', "if len(names)!=len({name.casefold() for name in names}):", 'if False:'),
    ('unsigned-host', "if sig.get('status')!='Valid':", 'if False:'),
    ('host-hash', "if sig['sha256']!=sig.get('sha256_after'):", 'if False:'),
    ('missing-module', 'if not {host_path,dll_path}.issubset(sets[0]):', 'if False:'),
    ('unsigned-dll', "if (sig.get('status')!='Valid' or", 'if (False or'),
    ('native-reuse', "if before['created']!=after['created']:", 'if False:'),
    ('after-type', 'for snapshot in (services,after_services):', 'for snapshot in (services,):'),
    ('missing-config-stage', "or c.get('error_stage')!='' for", "or bool(c.get('error_stage')) for"),
    ('missing-module-stage', "modules.get('error_stage')!=''", "bool(modules.get('error_stage'))"),
    ('missing-scm-stage', "svc.get('error_stage')!=''", "bool(svc.get('error_stage'))"),
    ('topology-conflict', "if 'kernel_before' in evidence or 'kernel_after' in evidence:", 'if False:'),
    ('host-arguments', "or command_arguments(c.get('expanded_image_path'))!=args or command_arguments(svc.get('binary_path'))!=args", 'or False'),
    ('arbitrary-kernel', "return blocked('IMAGE_PATH_UNAVAILABLE')", "return dict(status='VERIFIED_KERNEL',reason_code='MUTATION_ONLY')"),
    ('special-mixed', "if set(evidence)-{'kernel_before','kernel_after','collection_error'}:", 'if False:'),
]


CURRENT_TARGETS = {'host-arguments': ("REGISTRY_ARGS_MATCH=command_arguments(config.get('expanded_image_path'))==args,\n        SCM_ARGS_MATCH=command_arguments(svc.get('binary_path'))==args", 'REGISTRY_ARGS_MATCH=True,\n        SCM_ARGS_MATCH=True')}


def load(text):
    module = types.ModuleType('synthetic_mutated_classifier')
    exec(compile(text, '<synthetic-classifier>', 'exec'), module.__dict__)
    return module


def probe(module, tag, name):
    row, proof = negative(name, tag)
    return module.classify_missing(row, proof, ROOTS)['status'] == 'UNRESOLVED'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'commissioning/process_identity.py')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text(encoding='utf-8-sig')
    baseline = load(source)
    for name in CONTRACTS:
        row, proof = fixture(name)
        assert baseline.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SERVICE'
    row, proof = ordinary_fixture()
    assert baseline.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SYSTEM_IMAGE'
    gaps = [{'predicate': tag, 'contract': name} for tag, _, _ in MUTATIONS
            for name in CONTRACTS if not probe(baseline, tag, name)]
    results = []
    for tag, old, new in MUTATIONS:
        if source.count(old)==0 and tag in CURRENT_TARGETS:
            old,new=CURRENT_TARGETS[tag]
        count = source.count(old)
        if count == 0:
            results.append(dict(predicate=tag, result='INAPPLICABLE'))
            continue
        assert count == 1, (tag, count)
        mutant = load(source.replace(old, new))
        # Positive controls must survive; otherwise this is a broken mutant.
        for name in CONTRACTS:
            row, proof = fixture(name)
            assert mutant.classify_missing(row, proof, ROOTS)['status'] == 'VERIFIED_SERVICE', tag
        original_rejected = [name for name in CONTRACTS if probe(baseline, tag, name)]
        killed = [name for name in original_rejected if not probe(mutant, tag, name)]
        defended=[]
        if not killed and original_rejected and 'validate_success(row,evidence,roots)' in source:
            schema_off=load(source.replace('validate_success(row,evidence,roots)','None'))
            assert all(probe(schema_off,tag,n) for n in original_rejected)
            double=load(source.replace(old,new).replace('validate_success(row,evidence,roots)','None'))
            for n in CONTRACTS:
                r,e=fixture(n);assert double.classify_missing(r,e,ROOTS)['status']=='VERIFIED_SERVICE'
            defended=[n for n in original_rejected if not probe(double,tag,n)]
        result = 'KILLED' if killed else ('DEFENDED_BY_SCHEMA' if defended else ('SURVIVED' if original_rejected else 'BASELINE_GAP'))
        results.append(dict(predicate=tag, result=result,
                            baseline_rejected=len(original_rejected), witnesses=killed, composite_witnesses=defended))
    report = dict(positive_controls=6, baseline_negative_cases=75, baseline_admission_gaps=gaps,
                  mutations=results, killed=sum(r['result']=='KILLED' for r in results),
                  defended=sum(r['result']=='DEFENDED_BY_SCHEMA' for r in results),
                  survived=sum(r['result']=='SURVIVED' for r in results),
                  inapplicable=sum(r['result']=='INAPPLICABLE' for r in results))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"baseline gaps={len(gaps)} killed={report['killed']} defended={report['defended']} survived={report['survived']} inapplicable={report['inapplicable']}")
    if gaps or report['survived'] or report['inapplicable']: raise SystemExit(1)


if __name__ == '__main__':
    main()
