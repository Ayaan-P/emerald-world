"""Create and revise offline XL story worlds while preserving story identity."""
import secrets
from .xl_wilds_cast import validate_wire as validate_cast
from .wilds_events import encode_rules,EVENT_BYTES
from .xl_wilds_cast import META_BYTES
from .xl_painted_events import encode as encode_painted
from .cave_blueprint import proposal_from_blueprint
SIDE=127;MAGIC=b'EWGMAP0F';PAINTED=b'EWGMAP0E';ID_BYTES=16;SIZE=8+ID_BYTES+EVENT_BYTES+META_BYTES+SIDE*SIDE

def decode(blob):
    if type(blob) is not bytes or len(blob)!=SIZE or blob[:8]!=MAGIC or not any(blob[8:24]):raise ValueError('invalid versioned world')
    identity=blob[8:24];events=blob[24:24+EVENT_BYTES];cast=blob[24+EVENT_BYTES:24+EVENT_BYTES+META_BYTES];palette=blob[-SIDE*SIDE:]
    if any(c not in b'#.t' for c in palette) or any(palette[y*SIDE+x]!=ord('.') for x,y in ((1,1),(125,124),(125,125))):raise ValueError('invalid palette')
    geometry=bytes(ord('#') if c==ord('#') else ord('.') for c in palette)
    proposal,characters=validate_cast(b'EWGMAP0B'+cast+geometry)
    initial,count=events[:2]
    if not 1<=count<=24:raise ValueError('invalid event rules')
    rules=[]
    for i in range(24):
        record=events[2+i*61:2+(i+1)*61]
        if i>=count:
            if any(record):raise ValueError('invalid event padding')
            continue
        n=record[3]
        if not 1<=n<=57 or any(record[4+n:]):raise ValueError('invalid dialogue')
        try:text=record[4:4+n].decode('ascii')
        except UnicodeDecodeError:raise ValueError('invalid dialogue') from None
        rules.append({'state':record[0],'npc':record[1],'next':record[2],'text':text})
    graph={'initial':initial,'rules':rules}
    if encode_rules(graph,characters)!=events:raise ValueError('invalid event graph')
    return identity,proposal,characters,graph,palette

def create(painted,identity=None):
    if type(painted) is not bytes or len(painted)!=SIZE-ID_BYTES or painted[:8]!=PAINTED:raise ValueError('invalid painted world')
    if identity is None:
        identity=secrets.token_bytes(ID_BYTES)
    if type(identity) is not bytes or len(identity)!=ID_BYTES or not any(identity):raise ValueError('invalid world ID')
    result=MAGIC+identity+painted[8:];decode(result);return result

def revise(previous,blueprint,paint):
    identity,_,characters,graph,_=decode(previous)
    proposal=proposal_from_blueprint(blueprint,side=SIDE)
    updated=encode_painted(proposal,paint,characters,graph)
    return create(updated,identity)

def main(argv=None):
    import argparse,json
    from pathlib import Path
    from .map_store import write_map
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    c=sub.add_parser('create');c.add_argument('painted',type=Path);c.add_argument('output',type=Path);c.add_argument('--replace-output',action='store_true')
    r=sub.add_parser('revise');r.add_argument('previous',type=Path);r.add_argument('changes',type=Path);r.add_argument('output',type=Path);r.add_argument('--replace-output',action='store_true')
    a=p.parse_args(argv)
    try:
        if a.action=='create':
            with a.painted.open('rb') as f:raw=f.read(SIZE+1)
            blob=create(raw)
        else:
            with a.previous.open('rb') as f:raw=f.read(SIZE+1)
            with a.changes.open('rb') as f:data=f.read(32769)
            if len(data)>32768:raise ValueError('changes too large')
            changes=json.loads(data.decode('utf-8'))
            if type(changes) is not dict or set(changes)!={'blueprint','paint'}:raise ValueError('invalid revision')
            blob=revise(raw,changes['blueprint'],changes['paint'])
        write_map(a.output,blob,replace=a.replace_output)
    except (OSError,ValueError,UnicodeError):p.exit(1,'Could not write versioned world.\n')
    print('Wrote validated versioned world:',a.output)
if __name__=='__main__':main()
