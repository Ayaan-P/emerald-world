"""Bounded agent-authored characters in offline XL outdoor worlds."""
from collections import deque
from .xl_wilds import encode as encode_xl
from .wilds_cast import _text, META_BYTES, RECORD_BYTES

MAGIC=b'EWGMAP0B'
SIDE=127

def encode(proposal,cast):
    base=encode_xl(proposal)
    if type(cast) is not list or not 1<=len(cast)<=3:raise ValueError('cast must have one to three characters')
    cells=base[8:];blocked=set();records=bytearray()
    for item in cast:
        if type(item) is not dict or set(item)!={'gfx','x','y','text'}:raise ValueError('invalid character')
        gfx,x,y=item['gfx'],item['x'],item['y']
        if type(gfx) is not int or gfx not in (7,8) or type(x) is not int or type(y) is not int or not 1<=x<126 or not 1<=y<126 or (x,y) in ((1,1),(125,124),(125,125)) or (x,y) in blocked or cells[y*SIDE+x]!=ord('.'):raise ValueError('invalid character position')
        text=_text(item['text']);records.extend((gfx,x,y,len(text)));records.extend(text.ljust(57,b'\0'));blocked.add((x,y))
    seen={(1,1)};q=deque(seen)
    while q:
        x,y=q.popleft()
        for point in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            a,b=point
            if 0<=a<SIDE and 0<=b<SIDE and point not in blocked and point not in seen and cells[b*SIDE+a]==ord('.'):seen.add(point);q.append(point)
    if len(seen)!=cells.count(b'.')-len(blocked):raise ValueError('characters block access')
    for x,y in blocked:
        if not any(p in seen for p in ((x,y-1),(x+1,y),(x,y+1),(x-1,y))):raise ValueError('character cannot be reached')
    records.extend(bytes((3-len(cast))*RECORD_BYTES))
    return MAGIC+bytes([len(cast)])+bytes(records)+cells

def validate_wire(blob):
    if type(blob) is not bytes or len(blob)!=8+META_BYTES+SIDE*SIDE or blob[:8]!=MAGIC:raise ValueError('invalid XL cast file')
    meta=blob[8:8+META_BYTES];count=meta[0]
    if not 1<=count<=3:raise ValueError('invalid cast count')
    cast=[]
    for i in range(3):
        r=meta[1+i*RECORD_BYTES:1+(i+1)*RECORD_BYTES]
        if i>=count:
            if any(r):raise ValueError('noncanonical cast padding')
            continue
        n=r[3]
        if not 1<=n<=57 or any(r[4+n:]):raise ValueError('invalid dialogue')
        try:text=r[4:4+n].decode('ascii')
        except UnicodeDecodeError:raise ValueError('invalid dialogue') from None
        cast.append({'gfx':r[0],'x':r[1],'y':r[2],'text':text})
    cells=blob[8+META_BYTES:];rows=[cells[y*SIDE:(y+1)*SIDE].decode('ascii') for y in range(SIDE)]
    proposal={'rows':rows,'spawn':[1,1],'exit':[125,125]}
    if encode(proposal,cast)!=blob:raise ValueError('noncanonical cast map')
    return proposal,cast

def compile_document(doc):
    from .cave_blueprint import proposal_from_blueprint
    if type(doc) is not dict or set(doc)!={'blueprint','cast'}:raise ValueError('expected blueprint and cast')
    return encode(proposal_from_blueprint(doc['blueprint'],side=SIDE),doc['cast'])

def main(argv=None):
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args(argv)
    with a.input.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('input too large')
    try:blob=compile_document(json.loads(data.decode('utf-8')))
    except (ValueError,UnicodeError):p.error('invalid XL cast blueprint')
    with a.output.open('xb') as f:f.write(blob)
    print('Wrote validated offline XL cast area:',a.output)
if __name__=='__main__':main()
