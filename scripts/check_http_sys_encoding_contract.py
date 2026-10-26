"""Synthetic Windows PowerShell5.1 native-byte -> Unicode -> UTF8 JSON test.

Runs only a synthetic Python emitter in a hidden child; no host inventory.
All payloads are constants. Child stdout/stderr stays private, fixed result only.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

TEXT = '\u0421\u0438\u043d\u0442\u0435\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0442\u0435\u043a\u0441\u0442 \u0451\u0436'
HARNESS = r'''param([string]$Python,[string]$Emitter,[string]$Payload,[int]$DecodePage,[int]$StdinPage)
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) { throw 'EXPECTED_DESKTOP_51' }
[Threading.Thread]::CurrentThread.CurrentCulture=[Globalization.CultureInfo]::GetCultureInfo('ru-RU')
[Threading.Thread]::CurrentThread.CurrentUICulture=[Globalization.CultureInfo]::GetCultureInfo('ru-RU')
[Console]::OutputEncoding=[Text.Encoding]::GetEncoding($DecodePage)
$OutputEncoding=[Text.Encoding]::GetEncoding($StdinPage)
# No stdin pipeline: only the synthetic child writes known bytes.
$captured=@(& $Python -B -E -s -S $Emitter $Payload)
$childExit=$LASTEXITCODE
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
[ordered]@{schema=1;major=5;minor=1;native_exit=$childExit;decoder_cp=$DecodePage;stdin_cp=$StdinPage;json_cp=65001;text=($captured -join "`n")} | ConvertTo-Json -Compress
'''
EMITTER = "import base64,sys\nsys.stdout.buffer.write(base64.b64decode(sys.argv[1])+b'\\r\\n')\nsys.stdout.buffer.flush()\n"


def check(shell):
    if os.name!='nt':raise ValueError('WINDOWS_51_REQUIRED')
    observations={}
    environment={k:v for k,v in os.environ.items() if k.casefold() not in ('psexecutionpolicypreference','psmodulepath')}
    environment['PSModulePath']=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/Modules')
    with tempfile.TemporaryDirectory(prefix='synthetic-encoding-') as folder:
        path=Path(folder);script=path/'harness.ps1';emitter=path/'emitter.py'
        script.write_text(HARNESS,encoding='ascii');emitter.write_text(EMITTER,encoding='ascii')
        for encoding,cp in [('cp866',866),('utf-8',65001)]:
            payload=base64.b64encode(TEXT.encode(encoding)).decode('ascii')
            for decoder in (866,65001):
                for stdin in (20127,65001):
                    result=subprocess.run([shell,'-NoProfile','-NonInteractive','-File',str(script),
                        '-Python',sys.executable,'-Emitter',str(emitter),'-Payload',payload,
                        '-DecodePage',str(decoder),'-StdinPage',str(stdin)],
                        capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW,env=environment)
                    if result.returncode:raise ValueError('SYNTHETIC_CHILD_REFUSED')
                    raw=result.stdout.decode('utf-8-sig');value=json.loads(raw)
                    if (set(value)!={'schema','major','minor','native_exit','decoder_cp','stdin_cp','json_cp','text'} or
                        value['schema']!=1 or value['major']!=5 or value['minor']!=1 or value['native_exit']!=0 or
                        value['decoder_cp']!=decoder or value['stdin_cp']!=stdin or value['json_cp']!=65001 or type(value['text']) is not str):
                        raise ValueError('SYNTHETIC_SCHEMA_INVALID')
                    text=value['text'];matching=cp==decoder
                    if (text==TEXT)!=matching:raise ValueError('SYNTHETIC_DECODING_UNEXPECTED')
                    if ('\ufffd' in text)!=(cp==866 and decoder==65001):raise ValueError('SYNTHETIC_REPLACEMENT_UNEXPECTED')
                    observations[(cp,decoder,stdin)]=text
        for native in (866,65001):
            for decoder in (866,65001):
                if observations[(native,decoder,20127)]!=observations[(native,decoder,65001)]:
                    raise ValueError('STDIN_PREFERENCE_CHANGED_CAPTURE')
    return len(observations)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--shell',default='powershell.exe')
    args=parser.parse_args(argv)
    try:count=check(args.shell)
    except Exception:
        print('BLOCKED: SYNTHETIC_POWERSHELL_ENCODING_CONTRACT',file=sys.stderr);return 1
    print('PASS: WindowsPowerShell5.1 synthetic encoding cases='+str(count)+'; native collection=NONE; global encoding changes=NONE')
    return 0


if __name__=='__main__':raise SystemExit(main())
