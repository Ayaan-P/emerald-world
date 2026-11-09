"""Process one explicitly consented private cast request. Never deploys world code."""
import argparse
import json
from pathlib import Path
import tempfile
import time
from . import gm
from .canonical_reflection import prompt
from .runtime_gm import MODEL, luna_author_argv


def step(socket,model,timeout=120,*,request=None,author=None):
    request=request or (lambda body:gm.admin_request(socket,body,timeout))
    claimed=request({'command':'private_cast_claim'})
    if claimed.get('ok') is not True:raise ValueError('Private request claim refused.')
    item=claimed.get('request')
    if item is None:return dict(ok=True,status='idle')
    # Do not fetch inspect/history, previous code, parties or another player.
    text=prompt(item['context'])
    if author is None:
        with tempfile.TemporaryDirectory(prefix='private-cast-') as directory:
            wire=gm._run_author(luna_author_argv(model,timeout)+['--private-cast'],text,timeout,{},Path(directory))
            result=json.loads(wire)
    else:result=author(text)
    finished=request(dict(command='private_cast_finish',id=item['id'],lease=item['lease'],result=result))
    return dict(ok=finished.get('ok') is True,status='ready' if finished.get('ok') is True else 'not_applied')



def watch(socket,model,timeout=120,*,max_jobs=8,idle_seconds=300,poll=2,request=None,author=None,clock=time.monotonic,sleep=time.sleep):
    """Explicit host session, not an automatically installed background service."""
    if type(max_jobs) is not int or not 1<=max_jobs<=32:raise ValueError('max jobs must be 1..32')
    if not 1<=idle_seconds<=3600 or not 1<=poll<=30:raise ValueError('invalid watch timing')
    processed=0;last_work=clock()
    while processed<max_jobs and clock()-last_work<idle_seconds:
        result=step(socket,model,timeout,request=request,author=author)
        if result['status']=='idle':sleep(poll);continue
        processed+=1;last_work=clock()
        # Stale results can follow a NEW decision; model/API exceptions escape
        # and stop the watcher, never automatically replay an interrupted call.
    return dict(ok=True,status='job_limit' if processed==max_jobs else 'idle_timeout',processed=processed)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket',required=True);parser.add_argument('--model',required=True,choices=[MODEL])
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--watch',action='store_true',help='Explicit bounded host session for queued private requests')
    parser.add_argument('--max-jobs',type=int,default=8)
    parser.add_argument('--idle-seconds',type=float,default=300)
    args=parser.parse_args(argv)
    try:
        from .runtime_gm import validate_config,preflight_author
        validate_config(args.model,args.timeout,2)
        preflight_author() # Do not consume private grants when the CLI cannot run.
        result=(watch(args.socket,args.model,args.timeout,max_jobs=args.max_jobs,idle_seconds=args.idle_seconds)
                if args.watch else step(args.socket,args.model,args.timeout))
        print(json.dumps(result));return 0
    except Exception:
        # Never log private prompts/replies/exception content, and never replay.
        print(json.dumps(dict(ok=False,status='interrupted_no_retry')));return 1

if __name__=='__main__':raise SystemExit(main())
