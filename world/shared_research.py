"""Public aggregate of deliberately published native Dex flags, never save writes."""
import json,time
from pathlib import Path
BASIS='opted_in_client_reported_dex_flags'
MAX_DEX=1026

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS shared_research(dex INTEGER PRIMARY KEY,flags INTEGER NOT NULL)')

def names():
    rows=json.loads(Path(__file__).with_name('encounter_traits.json').read_text())['species']
    result={}
    for row in rows:result.setdefault(row['national_dex'],row['name'])
    return result

def catalog(server):
    setup(server.db)
    return dict(basis=BASIS,limits='Public aggregate of voluntarily reported personal seen/caught flags. Not verified captures, current ownership, location or a shared personal Pokedex.',entries=[dict(dex=d,seen=bool(f&1),caught=bool(f&2)) for d,f in server.db.execute('SELECT dex,flags FROM shared_research ORDER BY dex')])

def handle(server,conn,raw):
    setup(server.db)
    try:
        fields=raw.decode('ascii').split(' ')
        if len(fields)!=4 or fields[:3]!=['D','REPORT','1']:raise ValueError('format')
        packed=fields[3]
        if not 1<=len(packed)<=MAX_DEX//2 or any(c not in '0123456789abcdef' for c in packed):raise ValueError('flags')
        flags=[v for c in packed for v in (int(c,16)&3,int(c,16)>>2)]
        peer=conn['presence']
        if not peer.get('state') or time.monotonic()-peer.get('state_time',0)>5 or not peer['state'][6] or server.link_protocol.busy(conn['id']):raise ValueError('session')
        # Single atomic publication: no private lineage, trainer or raw save retained.
        added=[]
        with server.db:
            for dex,c in enumerate(flags,1):
                value=int(c)
                if not value:continue
                prior=server.db.execute('SELECT flags FROM shared_research WHERE dex=?',(dex,)).fetchone()
                old=prior[0] if prior else 0
                if value|old!=old:
                    server.db.execute('INSERT OR REPLACE INTO shared_research VALUES(?,?)',(dex,value|old));added.append([dex,value&~old])
            if added:
                seq=server.memory.append('shared_research_published',dict(entries=added,basis=BASIS,publication='explicit_current_dex_snapshot',limits='Client-reported seen/caught flags, not verified captures or current Pokemon ownership. No trainer, save, party or location published.'))
                server.revision=seq
        return 'D ACK 1\n'
    except (ValueError,KeyError,UnicodeError):return 'D ERROR 1\n'

def command(server,conn,words):
    from .guilds import GuildError
    entries=catalog(server)['entries'];labels=names()
    if not words:return ['Shared research: %d reported seen / %d reported caught.'%(sum(r['seen'] for r in entries),sum(r['caught'] for r in entries)), 'Search: /guild research NAME or National Dex number. List: /guild research page N.', 'Native /research explains one-time publication. Personal Dex unchanged.']
    if len(words)==2 and words[0]=='page' and words[1].isdigit():
        page=int(words[1]);rows=entries[page*8:page*8+8] if page<256 else []
    elif len(words)==1:
        term=words[0].upper();rows=[r for r in entries if str(r['dex'])==term or term in labels.get(r['dex'],'')][:8]
    else:raise GuildError('Use /guild research [NAME|NUMBER|page N]')
    return ['Public client reports (not verified captures):']+['#%d %s: %s%s'%(r['dex'],labels.get(r['dex'],'Unknown name'), 'seen ' if r['seen'] else '', 'caught' if r['caught'] else '') for r in rows]+([] if rows else ['No matching published findings.'])


def relevant(event, identity):
    # Only an anonymous, already-public aggregate delta. No attribution, locations
    # or claim that Birch met the reporter or saw an individual Pokemon.
    if (identity!='canon_birch' or event.get('event')!='shared_research_published'
            or event.get('basis')!=BASIS or event.get('publication')!='explicit_current_dex_snapshot'):
        return False
    entries=event.get('entries')
    return (type(entries) is list and 1<=len(entries)<=MAX_DEX
        and all(type(e) is list and len(e)==2 and type(e[0]) is int and 1<=e[0]<=MAX_DEX
                and type(e[1]) is int and 1<=e[1]<=3 for e in entries)
        and len({e[0] for e in entries})==len(entries))
