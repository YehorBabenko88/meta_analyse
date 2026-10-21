"""Record and verify exact Actions checkout identity; no branch-name inference."""
import json, os, subprocess
from pathlib import Path
actual=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
event=os.environ.get('GITHUB_EVENT_NAME')
expected=os.environ['GITHUB_SHA']
if event == 'pull_request':
    expected=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))['pull_request']['head']['sha']
if actual != expected:
    raise SystemExit('Actions checkout SHA mismatch')
Path('source-sha.json').write_text(json.dumps(dict(sha=actual,expected_sha=expected,event=event,
    event_sha=os.environ['GITHUB_SHA'],tree_sha=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()),indent=2)+'\n',encoding='utf-8')
print('Verified source SHA:',actual)
