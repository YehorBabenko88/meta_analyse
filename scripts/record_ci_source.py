"""Record and verify exact Actions checkout identity; no branch-name inference."""
import json, os, subprocess
from pathlib import Path
actual=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
expected=os.environ['GITHUB_SHA']
if actual != expected:
    raise SystemExit('Actions checkout SHA mismatch')
Path('source-sha.json').write_text(json.dumps(dict(sha=actual,expected_sha=expected,event=os.environ.get('GITHUB_EVENT_NAME')),indent=2)+'\n',encoding='utf-8')
print('Verified source SHA:',actual)
