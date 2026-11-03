"""The full-suite PG gate permits one impossible Windows filename case only."""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts.check_integration_postgres import REQUIRED

SHUTDOWN=('test_shutdown_waits_for_thread_write_before_cancelled_task_finishes',
    'test_repeated_cancellation_does_not_abandon_write',
    'test_failed_write_after_cancellation_waits_for_rollback',
    'test_write_failure_without_cancellation_is_propagated','test_successful_write_returns_result')

def test_postgres_gate_allows_only_platform_case_and_never_required_skip(tmp_path):
    root=ET.Element('testsuite',tests=str(len(REQUIRED)+len(SHUTDOWN)+1))
    for module,names in [('storage_ingestion_postgres',REQUIRED),('integration_contract_shutdown',SHUTDOWN)]:
        for name in names:ET.SubElement(root,'testcase',classname='tests.test_'+module,name=name)
    case=ET.SubElement(root,'testcase',classname='tests.test_headless_service',name='test_untracked_index_record_spoof_cannot_replace_removed_index_entry')
    ET.SubElement(case,'skipped',message='Windows forbids TAB in filenames')
    xml=tmp_path/'tests.xml'
    def run():
        ET.ElementTree(root).write(xml)
        return subprocess.run([sys.executable,'scripts/check_integration_postgres.py',str(xml)],capture_output=True).returncode
    assert (run()==0)==(sys.platform=='win32')
    case.set('name','unknown_optional_case')
    assert run()!=0
    case.set('name','test_untracked_index_record_spoof_cannot_replace_removed_index_entry')
    ET.SubElement(root[0],'skipped',message='missing actual PostgreSQL execution')
    assert run()!=0
