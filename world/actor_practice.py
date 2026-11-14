"""Durable requests, never an in-author native executor or fabricated exercise."""
import hashlib,json

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_practice_requests(id TEXT PRIMARY KEY,actor TEXT,individual TEXT,version INTEGER,token TEXT,plan TEXT,result TEXT)')

def request(server,actor,row,args):
 from .actor_runtime import Pending
 from .character_training import source
 if set(args)!={'individual'} or type(args['individual']) is not str:raise ValueError('Choose an identified on-team companion')
 current=source(server,actor,args['individual'])
 _,_,plan,step=server.actor_tool_execution
 key=hashlib.sha256(json.dumps([server.memory.world_id,actor,plan['id'],step['id']],sort_keys=True).encode()).hexdigest()[:24]
 server.db.execute('INSERT INTO actor_practice_requests VALUES(?,?,?,?,?,?,NULL)',(key,actor,args['individual'],current['version'],current['token'],plan['id']))
 return Pending(dict(request=key),lambda:None)

def active(server,actor,version,plan):
 from .actor_runtime import actor_records
 row=actor_records(server).get(actor,{})
 return row.get('version')==version and (row.get('plan') or {}).get('id')==plan

def poll(server,actor,row,pending):
 saved=server.db.execute('SELECT actor,individual,version,token,plan,result FROM actor_practice_requests WHERE id=?',(pending['request'],)).fetchone()
 if not saved or saved[0]!=actor:raise ValueError('Practice request unavailable')
 if saved[5]:return json.loads(saved[5])
 from .character_training import source
 if not active(server,actor,saved[2],saved[4]) or source(server,actor,saved[1])['token']!=saved[3]:raise ValueError('Practice source changed; no completion asserted')
 return None

def tasks(server,actor):
 from .character_training import source
 result=[]
 for key,individual,version,token,plan in server.db.execute('SELECT id,individual,version,token,plan FROM actor_practice_requests WHERE actor=? AND result IS NULL',(actor,)):
  if not active(server,actor,version,plan):continue
  try:
   if source(server,actor,individual)['token']!=token:continue
  except ValueError:continue
  result.append(dict(id=key,kind='practice',target=individual,capability_request=key))
 return result
