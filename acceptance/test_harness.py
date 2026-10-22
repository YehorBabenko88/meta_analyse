"""Adversarial controls for independent evidence validation."""
import xml.etree.ElementTree as ET
import pytest
import run as h


@pytest.mark.parametrize('body,count', [
    ('<testcase classname="t" name="required"/>','2'),
    ('<testcase classname="t" name="other"/>','1'),
    ('<testcase classname="t" name="required"/><testcase classname="t" name="required"/>','2'),
    ('<testcase classname="t" name="required"><failure/></testcase>','1'),
    ('<testcase classname="t" name="required"><error/></testcase>','1'),
    ('<testcase classname="t" name="required"><skipped/></testcase>','1'),
], ids=['count','missing','duplicate','failure','error','skip'])
def test_invalid_junit_rejected(body,count):
    root=ET.fromstring('<testsuite tests="'+count+'">'+body+'</testsuite>')
    with pytest.raises(ValueError):h.validate(root,['t.required'])


@pytest.mark.parametrize('counter',['failures','errors','skipped'])
def test_inconsistent_summary_rejected(counter):
    root=ET.fromstring('<testsuite tests="1" '+counter+'="1"><testcase classname="t" name="required"/></testsuite>')
    with pytest.raises(ValueError):h.validate(root,['t.required'])


@pytest.mark.parametrize('payload',['<testsuite hostname="synthetic"/>','{"services_before":[]}', 'C:\\Users\\synthetic\\private','/tmp/synthetic','{"sid":"synthetic"}'],ids=['junit-host','scm','path','temp','sid'])
def test_private_artifact_rejected(tmp_path,payload):
    path=tmp_path/'artifact.json';path.write_text(payload)
    with pytest.raises(ValueError):h.safe(path)


def test_exact_success_accepted():
    root=ET.fromstring('<testsuite tests="1"><testcase classname="t" name="required"/></testsuite>')
    assert len(h.validate(root,['t.required']))==1
