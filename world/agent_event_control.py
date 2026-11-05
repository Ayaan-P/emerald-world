"""Owner-agent commands for an active trainer's generated event graph.

The owner-only authority queues the command to a compatible connected client;
a successful response means queued, not that the trainer received or applied it.
"""
import argparse
import json
from pathlib import Path
from .client import admin_request

def set_state(admin_socket,trainer,identity,state):
    return admin_request('', {'command':'set_event_state','trainer':trainer,'identity':identity,'state':state}, admin_path=admin_socket)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admin-socket',required=True,type=Path);p.add_argument('--trainer',required=True);p.add_argument('--area',required=True);p.add_argument('--state',required=True,type=int);a=p.parse_args(argv)
    result=set_state(a.admin_socket,a.trainer,a.area,a.state);print(json.dumps(result,sort_keys=True));return 0 if result.get('ok') is True else 1
if __name__=='__main__':raise SystemExit(main())
