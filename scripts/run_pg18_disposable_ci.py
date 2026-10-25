"""Explicit GitHub-hosted Linux disposable PG18 controller; no ADMINIT access."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from psycopg import connect


def need(condition):
    if not condition: raise ValueError('DISPOSABLE_PG18_BLOCKED')


def run(xml, private_log):
    cid = None
    labels = None
    outcome = 1
    def command(args, **kwargs):
        result = subprocess.run(args, capture_output=True, text=True, timeout=120, **kwargs)
        need(result.returncode == 0)
        return result.stdout.strip()
    def owned():
        info = json.loads(command(['docker','inspect',cid]))
        need(type(info) is list and len(info) == 1 and info[0]['Id'] == cid)
        actual = info[0]['Config']['Labels']
        need(type(actual) is dict and all(actual.get(key) == value for key,value in labels.items()))
    try:
        need(sys.platform == 'linux' and os.environ.get('GITHUB_ACTIONS') == 'true')
        need(os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted')
        need(os.environ.get('META_ANALYSE_DISPOSABLE_PG18') == '1')
        need(not any(k.upper().startswith('PG') and v for k,v in os.environ.items()))
        run_id = os.environ.get('GITHUB_RUN_ID',''); attempt = os.environ.get('GITHUB_RUN_ATTEMPT','')
        sha = os.environ.get('META_ANALYSE_TEST_SOURCE_SHA','')
        need(all(re.fullmatch('[1-9][0-9]{0,19}',v) for v in (run_id,attempt)))
        need(re.fullmatch('[0-9a-f]{40}',sha))
        xml = Path(xml).absolute(); private_log = Path(private_log).absolute()
        version_receipt = xml.with_suffix('.postgres.json')
        need(xml != private_log and not xml.exists() and not private_log.exists())
        need(not version_receipt.exists() and version_receipt != private_log)
        need(xml.parent.is_dir() and private_log.parent.is_dir())
        labels = {'meta-analyse.disposable':secrets.token_hex(16), 'meta-analyse.run':run_id,
                  'meta-analyse.attempt':attempt, 'meta-analyse.sha':sha}
        password = secrets.token_hex(32)
        env = dict(os.environ, POSTGRES_PASSWORD=password)
        args = ['docker','create','--network=host','--memory=768m','--cpus=1',
                '--pids-limit=128','--shm-size=128m','--tmpfs',
                '/var/lib/postgresql:rw,size=512m,noexec,nosuid,nodev',
                '--env','POSTGRES_PASSWORD','--env','POSTGRES_USER=disposable_admin',
                '--env','POSTGRES_DB=postgres','--env','PGDATA=/var/lib/postgresql/18/docker']
        for key,value in labels.items(): args += ['--label',key+'='+value]
        args += ['postgres:18.1','postgres','-c','listen_addresses=127.0.0.1','-c','port=55480']
        candidate = command(args, env=env)
        need(re.fullmatch('[0-9a-f]{64}',candidate)); cid = candidate
        owned()
        command(['docker','start',cid])  # Occupied loopback port must stop provisioning.
        for _ in range(60):
            result = subprocess.run(['docker','exec',cid,'pg_isready','-h','127.0.0.1','-p','55480',
                                     '-U','disposable_admin','-d','postgres'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0: break
            time.sleep(0.5)
        else: raise ValueError('DISPOSABLE_PG18_BLOCKED')
        owned()
        control = command(['docker','exec','--env','LC_ALL=C',cid,'pg_controldata','/var/lib/postgresql/18/docker'])
        ids = re.findall(r'^Database system identifier:\s*([1-9][0-9]*)\s*$',control,re.M)
        need(len(ids) == 1); identifier = ids[0]
        config = dict(host='127.0.0.1',hostaddr='127.0.0.1',port=55480,dbname='postgres',
                      user='disposable_admin',password=password,connect_timeout=5)
        with connect(**config,autocommit=True,options='-c statement_timeout=5000 -c lock_timeout=5000') as conn:
            row = conn.execute("SELECT pg_catalog.current_setting('server_version_num'), "
                "pg_catalog.inet_server_addr()::pg_catalog.text, pg_catalog.inet_server_port(), "
                "current_user, pg_catalog.current_database(), "
                "(pg_catalog.pg_control_system()).system_identifier::pg_catalog.text").fetchone()
            need(row == ('180001','127.0.0.1',55480,'disposable_admin','postgres',identifier))
            conn.execute('REVOKE CONNECT ON DATABASE postgres FROM PUBLIC')
            conn.execute('REVOKE CONNECT ON DATABASE template1 FROM PUBLIC')
        from psycopg.conninfo import make_conninfo
        child_env = dict(os.environ,META_ANALYSE_TEST_ADMIN_DSN=make_conninfo(**config),
                         META_ANALYSE_TEST_SYSTEM_ID=identifier)
        result = subprocess.run([sys.executable,'-m','pytest','--noconftest','-q',
            '-p','no:cacheprovider','tests/test_pg18_disposable_acceptance.py','--junitxml='+str(xml)],
            capture_output=True,text=True,timeout=300,env=child_env)
        with private_log.open('x',encoding='utf8') as stream:
            stream.write(result.stdout); stream.write(result.stderr)
        outcome = 0 if result.returncode == 0 else 1
    except Exception:
        outcome = 1
    finally:
        if cid:
            try:
                owned()
                command(['docker','rm','--force',cid])
            except Exception:
                outcome = 1
    if outcome == 0:
        try:
            with version_receipt.open('x',encoding='utf8') as stream:
                stream.write('{"server_version":180001}\n')
        except Exception:
            outcome = 1
    print('PASS: disposable PG18 tests' if outcome == 0 else 'BLOCKED: DISPOSABLE_PG18_BLOCKED')
    return outcome


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('junit'); parser.add_argument('private_log')
    args = parser.parse_args()
    raise SystemExit(run(args.junit,args.private_log))
