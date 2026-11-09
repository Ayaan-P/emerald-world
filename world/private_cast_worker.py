"""Process one explicitly consented private cast request. Never deploys world code."""
import argparse
import json
from pathlib import Path
import tempfile
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


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket',required=True);parser.add_argument('--model',required=True,choices=[MODEL])
    parser.add_argument('--timeout',type=float,default=120)
    args=parser.parse_args(argv)
    try:
        from .runtime_gm import validate_config
        validate_config(args.model,args.timeout,2)
        print(json.dumps(step(args.socket,args.model,args.timeout)));return 0
    except Exception:
        # Never log private prompts/replies/exception content, and never replay.
        print(json.dumps(dict(ok=False,status='interrupted_no_retry')));return 1

if __name__=='__main__':raise SystemExit(main())
