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
    command = "& { function global:py { & '" + sys.executable.replace("'", "''") + "' @($args | Select-Object -Skip 1) }; & '" + str(script).replace("'", "''") + "' }"
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path / 'local'), PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
    result = subprocess.run([shell, '-NoProfile', '-Command', command], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0, result.stdout
    assert not (tmp_path / 'local' / 'MetaAnalyse' / 'run.cmd').exists()
    assert 'Installed. Start:' not in result.stdout
