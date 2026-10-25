"""Operator-only schema initialization, solely in the authorized private cluster."""
import argparse
import getpass
import os
import psycopg
from host_identity import authorize, validate_bound_database, validate_cluster_listener
from preflight import verify_database_role, verify_package_source


def initialize_new_schema(config, policy, expected_cluster=None):
    from meta_analyse.storage import SCHEMA
    from meta_analyse.pg_authorized_connection import authorized_private_connection, validate_connection_parameters
    validate_connection_parameters(config, expected_cluster)
    with authorized_private_connection(lambda: psycopg.connect(**config), expected_cluster) as conn:
        verify_database_role(conn,policy)
        conn.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)',(0x4D455441414E414C,))
        existing=conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace
            WHERE nspname !~ '^pg_' AND nspname NOT IN ('public','information_schema'))
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_class WHERE relnamespace='public'::pg_catalog.regnamespace)
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc WHERE pronamespace='public'::pg_catalog.regnamespace)
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_type WHERE typnamespace='public'::pg_catalog.regnamespace)""").fetchone()[0]
        if existing:
            raise ValueError('user schema is not empty; refusing initialization')
        conn.execute(SCHEMA)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','expected-sha','expected-computer','enrollment'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--cluster-system-identifier',required=True)
    p.add_argument('--operator-approved-new-schema',action='store_true',required=True)
    a=p.parse_args()
    root,_,policy,facts=authorize(a)
    verify_package_source(root)
    validate_cluster_listener(facts,policy)
    config=validate_bound_database(os.environ['META_ANALYSE_COMMISSIONING_DSN'],policy,os.environ)
    config['password']=getpass.getpass('NEW private session role password: ')
    from meta_analyse.pg_cluster_attestation import ExpectedCluster
    expected=ExpectedCluster(a.cluster_system_identifier,config['dbname'],config['user'])
    initialize_new_schema(config,policy,expected)
    print('Authorized NEW private schema initialized; no runtime test started')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('FAIL_CLOSED ('+type(exc).__name__+'); private details suppressed')
        raise SystemExit(1)
