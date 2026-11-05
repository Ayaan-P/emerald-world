"""Offline generated wilds with one literal, model-authored guide."""
from collections import deque
import re
from .wilds import encode as encode_wilds

SIDE=63
MAGIC=b'EWGMAP07'
TEXT_MAX=57
META_BYTES=59

def prepare(proposal):
    """Make the fixed guide position accessible without blocking the route."""
    encode_wilds(proposal)  # Independently reject malformed source first.
    rows=[list(row) for row in proposal['rows']]
    rows[1][2]='.';rows[2][1]='.'
    while True:
        seen={(1,1)};queue=deque([(1,1)])
        while queue:
            x,y=queue.popleft()
            for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
                if (0<=nx<SIDE and 0<=ny<SIDE and (nx,ny)!=(2,1)
                        and rows[ny][nx]=='.' and (nx,ny) not in seen):
                    seen.add((nx,ny));queue.append((nx,ny))
        missing=[(x,y) for y in range(1,SIDE-1) for x in range(1,SIDE-1)
                 if rows[y][x]=='.' and (x,y)!=(2,1) and (x,y) not in seen]
        if not missing:break
        # Join a disconnected component to the guaranteed southern approach.
        tx,ty=min(missing,key=lambda pt:abs(pt[0]-1)+abs(pt[1]-2))
        x,y=1,2
        while x!=tx:
            rows[y][x]='.';x += 1 if tx>x else -1
        while y!=ty:
            rows[y][x]='.';y += 1 if ty>y else -1
        rows[y][x]='.'
    return {'rows':[''.join(row) for row in rows],'spawn':[1,1],'exit':[61,61]}

def encode(proposal,gfx,text):
    if type(gfx) is not int or gfx not in (7,8):raise ValueError('invalid guide appearance')
    if (type(text) is not str or not re.fullmatch(r"[A-Za-z0-9 .,!?'-]+(?:\n[A-Za-z0-9 .,!?'-]+)?",text)
            or any(len(line)>28 or not line.strip() for line in text.split('\n'))):
        raise ValueError('guide dialogue needs one or two literal lines of up to 28 characters')
    literal=text.encode('ascii')
    if len(literal)>TEXT_MAX:raise ValueError('guide dialogue too long')
    prepared=prepare(proposal)
    return MAGIC+bytes((gfx,len(literal)))+literal.ljust(TEXT_MAX,b'\0')+encode_wilds(prepared)[8:]


def validate_wire(metadata,cells):
    """Reject noncanonical bytes and routes blocked by the fixed guide."""
    if type(metadata) is not bytes or len(metadata)!=META_BYTES or metadata[0] not in (7,8):
        raise ValueError('invalid guide metadata')
    n=metadata[1]
    if not 1<=n<=TEXT_MAX or any(metadata[2+n:]):raise ValueError('invalid guide padding')
    try:text=metadata[2:2+n].decode('ascii')
    except UnicodeDecodeError:raise ValueError('invalid guide text') from None
    if (not re.fullmatch(r"[A-Za-z0-9 .,!?'-]+(?:\n[A-Za-z0-9 .,!?'-]+)?",text)
            or any(len(line)>28 or not line.strip() for line in text.split('\n'))):
        raise ValueError('invalid guide dialogue')
    if type(cells) is not bytes or len(cells)!=SIDE*SIDE:raise ValueError('invalid terrain')
    try:rows=[cells[y*SIDE:(y+1)*SIDE].decode('ascii') for y in range(SIDE)]
    except UnicodeDecodeError:raise ValueError('invalid terrain') from None
    proposal={'rows':rows,'spawn':[1,1],'exit':[61,61]}
    if prepare(proposal)['rows']!=rows:raise ValueError('guide blocks access')
    return metadata[0],text
