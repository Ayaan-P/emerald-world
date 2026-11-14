"""Actual native feeder deposits leave bounded public scents; never shared Pokémon/items."""
import json,re,time
from pathlib import Path

def sites():return {e['id']:e for e in json.loads(Path(__file__).with_name('safari_feeders.json').read_text())['entries']}
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS safari_feeder_scents(site INTEGER PRIMARY KEY,block TEXT NOT NULL,expires REAL NOT NULL,revision INTEGER NOT NULL)')
def catalog(server):
 setup(server.db);places=sites()
 return dict(active=[dict(site=places[i],flavors=list(bytes.fromhex(b))[1:6],expires=e,receipt=r) for i,b,e,r in server.db.execute('SELECT site,block,expires,revision FROM safari_feeder_scents WHERE expires>? ORDER BY site',(time.time(),)) if i in places],basis='anonymous_native_client_report_of_real_feeder_deposit',limits='10-minute public scent configuration. Native feeder nature bias, not species migration, caught individuals, catch probability, shared inventory or proof of disk-save durability. Personal native feeder result takes priority.')
def handle(server,conn,raw):
 seq=0
 try:
  f=raw.decode('ascii').split(' ')
  if len(f) not in (4,5) or f[0]!='SF' or f[1] not in ('GET','PUT') or any(not re.fullmatch('[1-9][0-9]{0,9}',s) for s in f[2:4]):raise ValueError()
  seq,site=map(int,f[2:4]);peer=conn.get('presence');state=peer.get('state') if peer else None;now=time.monotonic()
  if seq>2**32-1 or seq<=conn.get('safari_feeder_seq',0) or server.link_channels.get(conn['id']) is not conn or server.peers.get(conn['id']) is not peer:raise ValueError()
  conn['safari_feeder_seq']=seq
  if not state or not state[6] or not 0<=now-peer.get('state_time',0)<3:raise ValueError()
  if conn['id'] in server.link_protocol.sessions._locks or conn['id'] in server.link_protocol._encounters:raise ValueError()
  target=sites().get(site)
  if not target or tuple(state[:2])!=(target['group'],target['num']):raise ValueError()
  dx=target['x']-state[2];dy=target['y']-state[3]
  setup(server.db)
  if f[1]=='GET' and len(f)==4:
   if abs(dx)+abs(dy)>5:raise ValueError()
   row=server.db.execute('SELECT block,expires FROM safari_feeder_scents WHERE site=?',(site,)).fetchone()
   if not row or int(row[1]-time.time())<1:return f'SF NONE {seq}\n'
   return f'SF SCENT {seq} {site} {row[0]} {max(1,min(600,int(row[1]-time.time())))}\n'
  if f[1]!='PUT' or len(f)!=5 or not re.fullmatch('[0-9a-f]{14}',f[4]) or not 1<=int(f[4][:2],16)<=14:raise ValueError()
  if (dx,dy)!={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(state[4]):raise ValueError()
  expires=time.time()+600
  with server.db:
   receipt=server.memory.append('safari_feeder_deposit_shared',dict(site=site,map=target['map'],x=target['x'],y=target['y'],flavors=list(bytes.fromhex(f[4]))[1:6],expires=expires,basis='consenting_native_client_report_after_item_clear',limits='Anonymous deposit report, not a verified durable inventory debit, catch, species population or guarantee of an encountered nature.'))
   server.db.execute('INSERT OR REPLACE INTO safari_feeder_scents VALUES(?,?,?,?)',(site,f[4],expires,receipt))
  server.revision=receipt
  return f'SF STORED {seq}\n'
 except (ValueError,KeyError,UnicodeError,TypeError):return f'SF FAIL {seq}\n'
