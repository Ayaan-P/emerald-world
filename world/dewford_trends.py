"""Persistent anonymous reports of accepted native Dewford phrases; no save mirroring."""
import re,time

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS dewford_public_trend(id INTEGER PRIMARY KEY CHECK(id=1),word0 INTEGER NOT NULL,word1 INTEGER NOT NULL,seed INTEGER NOT NULL,receipt INTEGER NOT NULL)')

def catalog(server):
    setup(server.db)
    row=server.db.execute('SELECT word0,word1,seed,receipt FROM dewford_public_trend WHERE id=1').fetchone()
    return dict(current=None if row is None else dict(words=list(row[:2]),seed=row[2],receipt=row[3]),basis='anonymous_native_client_report_of_accepted_phrase',limits='Optional immutable fishing-pattern adoption. Native private trends, NPC dialogue, Slot Machines and Match Call remain personal. Not catches, guaranteed Feebas, social votes or attested save durability.')

def handle(server,conn,raw):
    seq=0
    try:
        f=raw.decode('ascii').split(' ')
        if len(f) not in (3,6) or f[0]!='DT' or f[1] not in ('GET','PUT') or any(not re.fullmatch('0|[1-9][0-9]{0,9}',n) for n in f[2:]):raise ValueError()
        seq=int(f[2]);peer=conn.get('presence');state=peer.get('state') if peer else None
        if not 0<seq<2**32 or seq<=conn.get('dewford_seq',0) or server.link_channels.get(conn['id']) is not conn or server.peers.get(conn['id']) is not peer:raise ValueError()
        conn['dewford_seq']=seq
        if not state or not state[6] or not 0<=time.monotonic()-peer.get('state_time',0)<3:raise ValueError()
        if conn['id'] in server.link_protocol.sessions._locks or conn['id'] in server.link_protocol._encounters:raise ValueError()
        if tuple(state[:2]) not in ((0,11),(0,34)):raise ValueError()
        setup(server.db)
        if f[1]=='GET' and len(f)==3:
            row=server.db.execute('SELECT word0,word1,seed,receipt FROM dewford_public_trend WHERE id=1').fetchone()
            return f'DT NONE {seq}\n' if row is None else f'DT TREND {seq} {row[0]} {row[1]} {row[2]} {row[3]}\n'
        if f[1]!='PUT' or len(f)!=6 or tuple(state[:2])!=(0,11):raise ValueError()
        w0,w1,seed=map(int,f[3:])
        if not 0<=seed<65536 or any(not 0<=w<22*512 for w in (w0,w1)):raise ValueError()
        # Original stationary phrase boy is at (1,6). No arbitrary-map reports.
        if (1-state[2],6-state[3])!={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(state[4]):raise ValueError()
        old=server.db.execute('SELECT word0,word1,seed,receipt FROM dewford_public_trend WHERE id=1').fetchone()
        if old and old[:3]==(w0,w1,seed):return f'DT STORED {seq} {old[3]}\n'
        with server.db:
            receipt=server.memory.append('dewford_trend_shared',dict(words=[w0,w1],seed=seed,basis='consenting_native_client_report_after_phrase_acceptance',limits='Anonymous accepted-phrase report, not proof of disk-save durability or a catch. Followers explicitly adopt this fishing-pattern revision; nobody is forced to reroll.'))
            server.db.execute('INSERT OR REPLACE INTO dewford_public_trend VALUES(1,?,?,?,?)',(w0,w1,seed,receipt))
        server.revision=receipt
        return f'DT STORED {seq} {receipt}\n'
    except (ValueError,KeyError,UnicodeError,TypeError):return f'DT FAIL {seq}\n'
