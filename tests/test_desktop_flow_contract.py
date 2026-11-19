"""UI state transition checks independent of a running Windows display."""
from meta_analyse.desktop import Window

def test_desktop_exposes_explicit_disconnect_handler():
    assert callable(Window.disconnect_flow)
    assert callable(Window._stop_flow)

def test_flow_start_error_can_be_rendered_without_qt_worker_calls():
    assert callable(Window.repaint_state)


def test_legacy_desktop_cli_refuses_before_qt_or_exchange_start(monkeypatch):
    import pytest
    import meta_analyse.desktop as desktop

    def no_qt(*_args, **_kwargs):
        raise AssertionError("obsolete desktop must not construct a Qt application")

    monkeypatch.setattr(desktop, "QApplication", no_qt)
    monkeypatch.setattr(desktop, "Window", no_qt)
    with pytest.raises(SystemExit, match="META_LEGACY_TERMINAL_DISABLED_USE_UNIFIED_TERMINAN"):
        desktop.main()


def test_obsolete_module_entrypoint_refuses_in_fresh_process():
    import os
    import subprocess
    import sys

    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    completed = subprocess.run(
        [sys.executable, "-m", "meta_analyse.desktop"],
        capture_output=True, text=True, env=env, timeout=20, check=False,
    )
    assert completed.returncode != 0
    assert "META_LEGACY_TERMINAL_DISABLED_USE_UNIFIED_TERMINAN" in completed.stderr
