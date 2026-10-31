"""Fixed source-collected Linux/Windows coverage contract, never host admission.

Public receipts contain opaque test identities and source/run pins only. They are
cooperative CI evidence, not cryptographic host attestation. Windows evidence is
mandatory: a portable lane alone cannot qualify the complete test catalog.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import project_public_ci_evidence as public
from scripts.check_final_integration_junit import check

NATIVE_VARIANTS=('valid','malformed','raw_metadata','stderr','duplicate','escaped_duplicate',
    'forged_pass','timeout','memory','wrong_pin','wrong_python','fast_exit','partial',
    'late_stderr','slow_partial','array_sha','no_ack','wrong_nonce','extra_ack',
    'release_timeout','partial_ack')
ERROR='PLATFORM_COVERAGE_REJECTED'


def need(ok):
    if not ok:raise ValueError(ERROR)


def identity(classname,name):
    raw=(json.dumps([classname,name],sort_keys=True,separators=(',',':'))+'\n').encode()
    return 'case_'+hashlib.sha256(raw).hexdigest()


def native_identities():
    return sorted(identity('tests.test_s1_supervisor','test_supervisor_bounded_projection['+v+']') for v in NATIVE_VARIANTS)


def classify_native(rows):
    native=[]
    for file,function,variant in rows:
        if file=='tests/test_s1_supervisor.py':
            need(function=='test_supervisor_bounded_projection' and variant in NATIVE_VARIANTS)
            native.append(variant)
    need(len(native)==21 and set(native)==set(NATIVE_VARIANTS))
    return native_identities()


def ids(values):
    need(type(values) is list)
    need(all(type(v) is str and re.fullmatch('case_[0-9a-f]{64}',v) for v in values))
    need(values==sorted(set(values)))
    return set(values)


def selected_for(identities,native,platform,suite):
    need(platform in ('linux','windows') and suite in ('main','commissioning'))
    return identities-native if platform=='linux' else identities if suite=='main' else native


def validate_ledger(l):
    need(type(l) is dict and set(l)=={'schema','sha','tree','source_files_sha256','source_bound',
        'platform','suite','identities','native_identities','selected','deferred'})
    need(l['schema']=='meta.platform.ledger.v1')
    for key in ('sha','tree'):need(type(l[key]) is str and re.fullmatch('[0-9a-f]{40}',l[key]))
    need(type(l['source_files_sha256']) is str and re.fullmatch('[0-9a-f]{64}',l['source_files_sha256']))
    need(type(l['source_bound']) is bool)
    full,native,selected,deferred=(ids(l[k]) for k in ('identities','native_identities','selected','deferred'))
    need(l['native_identities']==native_identities() and native<full)
    need(selected==selected_for(full,native,l['platform'],l['suite']))
    need(deferred==full-selected and not selected&deferred)
    return l


def validate_receipt(r):
    need(type(r) is dict and set(r)=={'schema','ledger','run_id','attempt','passed','skipped','source_authenticity','physical'})
    need(r['schema']=='meta.platform.receipt.v1' and r['source_authenticity']=='NOT_EVALUATED' and r['physical']=='NOT_RUN')
    l=validate_ledger(r['ledger']);need(l['source_bound'] is True)
    for key in ('run_id','attempt'):need(type(r[key]) is str and re.fullmatch('[1-9][0-9]{0,19}',r[key]))
    passed,skipped=ids(r['passed']),ids(r['skipped'])
    need(not passed&skipped and passed|skipped==set(l['selected']))
    need(not set(l['native_identities'])&skipped)
    # Keep only the pre-existing narrowly allowed skips; never admit a native skip.
    allowed={identity('tests.test_installer','test_failed_pip_install_never_reports_success_or_creates_launcher')} if l['platform']=='linux' else set()
    allowed|={identity('tests.test_public_junit','test_symlink_is_rejected'),
              identity('tests.test_pr23_transaction','test_existing_private_survives_static_alias_spellings[symlink]')}
    need(skipped<=allowed)
    return r


def make_receipt(raw,manifest,ledger,*,run_id,attempt):
    l=validate_ledger(ledger)
    need(l['source_bound'] is True)
    check(raw,manifest,l['sha'],l['tree'])
    need(manifest['identities']==l['selected'])
    projected=public.project(raw,set())
    cases=list(public.parse(projected).iter('testcase'))
    r=dict(schema='meta.platform.receipt.v1',ledger=l,run_id=run_id,attempt=attempt,
        passed=sorted(c.get('name') for c in cases if c.find('skipped') is None),
        skipped=sorted(c.get('name') for c in cases if c.find('skipped') is not None),
        source_authenticity='NOT_EVALUATED',physical='NOT_RUN')
    return validate_receipt(r)


def aggregate(receipts,*,sha,tree,run_id,attempt,suite):
    need(type(receipts) is list and len(receipts)==2)
    lanes={}
    for r in receipts:
        validate_receipt(r);l=r['ledger'];platform=l['platform']
        need(platform not in lanes);lanes[platform]=r
        need((l['sha'],l['tree'],l['suite'],r['run_id'],r['attempt'])==(sha,tree,suite,run_id,attempt))
    need(set(lanes)=={'linux','windows'})
    a,b=lanes['linux']['ledger'],lanes['windows']['ledger']
    need(a['identities']==b['identities'] and a['native_identities']==b['native_identities'])
    need(a['source_files_sha256']==b['source_files_sha256'])
    need(set(a['selected'])|set(b['selected'])==set(a['identities']))
    native=set(a['native_identities'])
    need(not native&set(a['selected']) and native<=set(lanes['windows']['passed']))
    if suite=='commissioning':need(not set(a['selected'])&set(b['selected']))
    else:need(set(a['selected'])&set(b['selected'])==set(a['identities'])-native)
    return dict(schema='meta.platform.aggregate.v1',sha=sha,tree=tree,run_id=run_id,attempt=attempt,
        suite=suite,status='PASS_SOURCE_TESTS_ONLY',identities=len(a['identities']),
        windows_native_passed=len(native),source_authenticity='NOT_EVALUATED',physical='NOT_RUN')


def write_receipt(directory,r):
    validate_receipt(r)
    # New exclusive staging namespace; no mixed raw logs or overwritten evidence.
    directory=public.safe_path(directory);directory.mkdir(parents=True,exist_ok=False)
    data=public.json_bytes(r)
    try:
        (directory/'receipt.json').write_bytes(data)
        validate_directory(directory)
    except Exception:
        import shutil
        shutil.rmtree(directory)
        raise


def validate_directory(directory):
    directory=public.safe_path(directory)
    need(directory.is_dir() and {p.name for p in directory.iterdir()}=={'receipt.json'})
    r=public.decode(public.read(directory/'receipt.json'))
    validate_receipt(r)
    return r


def git(arg):
    return subprocess.check_output(['git','--no-replace-objects','rev-parse',arg],text=True,stderr=subprocess.DEVNULL).strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('receipt');p.add_argument('--xml',required=True);p.add_argument('--manifest',required=True);p.add_argument('--ledger',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('validate');p.add_argument('directory')
    p=sub.add_parser('aggregate');p.add_argument('--linux',required=True);p.add_argument('--windows',required=True);p.add_argument('--suite',choices=('main','commissioning'),required=True)
    args=parser.parse_args()
    try:
        if args.command=='validate':validate_directory(args.directory)
        else:
            need(os.environ.get('GITHUB_ACTIONS')=='true')
            sha,tree=git('HEAD'),git('HEAD^{tree}')
            # Check actual checkout binding again immediately before receipt/review.
            need(not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True))
            run_id,attempt=os.environ['GITHUB_RUN_ID'],os.environ['GITHUB_RUN_ATTEMPT']
            if args.command=='receipt':
                l=public.decode(public.read(args.ledger))
                need(l['sha']==sha and l['tree']==tree)
                actual='windows' if sys.platform=='win32' else sys.platform
                need(l['platform']==actual)
                r=make_receipt(public.read(args.xml),public.decode(public.read(args.manifest)),l,run_id=run_id,attempt=attempt)
                write_receipt(args.output,r)
            else:
                r=aggregate([validate_directory(args.linux),validate_directory(args.windows)],sha=sha,tree=tree,run_id=run_id,attempt=attempt,suite=args.suite)
                print(json.dumps(r,sort_keys=True))
        print('PASS: platform evidence validated; physical=NOT_RUN; authorization=NONE')
        return 0
    except Exception:
        print('BLOCKED: '+ERROR,file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
