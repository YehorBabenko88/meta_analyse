"""Every external GitHub Action must be pinned to an immutable 40-hex commit SHA.

Workstream F (unified-system#156). A mutable tag such as ``@v4`` can be moved
upstream; a full commit SHA cannot. Local (``./``) actions are exempt.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USES = re.compile(r'^\s*(?:-\s*)?uses:\s*(?P<ref>[^\s#]+)(?P<comment>\s+#\s*(?P<version>\S+))?\s*$')
SHA = re.compile(r'^[0-9a-f]{40}$')
VERSION = re.compile(r'^v\d+\.\d+\.\d+$')


def workflow_uses():
    found = []
    for path in sorted((ROOT / '.github' / 'workflows').glob('*.y*ml')):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            match = USES.match(line)
            if match:
                found.append((path.name, number, match))
    return found


class WorkflowActionPinTests(unittest.TestCase):
    def test_workflows_exist(self):
        self.assertTrue(workflow_uses())

    def test_every_external_action_is_pinned_to_a_full_commit_sha(self):
        unpinned = []
        for name, number, match in workflow_uses():
            ref = match.group('ref')
            if ref.startswith('./'):
                continue
            action, _, revision = ref.partition('@')
            if not action or not SHA.match(revision):
                unpinned.append(f'{name}:{number}: {ref}')
        self.assertEqual(unpinned, [])

    def test_version_comments_name_an_exact_release(self):
        loose = []
        for name, number, match in workflow_uses():
            version = match.group('version')
            if version is not None and not VERSION.match(version):
                loose.append(f'{name}:{number}: # {version}')
        self.assertEqual(loose, [])

    def test_one_sha_per_action_version_comment(self):
        seen = {}
        for name, number, match in workflow_uses():
            version = match.group('version')
            if version is None:
                continue
            action, _, revision = match.group('ref').partition('@')
            seen.setdefault((action, version), set()).add(revision)
        conflicts = {key: sorted(value) for key, value in seen.items() if len(value) > 1}
        self.assertEqual(conflicts, {})


if __name__ == '__main__':
    unittest.main()
