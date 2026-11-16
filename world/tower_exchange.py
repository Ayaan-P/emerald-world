"""Explicit public stock Battle Tower records; native import remains recipient-controlled."""
import hashlib
import re

HEX=re.compile('[0-9a-f]{298}')

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS tower_exchange(id TEXT PRIMARY KEY,owner TEXT NOT NULL,lineage TEXT NOT NULL,payload TEXT NOT NULL,revision TEXT NOT NULL,UNIQUE(owner,lineage))')

def key(owner,lineage):
    return hashlib.sha256((owner+'\0'+lineage).encode()).hexdigest()[:16]

def catalog(server):
    setup(server.db)
    return [dict(id=i,owner=o,revision=r,level_mode=int(p[2:4],16),streak=int.from_bytes(bytes.fromhex(p[6:10]),'little'),basis='explicit_client_record_not_verified_achievement') for i,o,p,r in server.db.execute('SELECT id,owner,payload,revision FROM tower_exchange ORDER BY id')]

def handle(server,conn,raw):
    setup(server.db);seq=0
    try:
        f=raw.decode('ascii').split(' ')
        if len(f)<3 or f[0]!='TR' or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
        seq=int(f[2])
        if seq>2**32-1 or seq<=conn.get('tower_record_seq',0):raise ValueError()
        conn['tower_record_seq']=seq
        lineage=conn['presence'].get('campaign_run');owner=conn['id']
        if not lineage or server.link_protocol.busy(owner):raise ValueError()
        ident=key(owner,lineage)
        if len(f)==4 and f[1]=='PUT' and HEX.fullmatch(f[3]):
            # V1 fixed-width normalized record, never raw native struct/padding.
            data=bytes.fromhex(f[3])
            if data[0]!=1 or data[1]>1 or int.from_bytes(data[3:5],'little')==0:raise ValueError()
            old=server.db.execute('SELECT revision FROM tower_exchange WHERE id=?',(ident,)).fetchone()
            if not old and server.db.execute('SELECT count(*) FROM tower_exchange').fetchone()[0]>=256:raise ValueError()
            revision=hashlib.sha256(bytes.fromhex(f[3])).hexdigest()[:16]
            with server.db:
                server.db.execute('INSERT OR REPLACE INTO tower_exchange VALUES(?,?,?,?,?)',(ident,owner,lineage,f[3],revision))
            return f'TR ACK {seq}\n'
        if len(f)==3 and f[1]=='DROP':
            with server.db:server.db.execute('DELETE FROM tower_exchange WHERE owner=? AND lineage=?',(owner,lineage))
            return f'TR ACK {seq}\n'
        if len(f)==5 and f[1]=='GET' and all(re.fullmatch('[0-9a-f]{16}',v) for v in f[3:]):
            row=server.db.execute('SELECT payload FROM tower_exchange WHERE id=? AND revision=?',(f[3],f[4])).fetchone()
            if not row:raise ValueError()
            return f'TR DATA {seq} {row[0]}\n'
        raise ValueError()
    except (ValueError,KeyError,UnicodeError):return f'TR ERROR {seq}\n'

def command(server,conn,words):
    from .guilds import GuildError
    entries=catalog(server)
    if not words:return ['Optional Tower record exchange: /guild tower page 0.', '/towerrecord for disclosure and experimental native controls. Stock Tower eligibility still decides appearances.']
    if len(words)==2 and words[0]=='page' and words[1].isdigit() and len(words[1])<4:
        rows=entries[int(words[1])*3:int(words[1])*3+3]
        return [line for r in rows for line in (f"{r['owner']} | mode {r['level_mode']} | reported streak {r['streak']}",f"/towerrecord get {r['id']} {r['revision']}")]+([] if rows else ['No published records on this page.'])
    raise GuildError('Use /guild tower [page N]')
