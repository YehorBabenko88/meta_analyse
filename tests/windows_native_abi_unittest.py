"""Standalone source-only ABI assertions. No pytest collection or native execution."""
import importlib.util
import pathlib
import unittest

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("abi_source_checks",HERE/"test_windows_native_abi_source.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SourceContracts(unittest.TestCase):
    def test_service_config_size_probe(self): module.test_service_config_size_probe_requires_insufficient_buffer()
    def test_native_cleanup(self): module.test_native_handle_and_buffer_cleanup_boundaries_remain_present()
    def test_process_and_module_access(self): module.test_native_image_and_module_access_are_not_bypassed()

if __name__=="__main__": unittest.main()
