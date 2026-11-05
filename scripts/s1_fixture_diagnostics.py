"""Test-copy-only progress, never a physical host or runtime admission receipt.

No production supervisor line or timeout is replaced. A missing marker means
script entry was not observed, not proof that PowerShell never started. Progress
writes are best effort and cannot change the original supervisor's verdict.
"""
import json
from pathlib import Path
import stat
import subprocess
import re

PHASES=frozenset(('SCRIPT_ENTERED','PACKET_DECODE','RUNTIME_FILE','ENVIRONMENT',
    'WORKER_START','WORKER_CONTROL','WORKER_OUTPUT','RELEASE_HANDSHAKE','PUBLICATION'))
ROLES=frozenset(('NONE','python_exe','python312_dll','hashlib_pyd','ctypes_pyd','libcrypto','libffi',
    'crt','crt_1','bz2_pyd','lzma_pyd','git_exe','git_core','libiconv','libintl','pcre2','zlib','powershell_exe'))

HEADER="""# TEST_ONLY_FIXTURE_PROGRESS_BEGIN
function Fixture-Phase([string]$Phase,[string]$Role='NONE'){
 try {
  if($Phase -cnotin @('SCRIPT_ENTERED','PACKET_DECODE','RUNTIME_FILE','ENVIRONMENT','WORKER_START','WORKER_CONTROL','WORKER_OUTPUT','RELEASE_HANDSHAKE','PUBLICATION')){return}
  if($Role -cnotin @('NONE','python_exe','python312_dll','hashlib_pyd','ctypes_pyd','libcrypto','libffi','crt','crt_1','bz2_pyd','lzma_pyd','git_exe','git_core','libiconv','libintl','pcre2','zlib','powershell_exe')){$Role='NONE'}
  $stamp=$watch.ElapsedMilliseconds.ToString([Globalization.CultureInfo]::InvariantCulture)
  $progress='{"phase":"'+$Phase+'","role":"'+$Role+'","elapsed_ms":'+$stamp+'}'
  [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'fixture-progress.json'),$progress,(New-Object Text.UTF8Encoding($false)))
 }catch{}
}
Fixture-Phase 'SCRIPT_ENTERED'
# TEST_ONLY_FIXTURE_PROGRESS_END
"""


def instrument_fixture(source):
    if type(source)is not str or len(source)>65536:raise ValueError('S1_FIXTURE_INSTRUMENTATION_REJECTED')
    placements=(
        ('$child=$null\n',HEADER),
        (' $privatePacket=$strictUtf8.GetString($packetBytes)|ConvertFrom-Json\n'," Fixture-Phase 'PACKET_DECODE'\n"),
        (' foreach($entry in $privatePacket.files){\n',None),
        (" $environmentKeys=@('PATH'", " Fixture-Phase 'ENVIRONMENT'\n"),
        (' $priorInputEncoding=[Console]::InputEncoding\n'," Fixture-Phase 'WORKER_START'\n"),
        (' $control=$child.StandardInput.BaseStream\n'," Fixture-Phase 'WORKER_CONTROL'\n"),
        (' $stdout=New-Object byte[] 4097;'," Fixture-Phase 'WORKER_OUTPUT'\n"),
        (' $random=New-Object byte[] 16\n'," Fixture-Phase 'RELEASE_HANDSHAKE'\n"),
        (' $r.elapsed_ms=[long]$watch.ElapsedMilliseconds\n'," Fixture-Phase 'PUBLICATION'\n"),
    )
    for needle,addition in placements:
        if source.count(needle)!=1:raise ValueError('S1_FIXTURE_INSTRUMENTATION_REJECTED')
        if addition is None:source=source.replace(needle,needle+"  Fixture-Phase 'RUNTIME_FILE' ([string]$entry.role)\n",1)
        else:source=source.replace(needle,addition+needle,1)
    return source


def timeout_note(root):
    phase='START_NOT_OBSERVED';role='NONE';elapsed=0
    path=Path(root)/'fixture-progress.json'
    try:
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode)or info.st_nlink!=1 or info.st_size>512:raise ValueError()
        with path.open('rb')as stream:raw=stream.read(513)
        if len(raw)>512:raise ValueError()
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError()
                result[key]=value
            return result
        data=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        if(type(data)is not dict or set(data)!={'phase','role','elapsed_ms'}or data['phase']not in PHASES
           or data['role']not in ROLES or type(data['elapsed_ms'])is not int or not 0<=data['elapsed_ms']<=30000):raise ValueError()
        phase=data['phase'];role=data['role'];elapsed=data['elapsed_ms']
    except FileNotFoundError:pass
    except (OSError,ValueError,UnicodeError,TypeError):phase='UNAVAILABLE'
    return f'S1_FIXTURE_TIMEOUT phase={phase} role={role} elapsed_ms={elapsed} reason=OUTER_15S_DEADLINE'


def annotate_timeout(root,error):
    if not isinstance(error,subprocess.TimeoutExpired):raise TypeError('S1_FIXTURE_TIMEOUT_TYPE_REJECTED')
    note=timeout_note(root)
    print(note,flush=True)
    error.add_note(note)


def public_timeout_lines(raw,expected_ids):
    """Project only closed notes for source-collected, failed S1 fixture cases.

    The workflow must first bind its collected inventory to exact Actions/Git
    provenance. This does not change the private/public JUnit acceptance rules.
    """
    from scripts import project_public_ci_evidence as public
    from scripts.platform_coverage import NATIVE_VARIANTS
    public.need(type(raw)is bytes and len(raw)<=public.LIMIT)
    public.need(type(expected_ids)is list and 1<=len(expected_ids)<=10000)
    public.need(all(type(value)is str and re.fullmatch('case_[0-9a-f]{64}',value)for value in expected_ids))
    public.need(expected_ids==sorted(set(expected_ids)))
    projected=public.project(raw,set());public.validate_junit(projected,set())
    projected_cases=list(public.parse(projected).iter('testcase'))
    public.need(sorted(case.get('name')for case in projected_cases)==expected_ids)
    original_cases=public.cases_from(public.parse(raw));public.need(len(original_cases)==len(projected_cases))
    pattern=re.compile(r'S1_FIXTURE_TIMEOUT phase=([A-Z_]+) role=([a-z0-9_]+|NONE) elapsed_ms=([0-9]{1,5}) reason=OUTER_15S_DEADLINE')
    names={'test_supervisor_bounded_projection['+variant+']'for variant in NATIVE_VARIANTS}
    output=[]
    for case,opaque in zip(original_cases,projected_cases):
        if case.get('classname')!='tests.test_s1_supervisor'or case.get('name')not in names:continue
        failure=case.find('failure')
        if failure is None:failure=case.find('error')
        if failure is None:continue
        notes=set()
        for value in (failure.get('message',''),failure.text or'',*(child.text or'' for child in case if child.tag in ('system-out','system-err'))):
            for line in value.splitlines():
                line=line.strip()
                if not line.startswith('S1_FIXTURE_TIMEOUT '):continue
                match=pattern.fullmatch(line)
                public.need(match is not None)
                phase,role,elapsed=match.groups()
                public.need(phase in PHASES|{'START_NOT_OBSERVED','UNAVAILABLE'}and role in ROLES and str(int(elapsed))==elapsed and 0<=int(elapsed)<=30000)
                notes.add((phase,role,elapsed))
        public.need(len(notes)<=1)
        if notes:
            phase,role,elapsed=next(iter(notes))
            output.append(f"S1_FIXTURE_TIMEOUT case={opaque.get('name')} phase={phase} role={role} elapsed_ms={elapsed} reason=OUTER_15S_DEADLINE")
    return output
