"""One-shot HTTP.sys FORMAT diagnostics, never process ownership/admission.

Raw child output is private/in-memory. Only fixed fields and coarsened structural
counts may be emitted. Unknown locale labels are neither emitted nor guessed.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

import evidence_schema as schema
import host_identity as host
from native_scm_diagnostic import source_binding

LIMIT = 1024 * 1024


def bucket(n):
    return ('ZERO' if n == 0 else 'ONE' if n == 1 else 'TWO_TO_FOUR' if n <= 4
            else 'FIVE_TO_SIXTEEN' if n <= 16 else 'SEVENTEEN_TO_SIXTY_FOUR' if n <= 64
            else 'SIXTY_FIVE_TO_256' if n <= 256 else 'OVER_256')


def project(text):
    if type(text) is not str or len(text) > LIMIT:
        raise ValueError('FORMAT_EVIDENCE_INVALID')
    lines = text.splitlines()
    def count(pattern):
        return bucket(sum(bool(re.match(pattern, line)) for line in lines))
    return dict(ownership='NOT_EVALUATED', format_support='NOT_ATTESTED',
        line_count=bucket(len(lines)),
        colon_line_count=bucket(sum(bool(re.match(r'^[ \t]*[^:\r\n]+:', line)) for line in lines)),
        characters=dict(non_ascii=any(ord(c)>127 for c in text),
                        cyrillic=any('\u0400'<=c<='\u04ff' for c in text),
                        replacement='\ufffd' in text,
                        control=any(ord(c)<32 and c not in '\r\n\t' for c in text)),
        markers=dict(queue_column_zero=count(r'^Request queue name:'),
                     queue_indented=count(r'^[ \t]+Request queue name:'),
                     attached_count=count(r'^[ \t]*Number of active processes attached:'),
                     summary_process_ids=count(r'^[ \t]*Process IDs:'),
                     verbose_process=count(r'^[ \t]+ID:[ \t]*[0-9]+, image:'),
                     registered_urls=count(r'^[ \t]*Registered URLs:'),
                     url_lines=count(r'(?i)^[ \t]*https?://')),
        target_token='PRESENT' if re.search(r'(?<![0-9])17845(?![0-9])',text) else 'ABSENT')


def capture_snapshot():
    directory=host.system_directory()
    environment={k:v for k,v in os.environ.items() if k.casefold()!='psexecutionpolicypreference'}
    environment['PSModulePath']=str(directory/'WindowsPowerShell/v1.0/Modules')
    result=subprocess.run([str(directory/'WindowsPowerShell/v1.0/powershell.exe'),
        '-NoProfile','-NonInteractive','-File',str(Path(__file__).with_name('http-sys-format.ps1'))],
        capture_output=True,timeout=20,env=environment)
    if type(result.returncode) is not int or result.returncode!=0 or len(result.stdout)>2*LIMIT:
        raise ValueError('FORMAT_CHILD_UNAVAILABLE')
    value=schema.strict_loads(result.stdout.decode('utf-8-sig'))
    if (type(value) is not dict or set(value)!={'schema','exit_code','text'} or
            type(value['schema']) is not int or value['schema']!=1 or
            type(value['exit_code']) is not int or value['exit_code']!=0 or
            type(value['text']) is not str or len(value['text'])>LIMIT):
        raise ValueError('FORMAT_CHILD_UNAVAILABLE')
    return value['text']


def main(argv=None):
    class SafeParser(argparse.ArgumentParser):
        def error(self,message):raise ValueError('FORMAT_ARGUMENTS_INVALID')
    binding=None;diagnostics=None;output=None;code='FORMAT_DIAGNOSTIC_ONLY'
    try:
        parser=SafeParser(add_help=False)
        for name in ('expected-sha','expected-tree','output'):parser.add_argument('--'+name,required=True)
        args=parser.parse_args(argv)
        if host.platform.system()!='Windows' or not host.is_elevated():
            raise ValueError('FORMAT_TOKEN_UNAVAILABLE')
        binding=source_binding(args.expected_sha,args.expected_tree)
        output=host.NewOutput(args.output)
        try:diagnostics=project(capture_snapshot())
        finally:
            if source_binding(args.expected_sha,args.expected_tree)!=binding:
                raise ValueError('FORMAT_SOURCE_CHANGED')
    except BaseException:
        diagnostics=None;binding=None;code='FORMAT_UNAVAILABLE'
    def report():
        return dict(schema=1,status='FAIL_CLOSED',authorization='NONE',
            diagnostic_status='HTTP_SYS_FORMAT_ONLY',lifetime_binding='NOT_EVALUATED_DIAGNOSTIC_ONLY',
            projection_status='AVAILABLE' if diagnostics is not None else 'UNAVAILABLE',
            reason_codes=[code],source={k:binding[k] for k in ('sha','tree')} if binding else None,
            diagnostics=diagnostics)
    if output is not None:
        try:output.write(json.dumps(report(),allow_nan=False,sort_keys=True).encode('utf-8'))
        except BaseException:diagnostics=None;code='FORMAT_OUTPUT_UNAVAILABLE'
        finally:
            try:output.close()
            except BaseException:diagnostics=None;code='FORMAT_OUTPUT_UNAVAILABLE'
    try:print(json.dumps(report(),allow_nan=False,sort_keys=True))
    except (OSError,ValueError):pass
    return 1


if __name__=='__main__':
    raise SystemExit(main())
