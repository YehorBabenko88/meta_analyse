"""Opt-in collection routing; no fixtures or synthetic runtime substitution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from _pytest.junitxml import mangle_test_address
from scripts import platform_coverage as coverage


def _git(*args):
    return subprocess.check_output(['git','--no-replace-objects',*args],stderr=subprocess.DEVNULL)


def pytest_collection_modifyitems(session,config,items):
    output=os.environ.get('META_ANALYSE_PLATFORM_LEDGER')
    if not output:return
    coverage.need(os.environ.get('META_ANALYSE_CI_IDENTITY_SCOPE')=='full')
    coverage.need(not config.option.keyword and not config.option.markexpr and not config.option.deselect)
    # The one existing separate PG18 gate is the only admitted collection omission.
    coverage.need(config.args==['tests'])
    coverage.need(config.option.ignore==['tests/test_pg18_disposable_acceptance.py'])
    coverage.need(not config.option.ignore_glob and not config.option.pyargs)
    suite=os.environ.get('META_ANALYSE_PLATFORM_SUITE','main')
    platform='windows' if sys.platform=='win32' else sys.platform
    rows=[];pairs=[];files={}
    root=Path(config.rootpath)
    source_bound=not bool(_git('status','--porcelain','--untracked-files=no').strip())
    for item in items:
        relative=Path(item.path).relative_to(root).as_posix()
        variant=getattr(item,'callspec',None)
        variant=variant.params.get('variant') if variant is not None else None
        rows.append((relative,getattr(item,'originalname',item.name),variant))
        names=mangle_test_address(item.nodeid)
        pairs.append((item,coverage.identity('.'.join(names[:-1]),item.name)))
        if relative not in files:
            tested=Path(item.path).read_bytes().replace(b'\r\n',b'\n')
            try:committed=_git('show','HEAD:'+relative).replace(b'\r\n',b'\n')
            except subprocess.CalledProcessError:committed=None
            source_bound=source_bound and committed==tested and not Path(item.path).is_symlink()
            files[relative]=hashlib.sha256(tested).hexdigest()
    native=coverage.classify_native(rows)
    all_ids=sorted(case for _,case in pairs)
    coverage.need(len(all_ids)==len(set(all_ids)))
    selected=coverage.selected_for(set(all_ids),set(native),platform,suite)
    # File labels are also opaque; no path strings leave the local collection.
    file_pins=sorted((hashlib.sha256(path.encode()).hexdigest(),digest) for path,digest in files.items())
    ledger=dict(schema='meta.platform.ledger.v1',sha=_git('rev-parse','HEAD').decode().strip(),
        tree=_git('rev-parse','HEAD^{tree}').decode().strip(),platform=platform,suite=suite,
        source_files_sha256=hashlib.sha256(json.dumps(file_pins,separators=(',',':')).encode()).hexdigest(),
        source_bound=bool(source_bound),identities=all_ids,native_identities=native,
        selected=sorted(selected),deferred=sorted(set(all_ids)-selected))
    coverage.validate_ledger(ledger)
    Path(output).write_text(json.dumps(ledger,sort_keys=True)+'\n',encoding='utf-8')
    retained=[item for item,case in pairs if case in selected]
    deferred=[item for item,case in pairs if case not in selected]
    items[:]=retained
    config.hook.pytest_deselected(items=deferred)
