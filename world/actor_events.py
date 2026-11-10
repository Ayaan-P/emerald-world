"""One-shot durable public-log subscriptions for composable actor plans."""
import hashlib,json,re

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_event_waits(id TEXT PRIMARY KEY,actor TEXT,cursor INTEGER,event TEXT,filters TEXT)')

def start(server,actor,row,args):
 from .actor_runtime import Pending
 if set(args)!={'event','where'} or type(args['event']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,63}',args['event']) or type(args['where']) is not str or len(args['where'])>600:raise ValueError('Supply an event type and bounded JSON exact-field filters')
 try:filters=json.loads(args['where'])
 except ValueError:raise ValueError('Invalid event filters')
 if type(filters) is not dict or len(filters)>4 or any(not re.fullmatch('[a-z][a-z0-9_]{0,63}',k) or type(v) not in (str,int,bool) or (type(v) is str and len(v)>128) for k,v in filters.items()):raise ValueError('Use up to four public top-level scalar equality filters')
 setup(server.db)
 _,_,plan,step=server.actor_tool_execution
 key=hashlib.sha256(json.dumps([server.memory.world_id,actor,plan['id'],step['id']]).encode()).hexdigest()
 cursor=server.memory.history(limit=1)['through']
 server.db.execute('INSERT INTO actor_event_waits VALUES(?,?,?,?,?)',(key,actor,cursor,args['event'],json.dumps(filters,sort_keys=True)))
 return Pending(dict(wait=key),lambda:None)

def poll(server,actor,row,pending):
 setup(server.db)
 saved=server.db.execute('SELECT actor,cursor,event,filters FROM actor_event_waits WHERE id=?',(pending['wait'],)).fetchone()
 if not saved or saved[0]!=actor:raise ValueError('Public event subscription unavailable')
 _,cursor,kind,encoded=saved;filters=json.loads(encoded)
 # Bounded scan per authority tick; cursor commits even when no match, avoiding
 # repeated scanning and loss in a busy world. Never reads private event kinds.
 page=server.memory.history(after=cursor,limit=64)
 for event in page['events']:
  if event.get('event')!=kind or any(type(event.get(k)) is not type(v) or event.get(k)!=v for k,v in filters.items()):continue
  result=dict(outcome='committed_public_event',event_seq=event['seq'],payload=event,
              semantics='Public authority record only, not personal observation, consent or proof of unrecorded activity.')
  for key,value in event.items():
   if type(value) in (str,int):result['event_'+key]=value
  return result
 server.db.execute('UPDATE actor_event_waits SET cursor=? WHERE id=?',(page['cursor'],pending['wait']))
 return None
