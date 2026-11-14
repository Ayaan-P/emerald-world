"""Compile capability-gated shared outdoor terrain using reviewed native metatiles."""
from .cave_blueprint import proposal_from_blueprint
from .xl_wilds import encode as encode_geometry
MAGIC=b'EWGMAP1A';SIDE=127

def encode(proposal,paint):
    base=encode_geometry(proposal);cells=bytearray(base[8:])
    if type(paint) is not list or len(paint)>64:raise ValueError('paint must be at most 64 rectangles')
    colors={'water':ord('#'),'grass':ord('.'),'tall_grass':ord('t'),'sand':ord('s'),'long_grass':ord('g'),'rock':ord('r')}
    for rect in paint:
        if type(rect) is not dict or set(rect)!={'x','y','width','height','terrain'}:raise ValueError('invalid paint rectangle')
        x,y,w,h=(rect[k] for k in ('x','y','width','height'));kind=rect['terrain']
        if any(type(v) is not int for v in (x,y,w,h)) or x<1 or y<1 or w<1 or h<1 or x+w>126 or y+h>126 or type(kind) is not str or kind not in colors:raise ValueError('invalid paint rectangle')
        for yy in range(y,y+h):cells[yy*SIDE+x:yy*SIDE+x+w]=bytes([colors[kind]])*w
    if any(cells[y*SIDE+x]!=ord('.') for x,y in ((1,1),(125,124),(125,125))):raise ValueError('protected entrance or exit')
    geometry=bytes(ord('#') if c in (ord('#'),ord('r')) else ord('.') for c in cells)
    encode_geometry({'rows':[geometry[y*SIDE:(y+1)*SIDE].decode('ascii') for y in range(SIDE)],'spawn':[1,1],'exit':[125,125]})
    return MAGIC+bytes(cells)

def compile_document(doc):
    if type(doc) is not dict or set(doc)!={'blueprint','paint'}:raise ValueError('expected blueprint and paint')
    return encode(proposal_from_blueprint(doc['blueprint'],side=SIDE),doc['paint'])

def main(argv=None):
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--replace-output',action='store_true');a=p.parse_args(argv)
    with a.input.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('input too large')
    try:blob=compile_document(json.loads(data.decode('utf-8')))
    except (ValueError,UnicodeError):p.error('invalid XL terrain blueprint')
    from .map_store import write_map
    write_map(a.output,blob,replace=a.replace_output)
    print('Wrote validated offline XL terrain:',a.output)
if __name__=='__main__':main()
