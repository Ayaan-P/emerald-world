"""Owner-agent state and rule commands for an active trainer's generated event graph.

The owner-only authority queues the command to a compatible connected client;
a successful response means queued, not that the trainer received or applied it.
"""
import argparse
import json
from pathlib import Path
from .client import admin_request

def set_state(admin_socket,trainer,identity,state):
    return admin_request('', {'command':'set_event_state','trainer':trainer,'identity':identity,'state':state}, admin_path=admin_socket)

def set_rule(admin_socket,trainer,identity,state,npc,next_state,text):
    return admin_request('', {'command':'set_event_rule','trainer':trainer,'identity':identity,'state':state,'npc':npc,'next_state':next_state,'text':text}, admin_path=admin_socket)

def status(admin_socket,trainer,identity,session,sequence):
    return admin_request('', {'command':'event_command_status','trainer':trainer,'identity':identity,'session':session,'sequence':sequence}, admin_path=admin_socket)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admin-socket',required=True,type=Path);p.add_argument('--trainer',required=True);p.add_argument('--area',required=True);p.add_argument('--state',type=int);p.add_argument('--status',type=int);p.add_argument('--session');p.add_argument('--npc',type=int);p.add_argument('--next-state',type=int);p.add_argument('--text');a=p.parse_args(argv)
    if (a.state is None)==(a.status is None):p.error('choose exactly one of --state or --status')
    if (a.status is not None) != (a.session is not None):p.error('--status and --session must be supplied together')
    if a.status is not None and any(v is not None for v in (a.npc,a.next_state,a.text)):p.error('--status cannot be combined with rule fields')
    if any(v is not None for v in (a.npc,a.next_state,a.text)) and any(v is None for v in (a.npc,a.next_state,a.text)):p.error('--npc, --next-state and --text must be supplied together')
    result=status(a.admin_socket,a.trainer,a.area,a.session,a.status) if a.status is not None else set_state(a.admin_socket,a.trainer,a.area,a.state) if a.npc is None else set_rule(a.admin_socket,a.trainer,a.area,a.state,a.npc,a.next_state,a.text);print(json.dumps(result,sort_keys=True));return 0 if result.get('ok') is True else 1
if __name__=='__main__':raise SystemExit(main())
