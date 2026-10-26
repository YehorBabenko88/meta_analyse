"""Offline G0 record review. No collection, signature verification or authority."""
import argparse
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
import time

LIMIT=1024*1024
COMMON=frozenset(('PYTHON_EXE','PYTHON_DLL','PYTHON_STDLIB','PYTHON_LOADER','CRT',
                  'POWERSHELL','GIT','GIT_RUNTIME','NETSH','DOTNET_RUNTIME','NATIVE_DLLS'))
NATIVE=frozenset(('CSHARP_COMPILER',))
CHECKS=frozenset(('host_context','elevation','tool_loader','postgres_5432_isolated',
                  'metascalp_read_only_plan','ci_exact','resources_reviewed','operator_scope'))
NAMESPACE=frozenset(('absolute_local','outside_source_and_runtime','leaf_absent',
                     'ancestors_checked','no_reparse','link_counts_reviewed',
                     'isolated_writer_scope','exclusive_create_reviewed'))
POLICIES=frozenset(('Undefined','Restricted','AllSigned','RemoteSigned','Unrestricted','Bypass'))
SOURCE=frozenset(('sha','tree','collector_manifest_sha256','scripts_signed'))
TOOL=frozenset(('sha256','authority_sha256','basis'))
POLICY=frozenset(('machine_policy','user_policy','process','current_user','local_machine',
                  'effective','language_mode','process_override_present','scripts_signed',
                  'script_policy_reviewed','motw_reviewed','add_type_chain_reviewed','temp_namespace_reviewed'))
REASONS=frozenset(('MALFORMED_EVIDENCE','BASELINE_UNAPPROVED','SOURCE_UNBOUND','STALE_RECORDS',
                   'TOOLS_UNAPPROVED','POLICY_UNREVIEWED','NAMESPACE_UNREVIEWED','PREFLIGHT_REFUSED',
                   'RECORDS_CONSISTENT','OUTPUT_UNAVAILABLE'))


class Refusal(ValueError):
    def __init__(self,code='MALFORMED_EVIDENCE'):
        self.code=code if code in REASONS else 'MALFORMED_EVIDENCE'
        super().__init__(self.code)


def need(condition,code='MALFORMED_EVIDENCE'):
    if not condition:raise Refusal(code)


def record(value,keys):
    need(type(value) is dict and set(value)==set(keys))


def hexstring(value,length):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is not None


def strict_object(raw):
    need(type(raw) is bytes and len(raw)<=LIMIT)
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result);result[key]=value
        return result
    def invalid(_):raise Refusal()
    try:value=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)
    except Exception:raise Refusal() from None
    need(type(value) is dict)
    return value


def report(code,source=None):
    return dict(schema=1,status='FAIL_CLOSED',authorization='NONE',
                diagnostic_status='OFFLINE_PREFLIGHT_RECORD_REVIEW',
                evidence_authenticity='OPERATOR_REVIEW_REQUIRED',
                readiness='READY_FOR_OPERATOR_REVIEW' if code=='RECORDS_CONSISTENT' else 'BLOCKED',
                reason_codes=[code],source=source)


def review(evidence,baseline_bytes,approved_digest,*,expected_sha,expected_tree,session,now):
    """Compare records only; caller must authenticate their origin independently.

    approved_digest must arrive over an independently approved channel, not be
    computed from the candidate baseline in the same operation. This function
    cannot authenticate that human decision, a Windows signature or host facts.
    """
    try:
        need(hexstring(approved_digest,64) and type(baseline_bytes) is bytes,'BASELINE_UNAPPROVED')
        need(hmac.compare_digest(hashlib.sha256(baseline_bytes).hexdigest(),approved_digest),'BASELINE_UNAPPROVED')
        baseline=strict_object(baseline_bytes);record(baseline,('schema','source','tools'))
        need(type(baseline['schema']) is int and baseline['schema']==1)
        need(hexstring(expected_sha,40) and hexstring(expected_tree,40) and hexstring(session,64))
        record(baseline['source'],SOURCE)
        need(baseline['source']['sha']==expected_sha and baseline['source']['tree']==expected_tree,'SOURCE_UNBOUND')
        need(hexstring(baseline['source']['collector_manifest_sha256'],64))
        need(type(baseline['source']['scripts_signed']) is bool)
        record(evidence,('schema','mode','session','recorded_at','source_before','source_after','tools',
                         'python_version','python_bits','powershell_version','checks','namespace','policy'))
        need(type(evidence['schema']) is int and evidence['schema']==1)
        mode=evidence['mode'];need(type(mode) is str and mode in ('HTTP_SYS_FORMAT','R0_R5'))
        need(evidence['session']==session,'STALE_RECORDS')
        stamp=evidence['recorded_at']
        need(type(stamp) in (int,float) and math.isfinite(stamp) and type(now) in (int,float) and math.isfinite(now))
        need(0<=now and -10<=now-stamp<=300,'STALE_RECORDS')
        for phase in ('source_before','source_after'):
            value=evidence[phase];record(value,SOURCE|{'clean'})
            need(type(value['scripts_signed']) is bool)
            need(value['clean'] is True and {k:value[k] for k in SOURCE}==baseline['source'],'SOURCE_UNBOUND')
        version=evidence['python_version']
        need(type(version) is list and len(version)==3 and all(type(v) is int and 0<=v<1000 for v in version))
        need(version[:2]==[3,12] and type(evidence['python_bits']) is int and evidence['python_bits']==64,'TOOLS_UNAPPROVED')
        need(type(evidence['powershell_version']) is list and all(type(v) is int for v in evidence['powershell_version']) and evidence['powershell_version']==[5,1],'TOOLS_UNAPPROVED')
        roles=COMMON | (NATIVE if mode=='R0_R5' else set())
        need(type(baseline['tools']) is dict and roles<=set(baseline['tools'])<=COMMON|NATIVE,'TOOLS_UNAPPROVED')
        for approved in baseline['tools'].values():
            record(approved,TOOL)
            need(hexstring(approved['sha256'],64) and hexstring(approved['authority_sha256'],64))
            need(approved['basis'] in ('AUTHENTICODE','CATALOG','SIGNED_DISTRIBUTION'))
        record(evidence['tools'],roles)
        for role in roles:
            approved=baseline['tools'][role];measured=evidence['tools'][role]
            record(approved,TOOL);record(measured,TOOL|{'verification'})
            need(measured['verification']=='VALID' and {k:measured[k] for k in TOOL}==approved,'TOOLS_UNAPPROVED')
        policy=evidence['policy'];record(policy,POLICY)
        scopes=('machine_policy','user_policy','process','current_user','local_machine')
        need(all(type(policy[k]) is str and policy[k] in POLICIES for k in (*scopes,'effective')))
        need(all(type(policy[k]) is bool for k in POLICY-set(scopes)-{'effective','language_mode'}))
        effective=next((policy[k] for k in scopes if policy[k]!='Undefined'),'Restricted')
        need(policy['effective']==effective and effective in ('RemoteSigned','AllSigned'),'POLICY_UNREVIEWED')
        need(all(policy[k]!='Bypass' for k in scopes) and policy['process']=='Undefined' and not policy['process_override_present'],'POLICY_UNREVIEWED')
        need(policy['language_mode']=='FullLanguage' and policy['script_policy_reviewed'] and policy['motw_reviewed'],'POLICY_UNREVIEWED')
        need(policy['scripts_signed'] is baseline['source']['scripts_signed'],'SOURCE_UNBOUND')
        need(effective!='AllSigned' or policy['scripts_signed'],'POLICY_UNREVIEWED')
        if mode=='R0_R5':need(policy['add_type_chain_reviewed'] and policy['temp_namespace_reviewed'],'POLICY_UNREVIEWED')
        for key,fields,code in (('checks',CHECKS,'PREFLIGHT_REFUSED'),('namespace',NAMESPACE,'NAMESPACE_UNREVIEWED')):
            record(evidence[key],fields)
            need(all(evidence[key][k] is True for k in fields),code)
        return report('RECORDS_CONSISTENT',dict(sha=expected_sha,tree=expected_tree))
    except BaseException as exc:
        return report(exc.code if isinstance(exc,Refusal) else 'MALFORMED_EVIDENCE')


def namespace(path):
    need(path.is_absolute() and path.anchor and not str(path).startswith(('\\\\','//')),'NAMESPACE_UNREVIEWED')
    need('..' not in path.parts and all(':' not in part for part in path.parts if part!=path.anchor),'NAMESPACE_UNREVIEWED')
    chain=[]
    for parent in reversed(path.parents):
        value=parent.lstat()
        need(not stat.S_ISLNK(value.st_mode) and not getattr(value,'st_file_attributes',0)&0x400,'NAMESPACE_UNREVIEWED')
        need(stat.S_ISDIR(value.st_mode),'NAMESPACE_UNREVIEWED')
        chain.append((str(parent),value.st_dev,value.st_ino))
    return chain


def publish_new(filename,payload):
    """Exclusive receipt only. Requires an isolated, approved namespace/writer.

    No unlink/rename/reopen or ACL change. A fault may leave a partial reservation;
    this is not crash durability or protection against a malicious concurrent admin.
    """
    path=Path(filename);before=namespace(path)
    need(type(payload) is bytes and len(payload)<=65536)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        info=os.fstat(fd)
        need(info.st_nlink==1 and stat.S_ISREG(info.st_mode),'NAMESPACE_UNREVIEWED')
        need(namespace(path)==before,'NAMESPACE_UNREVIEWED')
        leaf=path.lstat()
        need((leaf.st_dev,leaf.st_ino)==(info.st_dev,info.st_ino) and not getattr(leaf,'st_file_attributes',0)&0x400,'NAMESPACE_UNREVIEWED')
        need(os.write(fd,payload)==len(payload),'OUTPUT_UNAVAILABLE')
        need(os.fstat(fd).st_nlink==1 and namespace(path)==before,'NAMESPACE_UNREVIEWED')
    finally:os.close(fd)


def main(argv=None,*,now=None):
    value=report('MALFORMED_EVIDENCE')
    try:
        class Parser(argparse.ArgumentParser):
            def error(self,message):raise Refusal()
        parser=Parser(add_help=False)
        for key in ('records','baseline','approved-baseline-sha256','expected-sha','expected-tree','session','output'):
            parser.add_argument('--'+key,required=True)
        args=parser.parse_args(argv)
        def read(path):
            with open(path,'rb') as stream:
                raw=stream.read(LIMIT+1)
            need(len(raw)<=LIMIT)
            return raw
        value=review(strict_object(read(args.records)),read(args.baseline),args.approved_baseline_sha256,
                     expected_sha=args.expected_sha,expected_tree=args.expected_tree,session=args.session,
                     now=time.time() if now is None else now)
        try:publish_new(args.output,(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode('utf-8'))
        except BaseException:value=report('OUTPUT_UNAVAILABLE')
    except BaseException:value=report('MALFORMED_EVIDENCE')
    try:print(json.dumps(value,sort_keys=True,allow_nan=False))
    except (OSError,ValueError):pass
    return 1


if __name__=='__main__':raise SystemExit(main())
