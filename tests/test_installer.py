import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows installer')

def test_failed_pip_install_never_reports_success_or_creates_launcher(tmp_path):
    script = tmp_path / 'install.ps1'
    shutil.copy(Path(__file__).parents[1] / 'install.ps1', script)
    shutil.copy(Path(__file__).parents[1] / 'requirements.lock', tmp_path / 'requirements.lock')
    # Deliberately not a Python project. Native pip must fail.
    shell = shutil.which('pwsh') or shutil.which('powershell')
    command = [shell, '-NoProfile', '-NonInteractive', '-File', str(script), '-Python', sys.executable]
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path / 'local'), PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
    missing = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert missing.returncode != 0
    assert 'Specify -MathWheel and -TerminanWheel' in missing.stderr
    assert not (tmp_path / 'local' / 'MetaAnalyse').exists()

    # These paths are accepted as inputs but cannot be installed. The missing
    # Meta project must fail the application pip step before either is opened.
    math_wheel = tmp_path / 'unified_math_kernels-0.1.0-py3-none-any.whl'
    terminan_wheel = tmp_path / 'unified_terminan-0.1.0-py3-none-any.whl'
    for path in (math_wheel, terminan_wheel):
        path.touch()
    result = subprocess.run(
        [*command, '-MathWheel', str(math_wheel), '-TerminanWheel', str(terminan_wheel)],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0, result.stdout
    assert 'Dependency installation failed' in result.stderr
    assert not (tmp_path / 'local' / 'MetaAnalyse' / 'run.cmd').exists()
    assert 'Installed. Start:' not in result.stdout
