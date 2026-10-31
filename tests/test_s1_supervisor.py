"""Development-only PowerShell supervisor fixtures, never a host precheck."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[1]
PS = shutil.which('powershell.exe') if os.name == 'nt' else shutil.which('pwsh')


def receipt():
    return dict(schema=1, stage='S1_PRECHECK', contract_version=1,
                source_sha='b00c66776b27e929016f7541329c29c9349dddfe',
                source_tree='0418dc7bea4bb2f40f6712b0f3c0c1a6c63b8288', source_bound=True,
                source_continuity='PASS', runtime_continuity='PASS', output_readiness='PASS',
                outcome='PASS_PRECHECK_ONLY', reason='PRECHECK_COMPLETE', elapsed_ms=1,
                exit_code=0, attempts=1, s1_complete=False, authorization='NONE',
                g0_status='FAIL_CLOSED', next_stage='BLOCKED', stop_required=True)


@pytest.mark.parametrize('variant', ['valid', 'malformed', 'raw_metadata', 'stderr',
                                   'duplicate', 'escaped_duplicate', 'forged_pass', 'timeout',
                                   'memory', 'wrong_pin', 'wrong_python', 'fast_exit', 'partial',
                                   'late_stderr', 'slow_partial', 'array_sha', 'no_ack',
                                   'wrong_nonce', 'extra_ack', 'release_timeout', 'partial_ack'])
def test_supervisor_bounded_projection(tmp_path, variant):
    # This file is selected only on Windows. Linux runs actual portable worker
    # tests; it does not relabel Windows runtime cases as static PASS or skips.
    assert os.name == 'nt'
    assert PS is not None
    r = receipt()
    if variant == 'array_sha': r['source_sha'] = [r['source_sha'], 'PRIVATE_TYPE_LEAK']
    if variant == 'forged_pass': r['source_bound'] = False
    raw = json.dumps(r)
    if variant == 'malformed': raw = '{'
    if variant == 'raw_metadata': raw = 'PRIVATE_PATH_HOSTNAME_SID_EXCEPTION'
    if variant == 'duplicate': raw = raw.replace('{', '{"schema":1,', 1)
    if variant == 'escaped_duplicate': raw = raw.replace('"schema": 1', '"schema":0,"\\u0073chema":1', 1)
    control_marker = tmp_path / 'fixture-control-prefix.txt'
    code = 'import time,sys,os\ncontrol=sys.stdin.buffer.readline(32)\n'
    code += ('control_class=("UTF8_BOM" if control.startswith(bytes.fromhex("efbbbf")) else '
             '"UTF16_BOM" if control.startswith((bytes.fromhex("fffe"),bytes.fromhex("feff"))) else '
             '"ASCII_MATCH" if control.strip()==str(os.getpid()).encode("ascii") else '
             '"ASCII_MISMATCH" if control.isascii() else "NONASCII")\n')
    code += 'with open(' + repr(str(control_marker)) + ',"w",encoding="ascii") as marker:marker.write(control_class)\n'
    code += 'assert int(control)==os.getpid()\ntime.sleep(.1)\n'

    if variant == 'stderr': code += 'sys.stderr.write("PRIVATE_EXCEPTION")\n'
    if variant == 'timeout': code += 'time.sleep(60)\n'
    if variant == 'memory': code += 'x=bytearray(300*1024*1024)\ntime.sleep(5)\n'
    if variant == 'partial':
        half = len(raw) // 2
        code += 'sys.stdout.write(' + repr(raw[:half]) + ');sys.stdout.flush();time.sleep(.1)\n'
        raw = raw[half:]
    if variant == 'slow_partial':
        code += 'for c in ' + repr(raw[:30]) + ':\n sys.stdout.write(c);sys.stdout.flush();time.sleep(.05)\n'
        raw = raw[30:]
    code += 'print(' + repr(raw) + ');sys.stdout.flush()\n'
    if variant != 'fast_exit':
        code += 'release=sys.stdin.buffer.readline(128).strip().decode("ascii")\n'
        if variant == 'release_timeout': code += 'time.sleep(5)\n'
        if variant not in ('no_ack', 'release_timeout'):
            if variant == 'wrong_nonce': code += 'release="0"*32\n'
            if variant == 'partial_ack':
                code += 'sys.stdout.write("S1_");sys.stdout.flush();time.sleep(.05)\n'
                code += 'print("ACK:"+release);sys.stdout.flush()\n'
            else: code += 'print("S1_ACK:"+release);sys.stdout.flush()\n'
            if variant == 'extra_ack': code += 'print("PRIVATE_TRAILING_ACK");sys.stdout.flush()\n'
    if variant == 'late_stderr': code += 'sys.stderr.write("PRIVATE_LATE_EXCEPTION")\n'
    worker = tmp_path / 's1_precheck.py'
    worker.write_bytes(code.encode())
    launcher = (ROOT / 'scripts/Invoke-S1Precheck.ps1').read_text()
    import re
    pin = '0' * 64 if variant == 'wrong_pin' else hashlib.sha256(worker.read_bytes()).hexdigest()
    launcher = re.sub(r"\$workerPin='[^']+'", "$workerPin='" + pin + "'", launcher)
    if variant in ('timeout', 'slow_partial'):
        launcher = launcher.replace('$watch.Elapsed.TotalSeconds -ge 30', '$watch.Elapsed.TotalSeconds -ge 1')
    # Diagnose only the copied fixture supervisor, never alter production guards.
    # Line numbers/known booleans identify which exact refusal boundary failed;
    # paths, environment values and exception bodies stay private.
    launcher = launcher.replace(
        "function Need($Condition){if(-not $Condition){throw 'UNAVAILABLE'}}",
        "function Need($Condition){if(-not $Condition){$script:fixtureNeedLine=[int]$MyInvocation.ScriptLineNumber;throw 'UNAVAILABLE'}}")
    launcher = launcher.replace(
        "} catch {\n if($null -ne $child)",
        "} catch {\n [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'fixture-stage.json'),([ordered]@{need_line=[int]$script:fixtureNeedLine;catch_line=[int]$_.InvocationInfo.ScriptLineNumber;child_started=[bool]($null -ne $child);role=[string]$entry.role;environment_key=[string]$key}|ConvertTo-Json -Compress))\n if($null -ne $child)")
    wrapper = tmp_path / 'Invoke-S1Precheck.ps1'
    wrapper.write_text(launcher)
    packet = tmp_path / 'private.json'
    roles = ['python_exe','python312_dll','hashlib_pyd','ctypes_pyd','libcrypto','libffi',
             'crt','bz2_pyd','lzma_pyd','git_exe','git_core','libiconv','libintl','pcre2',
             'zlib','powershell_exe']
    files = []
    for role in roles:
        path = PS if role == 'powershell_exe' else sys._base_executable
        files.append(dict(role=role, path=path, sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()))
    if variant == 'wrong_python': files[0]['sha256'] = '0' * 64
    env_keys = ['PATH','GIT_CONFIG_SYSTEM','GIT_CONFIG_GLOBAL','GIT_CONFIG_NOSYSTEM',
                'PYTHONHOME','PYTHONPATH','PYTHONSTARTUP','PYTHONUSERBASE','__PYVENV_LAUNCHER__']
    packet.write_text(json.dumps(dict(schema=1, reference_kind='EXTERNALLY_REVIEWED_CONTINUITY',
                                     files=files, absent=[str(tmp_path / 'absent')],
                                     environment={k: os.environ.get(k) for k in env_keys})))
    p = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-File', str(wrapper),
                        '-Repo', str(tmp_path), '-Python', sys._base_executable, '-Packet', str(packet),
                        '-PacketSha256', hashlib.sha256(packet.read_bytes()).hexdigest(), '-OperatorApproved'],
                       capture_output=True, timeout=15)
    assert p.stderr == b''
    assert b'PRIVATE_' not in p.stdout and str(tmp_path).encode() not in p.stdout
    out = json.loads(p.stdout)
    marker = tmp_path / 'fixture-stage.json'
    stage = {}
    if marker.exists() and marker.stat().st_size <= 512:
        candidate = json.loads(marker.read_bytes())
        for key in ('need_line', 'catch_line'):
            if type(candidate.get(key)) is int and 0 <= candidate[key] <= 500:
                stage[key] = candidate[key]
        if type(candidate.get('child_started')) is bool:
            stage['child_started'] = candidate['child_started']
        if candidate.get('role') in roles:
            stage['role'] = candidate['role']
        if candidate.get('environment_key') in env_keys:
            stage['environment_key'] = candidate['environment_key']
    # No raw paths, executable identities, environment values or traceback text.
    control_class = 'NOT_OBSERVED'
    if control_marker.exists() and control_marker.stat().st_size <= 32:
        observed = control_marker.read_text(encoding='ascii')
        if observed in ('UTF8_BOM', 'UTF16_BOM', 'ASCII_MATCH', 'ASCII_MISMATCH', 'NONASCII'):
            control_class = observed
    diagnosis = json.dumps(dict(variant=variant, control_prefix=control_class, exit=p.returncode,
                                reason=out.get('reason'), attempts=out.get('attempts'),
                                python_path_canonical=str(Path(sys._base_executable).resolve()) == sys._base_executable,
                                shell_path_canonical=str(Path(PS).resolve()) == PS,
                                temporary_path_canonical=tmp_path.resolve() == tmp_path,
                                stage=stage), sort_keys=True)
    assert out['authorization'] == 'NONE' and out['g0_status'] == 'FAIL_CLOSED'
    if variant in ('valid', 'partial', 'partial_ack'):
        assert p.returncode == 0 and out['outcome'] == 'PASS_PRECHECK_ONLY', diagnosis
    else:
        assert p.returncode in (1, 2) and out['outcome'] != 'PASS_PRECHECK_ONLY'
    if variant in ('timeout', 'memory'):
        assert out['reason'] == 'BUDGET_EXCEEDED', diagnosis
    if variant == 'wrong_python': assert out['attempts'] == 0
