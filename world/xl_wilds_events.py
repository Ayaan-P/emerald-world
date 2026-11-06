"""Offline XL event graphs with agent-placed characters and literal dialogue."""
from .wilds_events import encode_rules,EVENT_BYTES
from .xl_wilds_cast import encode as encode_cast,SIDE
from .cave_blueprint import proposal_from_blueprint
MAGIC=b'EWGMAP0C'

def encode(proposal,cast,events):
    terrain=encode_cast(proposal,cast)
    return MAGIC+encode_rules(events,cast)+terrain[8:]

def compile_document(doc):
    if type(doc) is not dict or set(doc)!={'blueprint','cast','events'}:raise ValueError('expected blueprint, cast and events')
    return encode(proposal_from_blueprint(doc['blueprint'],side=SIDE),doc['cast'],doc['events'])

def main(argv=None):
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args(argv)
    with a.input.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('input too large')
    try:blob=compile_document(json.loads(data.decode('utf-8')))
    except (ValueError,UnicodeError):p.error('invalid XL event blueprint')
    with a.output.open('xb') as f:f.write(blob)
    print('Wrote validated offline XL event area:',a.output)
if __name__=='__main__':main()
