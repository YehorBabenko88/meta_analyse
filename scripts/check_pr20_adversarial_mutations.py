"""Twelve fresh in-memory mutation operators; no native/host/DB operations."""
import argparse
import copy
import json
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_process_identity_acceptance import fixture,add_topology,ROOTS,CONTRACTS


def altered(name,tag):
    row,e=fixture(name)
    if tag.startswith('kernel-'):
        add_topology(row,e)
        if tag=='kernel-parent-binding':
            for key in ('kernel_before','kernel_after'):e[key]['parent_pid']=999
        if tag=='kernel-name-binding':
            for key in ('kernel_before','kernel_after'):e[key]['name']='Registry'
        if tag=='kernel-snapshot-equality':e['kernel_after']['name']='Registry'
        if tag=='kernel-type-check':
            row['parent_pid']=0
            for key in ('kernel_before','kernel_after'):e[key]['parent_pid']=False
    if tag=='native-alive':
        for key in ('native_before','native_after'):e[key]['alive']=False
    if tag=='cim-creation':row['created']+=1000
    if tag=='signature-path':e['signature']['path']=r'C:\Other\signed.exe'
    if tag=='signature-reparse':e['signature']['reparse_point']=True
    if tag=='scm-completeness':e['services_after_complete']=False
    if tag=='contract-native-host':
        host=CONTRACTS[name][0];path='C:\\Other\\'+host
        for key in ('native_before','native_after','signature'):e[key]['path']=path
        for key in ('services_before','services_after'):
            e[key][0]['binary_path']=path+(' '+CONTRACTS[name][2] if CONTRACTS[name][2] else '')
    if tag=='contract-account':
        for suffix in ('before','after'):
            e['services_'+suffix][0]['start_name']='OtherAccount'
            e['implementation_'+suffix][name]['account']='OtherAccount'
    if tag=='integrated-empty-string':
        for key in ('implementation_before','implementation_after'):e[key][name].pop('expanded_dll_path')
    return row,e


MUTATIONS=[
 ('kernel-parent-binding',"if any(first[k]!=row[k] for k in ('pid','parent_pid','session_id')):",'if False:'),
 ('kernel-name-binding',"or first['name'].casefold()!=row['name'].casefold()",'or False'),
 ('kernel-snapshot-equality',"if first!=last:return 'KERNEL_IDENTITY_CONFLICT'",'if False:pass'),
 ('kernel-type-check',"if any(type(item.get(k)) is not int or not 0<=item[k]<=0x7fffffff\n               for k in ('pid','parent_pid','session_id')):",'if False:'),
 ('native-alive',"if any(n.get('alive') is not True for n in (before,after)):",'if False:'),
 ('cim-creation',"if any(not same_creation(row['created'],n['created']) for n in (before,after)):",'if False:'),
 ('signature-path',"if canonical(sig.get('path'))!=path:",'if False:'),
 ('signature-reparse',"if sig.get('reparse_point') is not False:",'if False:'),
 ('scm-completeness',"if evidence.get('services_before_complete') is not True or evidence.get('services_after_complete') is not True or 'services_before' not in evidence or 'services_after' not in evidence:",'if False:'),
 ('contract-native-host',"if canonical(native['path'])!=host_path:",'if False:'),
 ('contract-account',"or str(c.get('account','')).casefold()!=account or str(svc.get('start_name','')).casefold()!=account",'or False'),
 ('integrated-empty-string',"c.get('expanded_dll_path')!=''","bool(c.get('expanded_dll_path'))"),
]


def load(source):
    m=types.ModuleType('pure_security_mutant');exec(compile(source,'<pure-security-mutant>','exec'),m.__dict__);return m


def controls(m):
    for name in CONTRACTS:
        row,e=fixture(name);assert m.classify_missing(row,e,ROOTS)['status']=='VERIFIED_SERVICE'
    row,e=fixture();row['name']='winlogon.exe'
    for key in ('native_before','native_after','signature'):e[key]['path']=ROOTS['system32']+'\\winlogon.exe'
    for key in ('services_before','services_after'):e[key]=[]
    assert m.classify_missing(row,e,ROOTS)['status']=='VERIFIED_SYSTEM_IMAGE'
    for pid in (0,4):
        row=dict(pid=pid,name='System' if pid else 'System Idle Process',parent_pid=0,session_id=0,created=123456789012345670)
        k=dict(row,name='System' if pid else '')
        assert m.classify_missing(row,dict(kernel_before=k,kernel_after=copy.deepcopy(k)),ROOTS)['status']=='VERIFIED_KERNEL'


def main():
    a=argparse.ArgumentParser();a.add_argument('--source',type=Path,default=ROOT/'commissioning/process_identity.py');a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    source=args.source.read_text(encoding='utf-8-sig');baseline=load(source);controls(baseline)
    results=[];gaps=[]
    for tag,old,new in MUTATIONS:
        names=['SamSs'] if tag=='integrated-empty-string' else list(CONTRACTS)
        for name in names:
            row,e=altered(name,tag)
            if baseline.classify_missing(row,e,ROOTS)['status']!='UNRESOLVED':gaps.append(dict(predicate=tag,contract=name))
        if source.count(old)==0:
            results.append(dict(predicate=tag,result='INAPPLICABLE'));continue
        assert source.count(old)==1,(tag,source.count(old))
        mutant=load(source.replace(old,new));controls(mutant)
        killed=[]
        for name in names:
            row,e=altered(name,tag)
            if baseline.classify_missing(row,e,ROOTS)['status']=='UNRESOLVED' and mutant.classify_missing(row,e,ROOTS)['status']!='UNRESOLVED':killed.append(name)
        results.append(dict(predicate=tag,result='KILLED' if len(killed)==len(names) else 'SURVIVED',witnesses=killed,expected_witnesses=len(names)))
    report=dict(operators='12 distinct from earlier 15',positive_controls_per_mutant=8,baseline_gaps=gaps,mutations=results,killed=sum(r['result']=='KILLED' for r in results),survived=sum(r['result']=='SURVIVED' for r in results),inapplicable=sum(r['result']=='INAPPLICABLE' for r in results))
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"new operators: killed={report['killed']} survived={report['survived']} inapplicable={report['inapplicable']} baseline_gaps={len(gaps)}")
    if gaps or report['survived'] or report['inapplicable']:raise SystemExit(1)


if __name__=='__main__':main()
