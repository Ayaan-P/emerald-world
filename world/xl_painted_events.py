"""Compile a painted XL world with agent-authored characters and event graph."""
from .cave_blueprint import proposal_from_blueprint
from .xl_wilds_palette import encode as encode_palette,SIDE
from .xl_wilds_events import encode as encode_events
MAGIC=b'EWGMAP0E'

def encode(proposal,paint,cast,events):
    palette=encode_palette(proposal,paint)[8:]
    geometry=bytes(ord('#') if c==ord('#') else ord('.') for c in palette)
    p={'rows':[geometry[y*SIDE:(y+1)*SIDE].decode('ascii') for y in range(SIDE)],'spawn':[1,1],'exit':[125,125]}
    event_blob=encode_events(p,cast,events)
    return MAGIC+event_blob[8:-SIDE*SIDE]+palette

def compile_document(doc):
    if type(doc) is not dict or set(doc)!={'blueprint','paint','cast','events'}:raise ValueError('expected blueprint, paint, cast and events')
    return encode(proposal_from_blueprint(doc['blueprint'],side=SIDE),doc['paint'],doc['cast'],doc['events'])

def main(argv=None):
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--replace-output',action='store_true');a=p.parse_args(argv)
    with a.input.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('input too large')
    try:blob=compile_document(json.loads(data.decode('utf-8')))
    except (ValueError,UnicodeError):p.error('invalid painted XL event blueprint')
    from .map_store import write_map
    write_map(a.output,blob,replace=a.replace_output)
    print('Wrote validated offline painted XL event area:',a.output)
if __name__=='__main__':main()
