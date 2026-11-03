"""One exact identity policy shared by all full-suite evidence gates."""
import hashlib
import json


def allowed_pairs(platform,scope='full'):
    allowed={('tests.test_public_junit','test_symlink_is_rejected'),
             ('tests.test_pr23_transaction','test_existing_private_survives_static_alias_spellings[symlink]')}
    if scope=='full':
        if platform in ('win32','windows'):
            allowed.add(('tests.test_headless_service','test_untracked_index_record_spoof_cannot_replace_removed_index_entry'))
        else:
            allowed.add(('tests.test_installer','test_failed_pip_install_never_reports_success_or_creates_launcher'))
    return frozenset(allowed)


def allowed_identities(platform,scope='full'):
    return frozenset('case_'+hashlib.sha256((json.dumps(list(pair),sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
                     for pair in allowed_pairs(platform,scope))
