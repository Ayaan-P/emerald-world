"""Explicit public Secret Base snapshots; native import remains recipient-controlled."""
import hashlib
import json
from pathlib import Path
import re

HEX=re.compile('[0-9a-f]{308}')

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS base_neighborhood(id TEXT PRIMARY KEY,owner TEXT NOT NULL,lineage TEXT NOT NULL,payload TEXT NOT NULL,revision TEXT NOT NULL,UNIQUE(owner,lineage))')

def key(owner,lineage):
    return hashlib.sha256((owner+'\0'+lineage).encode()).hexdigest()[:16]

def locations():
    return {r['id']:r for r in json.loads(Path(__file__).with_name('secret_base_locations.json').read_text())['entries']}

def catalog(server):
    setup(server.db)
    sites=locations()
    return [dict(id=i,owner=o,revision=r,base_location=int(p[:2],16),entrance=sites.get(int(p[:2],16)),basis='explicit_owner_client_snapshot') for i,o,p,r in server.db.execute('SELECT id,owner,payload,revision FROM base_neighborhood ORDER BY id')]

def handle(server,conn,raw):
    setup(server.db);seq=0
    try:
        f=raw.decode('ascii').split(' ')
        if len(f)<3 or f[0]!='B' or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
        seq=int(f[2])
        if seq>2**32-1 or seq<=conn.get('neighborhood_seq',0):raise ValueError()
        conn['neighborhood_seq']=seq
        lineage=conn['presence'].get('campaign_run');owner=conn['id']
        if not lineage or server.link_protocol.busy(owner):raise ValueError()
        ident=key(owner,lineage)
        if len(f)==4 and f[1]=='PUT' and HEX.fullmatch(f[3]):
            # Decode only enough to exclude malformed location; full native format validation
            # belongs to the existing recipient importer. Never promise legitimacy of a roster.
            location=int(f[3][:2],16)
            if location not in locations():raise ValueError()
            old=server.db.execute('SELECT revision FROM base_neighborhood WHERE id=?',(ident,)).fetchone()
            if not old and server.db.execute('SELECT count(*) FROM base_neighborhood').fetchone()[0]>=256:raise ValueError()
            revision=hashlib.sha256(bytes.fromhex(f[3])).hexdigest()[:16]
            with server.db:
                server.db.execute('INSERT OR REPLACE INTO base_neighborhood VALUES(?,?,?,?,?)',(ident,owner,lineage,f[3],revision))
            return f'B ACK {seq}\n'
        if len(f)==3 and f[1]=='DROP':
            with server.db:server.db.execute('DELETE FROM base_neighborhood WHERE owner=? AND lineage=?',(owner,lineage))
            return f'B ACK {seq}\n'
        if len(f)==5 and f[1]=='GET' and all(re.fullmatch('[0-9a-f]{16}',v) for v in f[3:]):
            row=server.db.execute('SELECT payload FROM base_neighborhood WHERE id=? AND revision=?',(f[3],f[4])).fetchone()
            if not row:raise ValueError()
            return f'B DATA {seq} {row[0]}\n'
        raise ValueError()
    except (ValueError,KeyError,UnicodeError):return f'B ERROR {seq}\n'

def command(server,conn,words):
    from .guilds import GuildError
    entries=catalog(server)
    if not words:return ['Public Secret Base neighborhood. /guild bases page N (starts at 0).','Experimental native: /neighborhood for disclosure. Publishing is optional; owners may be offline.','Imports use personal free slots; conflicts/full slots refuse. No teleport or automatic save.']
    if len(words)==2 and words[0]=='page' and words[1].isdigit() and len(words[1])<4:
        rows=entries[int(words[1])*3:int(words[1])*3+3]
        return [line for r in rows for line in (f"{r['owner']} | {r['entrance']['map']} ({r['entrance']['x']},{r['entrance']['y']}) | client snapshot",f"/neighborhood get {r['id']} {r['revision']}")]+([] if rows else ['No published bases on this page.'])
    raise GuildError('Use /guild bases [page N]')
