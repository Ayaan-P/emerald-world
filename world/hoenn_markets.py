"""Optional ordinary Hoenn retail. Catalog publication is not supply or a sale."""
import json
import re
import sqlite3
import time
from .actor_shops import ITEMS
from .build_catalog import catalog_maps
SITES = {'OldaleTown_Mart': (2,4), 'LavaridgeTown_Mart': (4,4),
         'FallarborTown_Mart': (5,0), 'VerdanturfTown_Mart': (6,3),
         'PetalburgCity_Mart': (8,6), 'SlateportCity_Mart': (9,13),
         'MauvilleCity_Mart': (10,7), 'RustboroCity_Mart': (11,7),
         'FortreeCity_Mart': (12,4), 'MossdeepCity_Mart': (14,5),
         'SootopolisCity_Mart': (15,4)}

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS hoenn_market_reports(receipt INTEGER PRIMARY KEY,site TEXT,actor TEXT,revision INTEGER,item INTEGER,quantity INTEGER)')
    db.execute('CREATE TABLE IF NOT EXISTS hoenn_market_shelves(site TEXT PRIMARY KEY, actor TEXT NOT NULL, revision INTEGER NOT NULL, expires REAL NOT NULL, items TEXT NOT NULL)')

def catalog(server):
    setup(server.db)
    return dict(sites=list(SITES),items={str(k):v for k,v in ITEMS.items()},
        active=[dict(site=s,actor=a,revision=r,expires=e,items=json.loads(i))
                for s,a,r,e,i in server.db.execute('SELECT * FROM hoenn_market_shelves WHERE expires>? ORDER BY site',(time.time(),))],
        recent_reports=[dict(receipt=q,site=s,actor=a,shelf_revision=r,item=i,quantity=n) for q,s,a,r,i,n in server.db.execute('SELECT * FROM hoenn_market_reports ORDER BY receipt DESC LIMIT 64')],
        limits='Anonymous client-reported completed Community stock checkouts, not verified durable spending or finite inventory. Optional Visiting stock at existing Hoenn marts, ordinary unlimited native retail at native prices. No finite supply, delivery or revenue. Usual purchases are not reported. Usual stock and personal saves unchanged. A shop visit freezes its shelf until exit, including expiry or disconnect.')

def configure(server,actor,row,args):
    setup(server.db)
    if set(args)!={'site','items','minutes'} or args['site'] not in SITES or type(args['minutes']) is not int or not 0<=args['minutes']<=1440:
        raise ValueError('Choose a reviewed mart and 0..1440 minutes; zero closes your shelf')
    if type(args['items']) is not str or len(args['items'])>100:
        raise ValueError('Items must be a short JSON list')
    items=json.loads(args['items'])
    if type(items) is not list or len(items)>8 or any(type(i) is not int or i not in ITEMS for i in items) or len(items)!=len(set(items)):
        raise ValueError('Choose up to eight distinct ordinary retail items')
    if bool(items)!=bool(args['minutes']):
        raise ValueError('Opening needs items and duration; closing needs empty items and zero minutes')
    site=args['site']
    if catalog_maps().get(SITES[site],{}).get('name')!=site:
        raise ValueError('Exact native mart absent from this build')
    old=server.db.execute('SELECT actor,expires FROM hoenn_market_shelves WHERE site=?',(site,)).fetchone()
    if old and old[0]!=actor and old[1]>time.time():
        raise ValueError('Another actor owns this active shelf')
    expires=time.time()+args['minutes']*60
    seq=server.memory.append('hoenn_market_shelf_changed',dict(actor=actor,site=site,items=items,expires=expires,
        basis='authored_optional_native_retail_catalog',limits='No purchase, delivery, profit or original merchant agreement inferred. Already opened visits retain their frozen catalog.'))
    server.db.execute('INSERT OR REPLACE INTO hoenn_market_shelves VALUES(?,?,?,?,?)',(site,actor,seq,expires,json.dumps(items)))
    server.revision=seq
    return dict(outcome='shelf_opened' if items else 'shelf_closed',site=site,revision=seq,expires=expires,items=items)

def _legacy_wire(server,conn,raw):
    setup(server.db)
    if raw!=b'MK GET 1':return 'MK NONE\n'
    peer=conn.get('presence',{});state=peer.get('state')
    if not state or time.monotonic()-peer.get('state_time',0)>5:return 'MK NONE\n'
    pos=tuple(state[:2]);site=next((s for s,p in SITES.items() if p==pos),None)
    if not site or catalog_maps().get(pos,{}).get('name')!=site:return 'MK NONE\n'
    row=server.db.execute('SELECT expires,items FROM hoenn_market_shelves WHERE site=?',(site,)).fetchone()
    seconds=min(15,int(row[0]-time.time())) if row else 0
    if seconds<=0:return 'MK NONE\n'
    items=json.loads(row[1])
    return 'MK SHELF '+' '.join(map(str,[*pos,seconds,len(items),*items]))+'\n'


def wire(server,conn,raw):
    if raw==b'MK GET 1':return _legacy_wire(server,conn,raw)
    seq=0
    try:
        peer=conn.get('presence');state=peer.get('state') if peer else None
        if server.link_channels.get(conn['id']) is not conn or server.peers.get(conn['id']) is not peer:raise ValueError()
        if not state or not 0<=time.monotonic()-peer.get('state_time',0)<5:raise ValueError()
        if conn['id'] in server.link_protocol.sessions._locks or conn['id'] in server.link_protocol._encounters:raise ValueError()
        pos=tuple(state[:2]);site=next((s for s,p in SITES.items() if p==pos),None)
        if not site or catalog_maps().get(pos,{}).get('name')!=site:raise ValueError()
        setup(server.db)
        # This is a bounded witness of a shelf sent on this authenticated channel,
        # not a transferable item capability or proof of a durable private save.
        grants=conn.setdefault('market_report_shelves',{})
        now=time.monotonic()
        for rev in list(grants):
            if now-grants[rev]['at']>7200:del grants[rev]
        if raw==b'MK GET 2':
            row=server.db.execute('SELECT actor,revision,expires,items FROM hoenn_market_shelves WHERE site=?',(site,)).fetchone()
            seconds=min(15,int(row[2]-time.time())) if row else 0
            if seconds<=0:return 'MK NONE\n'
            actor,rev,_,encoded=row;items=json.loads(encoded)
            grants[rev]=dict(site=site,actor=actor,items=items,at=now)
            while len(grants)>16:del grants[min(grants,key=lambda r:grants[r]['at'])]
            return 'MK SHELF2 '+' '.join(map(str,[*pos,seconds,len(items),rev,*items]))+'\n'
        fields=raw.decode('ascii').split(' ')
        if len(fields)!=6 or fields[:2]!=['MK','BUY'] or any(not re.fullmatch('[1-9][0-9]{0,9}',v) for v in fields[2:]):raise ValueError()
        seq,revision,item,quantity=map(int,fields[2:])
        if seq>2**32-1 or seq<=conn.get('market_purchase_seq',0):raise ValueError()
        conn['market_purchase_seq']=seq
        grant=grants.get(revision)
        if not grant or grant['site']!=site or item not in grant['items'] or not 1<=quantity<=9999:raise ValueError()
        with server.db:
            receipt=server.memory.append('hoenn_market_purchase_reported',dict(site=site,actor=grant['actor'],shelf_revision=revision,item=item,quantity=quantity,basis='anonymous_native_client_report_after_item_credit_and_money_debit',limits='Not verified disk-save spending, revenue, delivery or finite shared supply. A modified client or later save rollback is not economically settled here.'))
            server.db.execute('INSERT INTO hoenn_market_reports VALUES(?,?,?,?,?,?)',(receipt,site,grant['actor'],revision,item,quantity))
        server.revision=receipt
        return f'MK RECORDED {seq}\n'
    except (ValueError,KeyError,UnicodeError,TypeError,sqlite3.Error):
        return 'MK NONE\n' if raw.startswith(b'MK GET') else f'MK UNCONFIRMED {seq}\n'
