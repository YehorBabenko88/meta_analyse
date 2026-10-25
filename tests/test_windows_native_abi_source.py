"""Source-only regression: never execute the PowerShell collector or Add-Type."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "commissioning" / "process-evidence.ps1"


def test_service_config_size_probe_requires_insufficient_buffer():
    source = SOURCE.read_text(encoding="utf-8")
    assert "bool sizeQuerySucceeded=QueryServiceConfig(service,IntPtr.Zero,0,out size);" in source
    assert "configError!=122" in source
    assert "sizeQuerySucceeded||configError!=122||size<=0||size>65536" in source
    assert 'row.error_stage="QUERY_SERVICE_CONFIG_SIZE"' in source


def test_native_handle_and_buffer_cleanup_boundaries_remain_present():
    source = SOURCE.read_text(encoding="utf-8")
    assert "finally {Marshal.FreeHGlobal(buffer);}" in source
    assert "finally {CloseServiceHandle(service);}" in source
    assert "finally {CloseServiceHandle(manager);}" in source
    assert "finally {CloseHandle(h);}" in source


def test_native_image_and_module_access_are_not_bypassed():
    source = SOURCE.read_text(encoding="utf-8")
    assert "OpenProcess(0x1000,false,pid)" in source
    assert "OpenProcess(0x410,false,pid)" in source
    assert "QueryFullProcessImageName(h,0,path,ref length)" in source
    assert "EnumProcessModulesEx(h,modules," in source
