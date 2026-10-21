"""Prompt for private role credentials in the child process; run only preflight."""
import getpass
import os
import sys
from psycopg.conninfo import make_conninfo
from host_identity import load_private

if __name__=='__main__':
    try:
        index=sys.argv.index('--enrollment')
        policy=load_private(sys.argv[index+1])
        db=policy['database']
        os.environ['META_ANALYSE_COMMISSIONING_DSN']=make_conninfo(host='127.0.0.1',port=db['port'],dbname=db['dbname'],user=db['user'],password=getpass.getpass('Private session role password: '))
        from preflight import main
        raise SystemExit(main())
    except (ValueError,KeyError,IndexError):
        print('FAIL_CLOSED; no private configuration published')
        raise SystemExit(1)
