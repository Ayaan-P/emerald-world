"""Public design metadata; private stock placement and inventory stay native."""
import json,re
from pathlib import Path
CATALOG=json.loads(Path(__file__).with_name('floorplan_catalog.json').read_text())
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS floorplans(id TEXT PRIMARY KEY,actor TEXT,document TEXT,revision INTEGER,active INTEGER)')
def catalog(server):
 setup(server.db)
 return dict(layouts=CATALOG['layouts'],decorations=CATALOG['decorations'],plans=[dict(id=i,actor=a,revision=r,**json.loads(d)) for i,a,d,r in server.db.execute('SELECT id,actor,document,revision FROM floorplans WHERE active=1 ORDER BY id')],limits='Public suggestions only. Players choose existing owned furniture and approve ordinary native placements. No inventory, base layout, party, build outcome or sharing is inferred. Native collision/surface rules may reject proposals.')
def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id','design'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']) or type(args['design']) is not str or len(args['design'])>3000:raise ValueError('Use a lowercase id and bounded JSON design, or empty design to close')
 old=server.db.execute('SELECT actor,document,active FROM floorplans WHERE id=?',(args['id'],)).fetchone()
 if old and old[0]!=actor:raise ValueError('Another author owns this design')
 if not args['design']:
  if not old:raise ValueError('Unknown design')
  active=0;encoded=old[1]
 else:
  d=json.loads(args['design'])
  if type(d) is not dict or set(d)!={'title','layout','placements'} or type(d['title']) is not str or not re.fullmatch('[A-Za-z0-9 ,.!?-]{1,40}',d['title']) or type(d['layout']) is not str or d['layout'] not in CATALOG['layouts']:raise ValueError('Reviewed layout and bounded title required')
  if type(d['placements']) is not list or not 1<=len(d['placements'])<=16:raise ValueError('Choose 1..16 ordered placements')
  seen=set();layout=CATALOG['layouts'][d['layout']]
  for p in d['placements']:
   if type(p) is not list or len(p)!=3 or any(type(v) is not int for v in p):raise ValueError('Each placement is [decoration_id,x,y], native bottom-left anchor')
   item,x,y=p;decor=CATALOG['decorations'].get(str(item))
   if not decor or not 0<=x<16 or not 0<=y<16 or x+decor['width']>layout['width'] or y+1<decor['height'] or y>=layout['height'] or tuple(p) in seen:raise ValueError('Invalid, duplicate or out-of-layout placement')
   seen.add(tuple(p))
  encoded=json.dumps(d,sort_keys=True,separators=(',',':'));active=1
  if old and old[1]!=encoded:raise ValueError('Design identity is immutable; publish a new id')
  if not old or not old[2]:
   if server.db.execute('SELECT COUNT(*) FROM floorplans WHERE active=1').fetchone()[0]>=128 or server.db.execute('SELECT COUNT(*) FROM floorplans WHERE active=1 AND actor=?',(actor,)).fetchone()[0]>=16:raise ValueError('Active design capacity reached; close a prior design')
 seq=server.memory.append('floorplan_published' if active else 'floorplan_closed',dict(character_id=actor,id=args['id'],basis='design_metadata_only',limits='No owned furniture, placement, completion or player base sharing inferred'))
 server.db.execute('INSERT INTO floorplans VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,active=excluded.active',(args['id'],actor,encoded,seq,active));server.revision=seq
 return dict(outcome='floorplan_published' if active else 'floorplan_closed',id=args['id'],revision=seq)
def handle(server,channel,raw):
 seq=0
 try:
  conn=channel['presence']
  if server.link_channels.get(channel['id']) is not channel or server.peers.get(channel['id']) is not conn or conn.get('closing'):raise ValueError()
  f=raw.decode('ascii').split()
  if len(f)!=4 or f[:2]!=['FP','GET'] or not re.fullmatch('[1-9][0-9]{0,9}',f[2]) or int(f[2])>0xffffffff or not re.fullmatch('[a-z][a-z0-9_]{0,23}',f[3]):raise ValueError()
  seq=int(f[2])
  if server.link_protocol.busy(conn['id']):raise ValueError()
  setup(server.db);row=server.db.execute('SELECT document FROM floorplans WHERE id=? AND active=1',(f[3],)).fetchone()
  if not row:raise ValueError()
  d=json.loads(row[0]);packed=''.join(bytes(p).hex() for p in d['placements'])
  return f"FP PLAN {seq} {d['layout']} {packed}\n"
 except (ValueError,KeyError,UnicodeError):return f'FP FAIL {seq}\n'
def command(server,conn,words):
 from .guilds import GuildError
 if len(words)>1 or words and (not words[0].isascii() or not words[0].isdigit() or not 0<=int(words[0])<100):raise GuildError('Use /guild floorplans [page], starting at 0')
 page=int(words[0]) if words else 0;plans=catalog(server)['plans'];lines=['Public floorplans, not free furniture. Native inventory stays private.']
 for p in plans[page*3:page*3+3]:lines.extend([p['id']+': '+p['title'],p['layout']+'; '+str(len(p['placements']))+' placements','In your matching own base: /floorplan '+p['id']])
 return lines+['Choose furniture normally at your PC. SELECT guides; A still asks to place.']
