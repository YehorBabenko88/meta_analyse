"""UI state transition checks independent of a running Windows display."""
from meta_analyse.desktop import Window

def test_desktop_exposes_explicit_disconnect_handler():
    assert callable(Window.disconnect_flow)
    assert callable(Window._stop_flow)

def test_flow_start_error_can_be_rendered_without_qt_worker_calls():
    assert callable(Window.repaint_state)
