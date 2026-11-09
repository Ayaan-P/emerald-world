"""Trusted local-host practice reconciliation for world-owned recurring NPCs.
No player-result packet, author text or canonical story party grants growth.
"""
import hashlib,json,re
from .companion_practice import state as parse_state

def setup(db):
 from .actor_practice import setup as request_setup
 request_setup(db)
 db.executescript('''CREATE TABLE IF NOT EXISTS character_training(actor TEXT,individual TEXT,engine TEXT,authored_level INTEGER,state TEXT,PRIMARY KEY(actor,individual));
 CREATE TABLE IF NOT EXISTS character_training_receipts(job TEXT PRIMARY KEY,actor TEXT,individual TEXT,seq INTEGER,fingerprint TEXT);''')

def saved(db,actor,individual):
 row=db.execute('SELECT engine,authored_level,state FROM character_training WHERE actor=? AND individual=?',(actor,individual)).fetchone()
 return dict(engine=row[0],authored_level=row[1],state=json.loads(row[2])) if row else None

def source(server,actor,individual):
 from .characters import records
 c=records(server.module_state).get(actor)
 if not c:raise ValueError('Only existing world-owned dynamic characters support reconciled practice')
 mon=next((m for m in c['team'] if m.get('individual')==individual),None)
 if not mon:raise ValueError('Companion is not on this character team')
 identity=server.db.execute('SELECT species,personality,owner FROM character_companions WHERE actor=? AND individual=?',(actor,individual)).fetchone()
 from .companion_exchange import owned
 if identity is None or not owned(server.db,actor,individual):raise ValueError('Companion has no owned durable identity')
 result=dict(world_id=server.memory.world_id,actor=actor,individual=individual,version=c['version'],
             species=identity[0],personality=identity[1],owner=identity[2],authored_level=mon['level'],trained=saved(server.db,actor,individual))
 result['token']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
 return result

def reconcile(server,request):
 if set(request)-{'capability_request'}!={'command','actor','individual','token','job','engine','before','after','steps','cap'}:raise ValueError('Invalid practice receipt fields')
 fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
 prior_receipt=server.db.execute('SELECT seq,fingerprint FROM character_training_receipts WHERE job=?',(request['job'],)).fetchone()
 if prior_receipt:
  if prior_receipt[1]!=fingerprint:raise ValueError('Job identity reused with different receipt')
  return dict(ok=True,seq=prior_receipt[0],already_applied=True)
 actor,individual=request['actor'],request['individual'];current=source(server,actor,individual)
 capability=request.get('capability_request')
 if capability is not None:
  from .actor_practice import active
  pending=server.db.execute('SELECT actor,individual,version,token,plan,result FROM actor_practice_requests WHERE id=?',(capability,)).fetchone()
  if not pending or pending[:2]!=(actor,individual) or pending[3]!=request['token'] or pending[5] is not None or not active(server,actor,pending[2],pending[4]):raise ValueError('Practice request withdrawn or changed')
 if current['token']!=request['token']:raise ValueError('Companion source changed; receipt is stale')
 if not re.fullmatch('[0-9a-f]{32}',request['job']) or not re.fullmatch('[0-9a-f]{64}',request['engine']):raise ValueError('Invalid host job identity')
 before,after=request['before'],request['after']
 for value in (before,after):
  if type(value) is not dict or set(value)!={'size','species','level','personality','owner','exp','blob'}:raise ValueError('Full native state required')
  if parse_state('STATE1 '+' '.join(str(value[k]) for k in ('size','species','level','personality','owner','exp','blob')))!=value:raise ValueError('Invalid full state')
  if value['size']!=100 or any(value[k]!=current[k] for k in ('species','personality','owner')):raise ValueError('Wrong native companion identity or ABI')
 prior=current['trained']
 if prior:
  if prior['engine']!=request['engine'] or prior['state']!=before:raise ValueError('Native engine or prior full state changed')
 elif before['level']!=current['authored_level']:raise ValueError('Initial practice must start at authored baseline')
 if (type(request['steps']) is not int or not 1<=request['steps']<=1024 or type(request['cap']) is not int
     or not before['level']<=after['level']<=request['cap']<=100 or not before['exp']<after['exp']<=before['exp']+request['steps']):raise ValueError('Practice exceeds frozen exercise budget')
 with server.db:
  if server.db.execute('SELECT 1 FROM character_training_receipts WHERE job=?',(request['job'],)).fetchone():raise ValueError('Practice receipt already applied')
  server.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?) ON CONFLICT(actor,individual) DO UPDATE SET engine=excluded.engine,authored_level=excluded.authored_level,state=excluded.state',
     (actor,individual,request['engine'],current['authored_level'],json.dumps(after,sort_keys=True)))
  seq=server.memory.append('character_practice_completed',dict(character_id=actor,individual=individual,character_version=current['version'],
       job=request['job'],before_level=before['level'],after_level=after['level'],exp_added=after['exp']-before['exp'],
       simulated_steps=request['steps'],publication='public_fictional_character_practice',basis='trusted_local_host_native_receipt'))
  if capability is not None:
   result=dict(outcome='practice_reconciled',individual=individual,job=request['job'],world_receipt=seq,before_level=before['level'],after_level=after['level'],exp_added=after['exp']-before['exp'],basis='trusted_isolated_native_practice_not_battle_victory')
   server.db.execute('UPDATE actor_practice_requests SET result=? WHERE id=?',(json.dumps(result,sort_keys=True),capability))
  server.db.execute('INSERT INTO character_training_receipts VALUES(?,?,?,?,?)',(request['job'],actor,individual,seq,fingerprint));server.revision=seq
 return dict(ok=True,seq=seq)

def battle_values(server,actor,team):
 result=[];trained=False
 for mon in team:
  current=source(server,actor,mon['individual']);saved_state=current['trained'];s=saved_state['state'] if saved_state else None
  result.extend((mon['species'],s['level'] if s else mon['level'],current['personality'],current['owner'],s['blob'] if s else '-'))
  trained=trained or s is not None
 return result if trained else None


def intentions(server):
 from .canonical_cast import records as canonical
 from .characters import records
 actors={key:dict(version=row['version'],binding='canonical',intentions=[t for t in row.get('intentions',[]) if t['kind']=='practice']) for key,row in canonical(server.module_state).items()}
 actors.update({key:dict(version=row['version'],binding='world_character',intentions=row.get('intentions',[])) for key,row in records(server.module_state).items() if row['status']!='retired'})
 from .actor_practice import tasks
 for actor,row in actors.items():
  if row['binding']=='world_character':row['intentions']=list(row['intentions'])+tasks(server,actor)
 return dict(ok=True,world_id=server.memory.world_id,actors=actors)
