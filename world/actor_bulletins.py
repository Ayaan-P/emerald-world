"""Attributed shared-world TV reports, never fabricated authoritative news."""
import json,re,time

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_bulletins(actor TEXT PRIMARY KEY,seq INTEGER,expires REAL,pages TEXT)')

def publish(server,actor,row,args):
 from .actor_runtime import actor_records
 setup(server.db)
 if set(args)!={'pages','evidence','hours'} or type(args['pages']) is not str or type(args['evidence']) is not str or type(args['hours']) is not int or not 1<=args['hours']<=24:raise ValueError('Supply two text pages, actual public evidence sequence IDs and duration 1..24 hours')
 try:pages=json.loads(args['pages']);evidence=json.loads(args['evidence'])
 except ValueError:raise ValueError('Invalid bulletin JSON')
 if type(pages) is not list or len(pages)!=2 or any(type(p) is not str or not 1<=len(p.split('\n'))<=2 or any(not 1<=len(line)<=28 for line in p.split('\n')) or not re.fullmatch("[A-Za-z0-9 .,!?'\\n-]+",p) for p in pages):raise ValueError('Two literal pages, up to two 28-character lines each')
 if type(evidence) is not list or not 1<=len(evidence)<=4 or any(type(n) is not int or n<1 for n in evidence) or len(set(evidence))!=len(evidence):raise ValueError('One to four distinct public event references required')
 for seq in evidence:
  if not server.db.execute("SELECT 1 FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone():raise ValueError('Only committed public world history may support a broadcast')
 current=actor_records(server).get(actor)
 if not current:raise ValueError('Existing author character required')
 name=current.get('name',actor)
 name=re.sub("[^A-Za-z0-9 .,!?'-]",'',name)[:28] or 'World character'
 expires=time.time()+args['hours']*3600
 seq=server.memory.append('character_bulletin_published',dict(character_id=actor,pages=pages,source_events=evidence,expires=expires,basis='attributed_character_report',limits='Character-authored interpretation of referenced public records, not independently verified facts or observed outcomes.'))
 server.db.execute('INSERT INTO actor_bulletins VALUES(?,?,?,?) ON CONFLICT(actor) DO UPDATE SET seq=excluded.seq,expires=excluded.expires,pages=excluded.pages',(actor,seq,expires,json.dumps(['Report by\n'+name,*pages])))
 server.revision=seq
 return dict(outcome='world_bulletin_published',bulletin=seq,expires=expires,limits='Available to compatible players at ordinary TVs; no forced announcement, view receipt or change to story news.')

def withdraw(server,actor,row,args):
 if args:raise ValueError('Withdraw takes no arguments')
 setup(server.db)
 changed=server.db.execute('DELETE FROM actor_bulletins WHERE actor=?',(actor,)).rowcount
 return dict(outcome='world_bulletin_withdrawn' if changed else 'no_active_bulletin')

def line(server,conn):
 if not conn.get('world_bulletin_capable'):return None
 setup(server.db)
 from .actor_runtime import actor_records
 actors=actor_records(server)
 for actor,seq,raw in server.db.execute('SELECT actor,seq,pages FROM actor_bulletins WHERE expires>? ORDER BY seq DESC',(time.time(),)):
  if actor in actors:
   return 'WORLD_BULLETIN '+' '.join([str(seq),*[p.encode('ascii').hex() for p in json.loads(raw)]])
 return None
