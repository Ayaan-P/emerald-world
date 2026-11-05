"""Compile agent-authored, bounded interaction graphs into native map data.

The graph is declarative: an NPC interaction in a state selects inert text and
one next state. It contains no executable scripts, shell commands or callbacks.
"""
import argparse
import json
from pathlib import Path
from .cave_blueprint import proposal_from_blueprint
from .wilds_cast import encode as encode_cast, _text

MAGIC=b'EWGMAP09'
MAX_RULES=24
RECORD_BYTES=61
EVENT_BYTES=2+MAX_RULES*RECORD_BYTES
MAX_JSON=32768

def encode(proposal,cast,events):
    if type(events) is not dict or set(events)!={'initial','rules'}:
        raise ValueError('events require initial and rules')
    initial,rules=events['initial'],events['rules']
    if type(initial) is not int or not 0<=initial<=15:raise ValueError('initial state must be 0..15')
    if type(rules) is not list or not 1<=len(rules)<=MAX_RULES:raise ValueError('events need 1..24 rules')
    if type(cast) is not list or not 1<=len(cast)<=3:raise ValueError('cast needs 1..3 characters')
    out=bytearray((initial,len(rules)));seen=set()
    for rule in rules:
        if type(rule) is not dict or set(rule)!={'state','npc','next','text'}:raise ValueError('invalid event rule')
        state,npc,nxt=rule['state'],rule['npc'],rule['next']
        if any(type(v) is not int for v in (state,npc,nxt)) or not 0<=state<=15 or not 0<=nxt<=15 or not 1<=npc<=len(cast):raise ValueError('invalid event state or character')
        if (state,npc) in seen:raise ValueError('duplicate event rule')
        seen.add((state,npc));value=_text(rule['text']);out.extend((state,npc,nxt,len(value)));out.extend(value.ljust(57,b'\0'))
    out.extend(bytes((MAX_RULES-len(rules))*RECORD_BYTES))
    return MAGIC+bytes(out)+encode_cast(proposal,cast)[8:]

def compile_document(doc):
    if type(doc) is not dict or set(doc)!={'blueprint','cast','events'}:raise ValueError('expected blueprint, cast and events')
    return encode(proposal_from_blueprint(doc['blueprint'],side=63),doc['cast'],doc['events'])

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args(argv)
    data=a.input.read_bytes()
    if len(data)>MAX_JSON:raise ValueError('input too large')
    doc=json.loads(data.decode('utf-8'));blob=compile_document(doc)
    with a.output.open('xb') as f:f.write(blob)
    print('Wrote validated offline event area:',a.output)

if __name__=='__main__':main()
