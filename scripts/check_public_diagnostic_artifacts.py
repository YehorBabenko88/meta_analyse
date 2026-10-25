"""Reject obvious raw diagnostic material without echoing values or filenames.

Defense in depth for explicitly listed CI outputs. This is not a universal
secret detector; CI must never collect real host facts or upload temp folders.
"""
from pathlib import Path
import re
import sys

PRIVATE_KEYS = re.compile(r'["\'](?:kernel_before|kernel_after|native_before|native_after|native_format_path|implementation_before|implementation_after|implementation_signatures|modules_before|modules_after|process_evidence|private_inventory|machine_guid|hardware_uuid|sid|binary_path|source_hashes)["\']\s*:', re.I)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('PUBLIC_ARTIFACT_GATE_REQUIRES_EXPLICIT_FILES')
    for argument in sys.argv[1:]:
        path = Path(argument)
        if not path.is_file() or path.suffix.lower() == '.dpapi':
            raise SystemExit('PUBLIC_ARTIFACT_REJECTED')
        try:
            text = path.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError):
            raise SystemExit('PUBLIC_ARTIFACT_REJECTED') from None
        if PRIVATE_KEYS.search(text) or 'PRIVATE_SENTINEL_' in text or re.search(r'\bS-1-5-(?:\d+-){2,}\d+', text):
            raise SystemExit('PUBLIC_ARTIFACT_REJECTED')
    print('Diagnostic pattern scan complete; publication NOT_AUTHORIZED')


if __name__ == '__main__':
    main()
