"""Bounded generated outdoor cast; all dialogue is literal inert text."""
from collections import deque
import re
from .wilds import encode as encode_wilds
from .wilds_guide import prepare as prepare_guide

SIDE=63
MAGIC=b'EWGMAP08'
POSITIONS=((2,1),(20,20),(40,40))
RECORD_BYTES=61
META_BYTES=1+3*RECORD_BYTES

def prepare(proposal,count):
    if type(count) is not int or not 1<=count<=3:raise ValueError('cast must have one to three characters')
    rows=[list(row) for row in prepare_guide(proposal)['rows']]
    blocked=set(POSITIONS[:count])
    for x,y in blocked:
        rows[y][x]='.';rows[y][x-1]='.'
    while True:
        seen={(1,1)};q=deque([(1,1)])
        while q:
            x,y=q.popleft()
            for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
                if 0<nx<SIDE-1 and 0<ny<SIDE-1 and (nx,ny) not in blocked and rows[ny][nx]=='.' and (nx,ny) not in seen:
                    seen.add((nx,ny));q.append((nx,ny))
        missing={(x,y) for y in range(1,SIDE-1) for x in range(1,SIDE-1) if rows[y][x]=='.' and (x,y) not in blocked and (x,y) not in seen}
        if not missing:break
        # Multi-source BFS finds the shortest carve through interior walls,
        # never through a character. Sorted seeds make the result deterministic.
        q=deque(sorted(seen));parent={xy:None for xy in seen};target=None
        while q and target is None:
            x,y=q.popleft()
            for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
                point=(nx,ny)
                if 0<nx<SIDE-1 and 0<ny<SIDE-1 and point not in blocked and point not in parent:
                    parent[point]=(x,y)
                    if point in missing:target=point;break
                    q.append(point)
        if target is None:raise ValueError('cannot connect cast layout')
        while target is not None:
            x,y=target;rows[y][x]='.';target=parent[target]
    result={'rows':[''.join(row) for row in rows],'spawn':[1,1],'exit':[61,61]}
    encode_wilds(result)
    return result

def _text(text):
    if (type(text) is not str or not re.fullmatch(r"[A-Za-z0-9 .,!?'-]+(?:\n[A-Za-z0-9 .,!?'-]+)?",text)
            or any(len(line)>28 or not line.strip() for line in text.split('\n'))):
        raise ValueError('character dialogue needs one or two short literal lines')
    value=text.encode('ascii')
    if len(value)>57:raise ValueError('dialogue too long')
    return value

def encode(proposal,cast):
    if type(cast) is not list or not 1<=len(cast)<=3:raise ValueError('cast must have one to three characters')
    records=bytearray()
    for index,item in enumerate(cast):
        if type(item) is not dict or set(item)!={'gfx','text'} or type(item['gfx']) is not int or item['gfx'] not in (7,8):
            raise ValueError('invalid character')
        text=_text(item['text']);x,y=POSITIONS[index]
        records.extend((item['gfx'],x,y,len(text)));records.extend(text.ljust(57,b'\0'))
    records.extend(bytes((3-len(cast))*RECORD_BYTES))
    terrain=prepare(proposal,len(cast))
    return MAGIC+bytes([len(cast)])+bytes(records)+encode_wilds(terrain)[8:]
