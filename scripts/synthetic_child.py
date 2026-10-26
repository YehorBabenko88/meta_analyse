"""Trusted bootstrap for reviewed synthetic test helpers only, never host probes."""
import json
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    policy=json.loads(sys.argv[1]);sys.path[:0]=policy['paths']
    from scripts.synthetic_boundary import boundary
    class Patch:
        def setattr(self,obj,name,value):setattr(obj,name,value)
    with boundary(Patch(),child=True):
        args=policy['argv']
        if args[0]=='-c':
            sys.argv=['-c',*args[2:]]
            exec(compile(args[1],'<synthetic-child>','exec'),{'__name__':'__main__'})
        else:
            sys.argv=args
            sys.path.insert(0,str(Path(args[0]).resolve().parent))
            runpy.run_path(args[0],run_name='__main__')


if __name__=='__main__':main()
