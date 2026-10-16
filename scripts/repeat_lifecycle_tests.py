"""Repeat resource-sensitive tests in fresh processes, retaining every failure."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be positive')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONASYNCIODEBUG='1')
    modules = ['tests/test_desktop_lifecycle.py', 'tests/test_qt_diagnostics.py',
               'tests/test_windows_smoke.py', 'tests/test_desktop_service.py',
               'tests/test_session_lifecycle.py', 'tests/test_http_client.py']
    for index in range(1, args.runs + 1):
        run_dir = args.output_dir / f'run-{index:02d}'
        run_dir.mkdir(exist_ok=True)
        command = [sys.executable, '-m', 'pytest', '-q', '-W', 'error::RuntimeWarning',
                   *modules, f'--junitxml={run_dir / "tests.xml"}',
                   f'--basetemp={run_dir / "temp"}']
        with (run_dir / 'tests.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        lines = (run_dir / 'tests.log').read_text(encoding='utf-8', errors='replace').splitlines()
        print(f'Lifecycle repetition {index}/{args.runs}: exit {result.returncode}', flush=True)
        print('\n'.join(lines[-12:]), flush=True)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
