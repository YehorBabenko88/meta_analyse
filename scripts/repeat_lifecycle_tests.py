"""Repeat resource-sensitive tests in fresh processes, retaining every failure."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--expected-tests', type=int, default=67)
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
        try:
            root = ET.parse(run_dir / 'tests.xml').getroot()
            cases = list(root.iter('testcase'))
            bad = [case for case in cases if any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))]
            if len(cases) != args.expected_tests or bad:
                print(f'Lifecycle contract failure: expected={args.expected_tests}, actual={len(cases)}, nonpassed={len(bad)}', flush=True)
                return 1
        except (OSError, ET.ParseError) as exc:
            print(f'Lifecycle JUnit missing or invalid: {exc}', flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
