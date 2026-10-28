"""Offline, synthetic-only S0 command contract. Does not launch Python on ADMINIT."""
import json
import re
import sys

FLAGS=('-B','-E','-s','-S')
def check(argv):
    if type(argv) is not list or len(argv)!=5 or not all(type(x) is str for x in argv):
        return 'BLOCKED'
    executable,*flags=argv
    if not re.fullmatch(r'[A-Za-z]:\\(?:[^\\/:*?"<>|]+\\)+python(?:3(?:\.12)?)?\.exe',executable,re.I):
        return 'BLOCKED'
    if tuple(flags)!=FLAGS:return 'BLOCKED'
    return 'COMMAND_SHAPE_ONLY'

def main():
    # No project imports, subprocesses, host inventory, filesystem writes or native calls.
    samples=[
        ['C:\\Approved\\Python312\\python.exe',*FLAGS],
        ['python',*FLAGS],
        ['C:\\Approved\\Python312\\python.exe','-B','-E','-s','-O'],
    ]
    assert [check(x) for x in samples]==['COMMAND_SHAPE_ONLY','BLOCKED','BLOCKED']
    print(json.dumps({'status':'PASS_OFFLINE_CONTRACT','physical_authorization':'NONE',
                      'loader_attestation':'NOT_EVALUATED','namespace':'NOT_AUTHORIZED'}))
if __name__=='__main__':main()
