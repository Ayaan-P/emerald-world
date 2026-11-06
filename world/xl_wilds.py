"""Compile an agent-authored blueprint into an offline 127×127 outdoor area."""
import argparse,json
from pathlib import Path
from collections import deque
from .cave_blueprint import proposal_from_blueprint
SIDE=127
MAGIC=b'EWGMAP0A'

def encode(proposal):
    if type(proposal) is not dict or set(proposal)!={'rows','spawn','exit'} or proposal['spawn']!=[1,1] or proposal['exit']!=[125,125]:raise ValueError('invalid XL proposal')
    rows=proposal['rows']
    if type(rows) is not list or len(rows)!=SIDE or any(type(r) is not str or len(r)!=SIDE or any(c not in '.#' for c in r) for r in rows):raise ValueError('invalid XL rows')
    if any(c!='#' for c in rows[0]+rows[-1]) or any(r[0]!='#' or r[-1]!='#' for r in rows):raise ValueError('open perimeter')
    if any(rows[y][x]!='.' for x,y in ((1,1),(125,124),(125,125))):raise ValueError('invalid entry or exit')
    seen={(1,1)};q=deque(seen)
    while q:
        x,y=q.popleft()
        for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            if 0<=nx<SIDE and 0<=ny<SIDE and rows[ny][nx]=='.' and (nx,ny) not in seen:seen.add((nx,ny));q.append((nx,ny))
    if len(seen)!=sum(r.count('.') for r in rows):raise ValueError('disconnected XL area')
    return MAGIC+''.join(rows).encode('ascii')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('blueprint',type=Path);p.add_argument('output',type=Path);a=p.parse_args(argv)
    with a.blueprint.open('rb') as f:data=f.read(16385)
    if len(data)>16384:p.error('blueprint too large')
    try:doc=json.loads(data.decode('utf-8'));blob=encode(proposal_from_blueprint(doc,side=SIDE))
    except (ValueError,UnicodeError):p.error('invalid XL blueprint')
    with a.output.open('xb') as f:f.write(blob)
    print('Wrote validated offline XL wilds:',a.output)
if __name__=='__main__':main()
