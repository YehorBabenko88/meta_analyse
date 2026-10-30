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
                                   'memory', 'wrong_pin', 'wrong_python', 'fast_exit', 'partial', 'late_stderr'])
def test_supervisor_bounded_projection(tmp_path, variant):
    # This file is selected only on Windows. Linux runs actual portable worker
    # tests; it does not relabel Windows runtime cases as static PASS or skips.
    assert os.name == 'nt'
    assert PS is not None
    r = receipt()
    if variant == 'forged_pass': r['source_bound'] = False
    raw = json.dumps(r)
    if variant == 'malformed': raw = '{'
    if variant == 'raw_metadata': raw = 'PRIVATE_PATH_HOSTNAME_SID_EXCEPTION'
    if variant == 'duplicate': raw = raw.replace('{', '{"schema":1,', 1)
    if variant == 'escaped_duplicate': raw = raw.replace('"schema": 1', '"schema":0,"\\u0073chema":1', 1)
    code = 'import time,sys,os\nassert int(sys.stdin.buffer.readline(32))==os.getpid()\ntime.sleep(.1)\n'
    if variant == 'stderr': code += 'sys.stderr.write("PRIVATE_EXCEPTION")\n'
    if variant == 'timeout': code += 'time.sleep(60)\n'
    if variant == 'memory': code += 'x=bytearray(300*1024*1024)\ntime.sleep(5)\n'
    if variant == 'partial':
        half = len(raw) // 2
        code += 'sys.stdout.write(' + repr(raw[:half]) + ');sys.stdout.flush();time.sleep(.1)\n'
        raw = raw[half:]
    code += 'print(' + repr(raw) + ');sys.stdout.flush()\n'
    if variant != 'fast_exit': code += 'sys.stdin.buffer.read(1)\n'
    if variant == 'late_stderr': code += 'sys.stderr.write("PRIVATE_LATE_EXCEPTION")\n'
    worker = tmp_path / 's1_precheck.py'
    worker.write_bytes(code.encode())
    launcher = (ROOT / 'scripts/Invoke-S1Precheck.ps1').read_text()
    import re
    pin = '0' * 64 if variant == 'wrong_pin' else hashlib.sha256(worker.read_bytes()).hexdigest()
    launcher = re.sub(r"\$workerPin='[^']+'", "$workerPin='" + pin + "'", launcher)
    if variant == 'timeout':
        launcher = launcher.replace('$watch.Elapsed.TotalSeconds -ge 30', '$watch.Elapsed.TotalSeconds -ge 1')
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
    assert out['authorization'] == 'NONE' and out['g0_status'] == 'FAIL_CLOSED'
    if variant in ('valid', 'partial'):
        assert p.returncode == 0 and out['outcome'] == 'PASS_PRECHECK_ONLY'
    else:
        assert p.returncode in (1, 2) and out['outcome'] != 'PASS_PRECHECK_ONLY'
    if variant in ('timeout', 'memory'):
        assert out['reason'] == 'BUDGET_EXCEEDED'
    if variant == 'wrong_python': assert out['attempts'] == 0
