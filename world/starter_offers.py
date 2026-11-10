"""Agent-authored optional fresh-save starter choices, never granted Pokemon."""
import hashlib,json,re
from pathlib import Path
SPECIES=json.loads(Path(__file__).with_name('starter_catalog.json').read_text())['species']
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS starter_offers(id TEXT PRIMARY KEY,actor TEXT,species TEXT,revision TEXT,active INTEGER)')
def catalog(server):
 setup(server.db)
 return [dict(id=i,actor=a,species=json.loads(s),revision=r) for i,a,s,r in server.db.execute('SELECT id,actor,species,revision FROM starter_offers WHERE active=1 ORDER BY id')]
def publish(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id','species'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']) or type(args['species']) is not str:raise ValueError('Use id and JSON three starter names')
 try:names=json.loads(args['species'])
 except ValueError:raise ValueError('Invalid starter JSON') from None
 if type(names) is not list or len(names)!=3 or any(type(n) is not str or n not in SPECIES for n in names) or len(set(names))!=3:raise ValueError('Choose three distinct names from starter catalog')
 encoded=json.dumps(names,separators=(',',':'));revision=hashlib.sha256(('starter1:'+encoded).encode()).hexdigest()[:16]
 old=server.db.execute('SELECT actor,species,active FROM starter_offers WHERE id=?',(args['id'],)).fetchone()
 if old and old[:2]!=(actor,encoded):raise ValueError('Offer identity is immutable; choose a new ID')
 if (not old or not old[2]) and len(catalog(server))>=32:raise ValueError('Close an offer before publishing more')
 server.db.execute('INSERT OR REPLACE INTO starter_offers VALUES(?,?,?,?,1)',(args['id'],actor,encoded,revision))
 return dict(outcome='optional_starter_offer_published',id=args['id'],revision=revision,species=names,limits='Fresh-save player must explicitly load and choose in native Birch UI. No starter grant, adoption, new story or rival-team change inferred.')
def close(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id'} or type(args['id']) is not str:raise ValueError('Use offer id')
 old=server.db.execute('SELECT actor FROM starter_offers WHERE id=?',(args['id'],)).fetchone()
 if not old or old[0]!=actor:raise ValueError('Only own offer may close')
 server.db.execute('UPDATE starter_offers SET active=0 WHERE id=?',(args['id'],))
 return dict(outcome='starter_offer_closed',id=args['id'],limits='Already armed/frozen/chosen personal selections are not revoked.')
def tool(server,actor,row,args):
 if set(args)!={'operation','value'}:raise ValueError('Use operation and value')
 if args['operation']=='inspect' and args['value']=='':return dict(outcome='starter_catalog',species=list(SPECIES),offers=catalog(server))
 if args['operation']=='close':return close(server,actor,row,dict(id=args['value']))
 if args['operation']=='publish' and type(args['value']) is str:
  try:value=json.loads(args['value'])
  except ValueError:raise ValueError('Use JSON {id,species:[three names]}') from None
  if type(value) is not dict or set(value)!={'id','species'}:raise ValueError('Use id and species')
  return publish(server,actor,row,dict(id=value['id'],species=json.dumps(value['species'])))
 raise ValueError('Use inspect, publish or close')
def handle(server,conn,raw):
 setup(server.db);seq=0
 try:
  f=raw.decode('ascii').split(' ')
  if len(f)!=5 or f[:2]!=['SO','GET'] or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
  seq=int(f[2])
  if seq>0xffffffff or not conn['presence'].get('campaign_run') or server.link_protocol.busy(conn['id']):raise ValueError()
  r=server.db.execute('SELECT species FROM starter_offers WHERE id=? AND revision=? AND active=1',(f[3],f[4])).fetchone()
  if not r:raise ValueError()
  return f'SO OFFER {seq} '+ ' '.join(str(SPECIES[n]) for n in json.loads(r[0]))+'\n'
 except (ValueError,KeyError,UnicodeError):return f'SO ERROR {seq}\n'
def command(server,conn,words):
 from .guilds import GuildError
 if not words:return ['Optional fresh-save starters: /guild starters page 0.','/starter load ID REV yes before Birch selection; vanilla otherwise. Rival teams/story unchanged.']
 if len(words)==2 and words[0]=='page' and words[1].isdigit() and len(words[1])<4:
  rows=catalog(server)[int(words[1])*3:int(words[1])*3+3]
  return [line for r in rows for line in (f"{r['id']} by {r['actor']}: {', '.join(r['species'])}",f"/starter load {r['id']} {r['revision']} yes")]+([] if rows else ['No starter offers.'])
 raise GuildError('Use /guild starters [page N]')
