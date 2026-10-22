"""Project disposable native probe result and bind it to exact-source provenance."""
import hashlib
import json
from pathlib import Path
import re
import run as h

h.verify()
source=Path('native-probe.json')
raw=json.loads(source.read_text(encoding='utf-8-sig')) if source.is_file() else {}
allowed=('status','native_process','creation_binding','unknown_process_service','scm_native_status_config','scm_membership','scm_coverage_reason','kernel_snapshot','module_boundary','registry_scm_boundary','native_format','access','services_changed','private_values_published','host_admission','stage','error_type')
projection={}
for key in allowed:
    value=raw.get(key)
    if type(value) is bool or isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_. -]{1,160}',value):projection[key]=value
projection.setdefault('status','BLOCKED_MISSING_PROBE')
out=Path('acceptance-public')
summary=out/'native-summary.json'
summary.write_text(json.dumps(dict(candidate_sha=h.TARGET,candidate_tree=h.TREE,probe=projection),indent=2)+'\n')
provenance=out/'provenance.json'
data=json.loads(provenance.read_text())
data.update(native_probe_status=projection['status'],native_summary_sha256=hashlib.sha256(summary.read_bytes()).hexdigest())
provenance.write_text(json.dumps(data,indent=2)+'\n')
h.safe(summary);h.safe(provenance)
