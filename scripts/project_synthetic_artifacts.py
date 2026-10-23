"""Project synthetic JUnit to approved identities/statuses; validate JSON outputs.

No host APIs. Raw runner metadata, parameter text, paths, properties, stdout and
tracebacks never survive projection. This is intentionally narrower than logs.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'commissioning'))
from evidence_schema import json_value


def need(value):
    if not value:raise ValueError('PUBLIC_SCHEMA_REJECTED')


def read_json(path):
    def unique(pairs):
        value={}
        for key,item in pairs:need(key not in value);value[key]=item
        return value
    value=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique)
    json_value(value)
    return value


def identity(classname,name):
    root=name.split('[',1)[0]
    allowed=ROOT/'tests'/(classname.split('.')[-1]+'.py')
    need(classname.startswith('tests.test_') and re.fullmatch(r'tests\.test_[a-z0-9_]+',classname) is not None and allowed.is_file())
    functions={n.name for n in ast.walk(ast.parse(allowed.read_text(encoding='utf-8-sig'))) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    need(root in functions and root.startswith('test_'))
    return root if name==root else root+'[sha256:'+hashlib.sha256(name.encode()).hexdigest()+']'


def validate_raw_structure(node):
    if node.tag in ('testsuites','testsuite'):
        children={'testsuite','properties','system-out','system-err'}
        if node.tag=='testsuite':children.add('testcase')
        need(all(child.tag in children for child in node))
        cases=[]
        for child in node:
            if child.tag in ('testsuite','testcase'):cases.extend(validate_raw_structure(child))
            else:need(not any(n.tag in ('testcase','testsuite','testsuites','error','failure','skipped') for n in child.iter()))
        counts=dict(tests=len(cases),errors=sum(c.find('error') is not None for c in cases),
                    failures=sum(c.find('failure') is not None for c in cases),
                    skipped=sum(c.find('skipped') is not None for c in cases))
        for key,count in counts.items():
            if key in node.attrib:need(node.get(key)==str(count))
        return cases
    need(node.tag=='testcase')
    need(all(child.tag in ('error','failure','skipped','properties','system-out','system-err') for child in node))
    need(sum(child.tag in ('error','failure','skipped') for child in node)<=1)
    # Metadata/status payloads may contain text, never nested test records.
    need(not any(child.tag in ('testcase','testsuite','testsuites','error','failure','skipped') for outer in node for child in outer.iter() if child is not outer))
    return [node]


def project_junit(path):
    need(path.stat().st_size<=8*1024*1024)
    tree=ET.parse(path);cases=validate_raw_structure(tree.getroot());need(bool(cases))
    identities=set();result=ET.Element('testsuites',name='synthetic')
    suite=ET.SubElement(result,'testsuite',name='synthetic-identity')
    counts=dict(tests=len(cases),errors=0,failures=0,skipped=0)
    for case in cases:
        classname=case.get('classname','');name=identity(classname,case.get('name',''))
        need((classname,name) not in identities);identities.add((classname,name))
        clean=ET.SubElement(suite,'testcase',classname=classname,name=name)
        for tag,counter in [('error','errors'),('failure','failures'),('skipped','skipped')]:
            if case.find(tag) is not None:
                counts[counter]+=1
                ET.SubElement(clean,tag,message='Synthetic status; raw detail omitted')
    for key,value in counts.items():suite.set(key,str(value))
    ET.ElementTree(result).write(path,encoding='utf-8',xml_declaration=True)
    validate_junit(path)


def validate_junit(path):
    tree=ET.parse(path);root=tree.getroot()
    need(all(not (n.text or '').strip() and not (n.tail or '').strip() for n in root.iter()))
    need(path.read_bytes().replace(b'\r\n',b'\n')==ET.tostring(root,encoding='utf-8',xml_declaration=True))
    need(root.tag=='testsuites' and root.attrib=={'name':'synthetic'} and len(root)==1)
    suite=root[0];need(suite.tag=='testsuite' and set(suite.attrib)=={'name','tests','errors','failures','skipped'})
    need(suite.get('name')=='synthetic-identity');counts=dict(tests=0,errors=0,failures=0,skipped=0);seen=set()
    for case in suite:
        need(case.tag=='testcase' and set(case.attrib)=={'classname','name'} and not (case.text or '').strip())
        cls,name=case.get('classname'),case.get('name');rootname=name.split('[',1)[0]
        need(identity(cls,rootname)==rootname)
        need(name==rootname or re.fullmatch(re.escape(rootname)+r'\[sha256:[0-9a-f]{64}\]',name) is not None)
        need((cls,name) not in seen);seen.add((cls,name));counts['tests']+=1
        need(len(case)<=1)
        for status in case:
            need(status.tag in ('error','failure','skipped') and status.attrib=={'message':'Synthetic status; raw detail omitted'} and not list(status) and not status.text)
            counts[{'error':'errors','failure':'failures','skipped':'skipped'}[status.tag]]+=1
    need(all(suite.get(key)==str(value) for key,value in counts.items()))


def validate_source(path):
    value=read_json(path);need(set(value)=={'sha','expected_sha','event','event_sha','tree_sha'})
    need(value['event'] in ('push','pull_request','workflow_dispatch','local-synthetic'))
    for key in ('sha','expected_sha','event_sha','tree_sha'):need(type(value[key]) is str and re.fullmatch('[0-9a-f]{40}',value[key]) is not None)
    need(value['sha']==value['expected_sha'])


def validate_mutations(path):
    value=read_json(path)
    allowed={'positive_controls','positive_controls_per_mutant','baseline_negative_cases','baseline_admission_gaps',
        'baseline_gaps','operators','mutations','killed','defended','survived','inapplicable'}
    need(type(value) is dict and set(value)<=allowed)
    tags=set()
    for name in ('check_process_identity_mutations.py','check_pr20_adversarial_mutations.py','check_evidence_schema_mutations.py'):
        tree=ast.parse((ROOT/'scripts'/name).read_text(encoding='utf-8-sig'))
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MUTATIONS' for t in node.targets):
                tags.update(row[0] for row in ast.literal_eval(node.value))
    for key,item in value.items():
        if key in ('baseline_admission_gaps','baseline_gaps'):need(item==[])
        elif key=='operators':need(item=='12 distinct from earlier 15')
        elif key!='mutations':need(type(item) is int and 0<=item<=10000)
    need(type(value.get('mutations')) is list)
    contracts={'KeyIso','SamSs','VaultSvc','DoSvc','wscsvc'}
    for mutation in value['mutations']:
        need(set(mutation)<={'predicate','result','baseline_rejected','witnesses','composite_witnesses','expected_witnesses'})
        need(mutation['predicate'] in tags and mutation['result'] in ('KILLED','DEFENDED_BY_SCHEMA'))
        for key,item in mutation.items():
            if key in ('witnesses','composite_witnesses'):need(type(item) is list and all(v in contracts for v in item))
            elif key in ('baseline_rejected','expected_witnesses'):need(type(item) is int and 0<=item<=5)


def main():
    p=argparse.ArgumentParser();p.add_argument('--junit',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--mutations',type=Path,action='append',default=[]);p.add_argument('--validate-only',action='store_true');args=p.parse_args()
    if not args.validate_only:project_junit(args.junit)
    validate_junit(args.junit);validate_source(args.source)
    for path in args.mutations:validate_mutations(path)
    print('Strict synthetic artifact projection/schema PASS')


if __name__=='__main__':main()
