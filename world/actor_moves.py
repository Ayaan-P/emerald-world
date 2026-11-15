"""Author requests for native level-up reminder, executed by the isolated host."""
import hashlib,json,re
from .character_training import source

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_move_requests(id TEXT PRIMARY KEY,actor TEXT,individual TEXT,version INTEGER,token TEXT,plan TEXT,args TEXT,result TEXT)')

def request(server,actor,row,args):
 from .actor_runtime import Pending
 if set(args) not in ({'individual'},{'individual','move','slot'}) or type(args['individual']) is not str:raise ValueError('Choose one owned individual')
 if 'move' in args and (type(args['move']) is not int or not 1<=args['move']<=65535 or type(args['slot']) is not int or not 0<=args['slot']<4):raise ValueError('Choose a native legal move and slot 0..3')
 current=source(server,actor,args['individual'])
 # Do not manufacture an initialized individual as a side effect of inspection.
 if not current['trained']:raise ValueError('Companion needs an existing reconciled full native state')
 _,_,plan,step=server.actor_tool_execution
 key=hashlib.sha256(json.dumps([server.memory.world_id,actor,plan['id'],step['id']],sort_keys=True).encode()).hexdigest()[:24]
 server.db.execute('INSERT INTO actor_move_requests VALUES(?,?,?,?,?,?,?,NULL)',(key,actor,args['individual'],current['version'],current['token'],plan['id'],json.dumps(args,sort_keys=True)))
 return Pending(dict(request=key),lambda:None)

def current_request(server,key):
 from .actor_practice import active
 row=server.db.execute('SELECT actor,individual,version,token,plan,args,result FROM actor_move_requests WHERE id=?',(key,)).fetchone()
 if not row:raise ValueError('Move request unavailable')
 if row[6]:return row
 if not active(server,row[0],row[2],row[4]) or source(server,row[0],row[1])['token']!=row[3]:raise ValueError('Move request changed')
 return row

def poll(server,actor,row,pending):
 value=current_request(server,pending['request'])
 if value[0]!=actor:raise ValueError('Wrong move request owner')
 return json.loads(value[6]) if value[6] else None

def tasks(server,actor):
 result=[]
 for key, in server.db.execute('SELECT id FROM actor_move_requests WHERE actor=? AND result IS NULL',(actor,)):
  try:row=current_request(server,key)
  except ValueError:continue
  result.append(dict(id=key,kind='moves',target=row[1],args=json.loads(row[5]),token=row[3]))
 return result

def finish(server,request):
 from .companion_moves import choices
 from .companion_practice import state
 if set(request)!={'command','request','engine','before','after','choices'}:raise ValueError('Invalid move receipt')
 row=current_request(server,request['request'])
 # Identical completion replay is idempotent, different replay is refused.
 fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
 if row[6]:
  prior=json.loads(row[6])
  if prior['receipt']!=fingerprint:raise ValueError('Move receipt changed')
  return dict(ok=True,result=prior)
 actor,individual=row[:2];current=source(server,actor,individual);saved=current['trained'];before=request['before'];after=request['after'];args=json.loads(row[5])
 if not saved or saved['engine']!=request['engine'] or saved['state']!=before:raise ValueError('Native source changed')
 available=choices(request['choices'])
 from pathlib import Path
 names=json.loads(Path(__file__).with_name('companion_move_names.json').read_text())['names']
 result=dict(outcome='native_move_choices',individual=individual,**available,names={str(m):names.get(str(m),'native move '+str(m)) for m in available['slots']+available['moves']},receipt=fingerprint)
 if 'move' in args:
  if args['move'] not in available['moves']:raise ValueError('Chosen move unavailable')
  if type(after) is not dict or set(after)!=set(before) or state('STATE1 '+' '.join(str(after[k]) for k in ('size','species','level','personality','owner','exp','blob')))!=after:raise ValueError('Full native result required')
  if any(after[k]!=before[k] for k in ('size','species','level','personality','owner','exp')):raise ValueError('Native move receipt changed growth or identity')
  result=dict(outcome='move_reconciled',individual=individual,move=args['move'],slot=args['slot'],receipt=fingerprint)
 elif after is not None:raise ValueError('Inspection cannot alter companion')
 with server.db:
  if 'move' in args:
   server.db.execute('UPDATE character_training SET state=? WHERE actor=? AND individual=?',(json.dumps(after,sort_keys=True),actor,individual))
   seq=server.memory.append('character_move_learned',dict(character_id=actor,individual=individual,move=args['move'],slot=args['slot'],basis='trusted_isolated_native_level_up_reminder'))
   server.revision=seq;result['world_receipt']=seq
  server.db.execute('UPDATE actor_move_requests SET result=? WHERE id=?',(json.dumps(result,sort_keys=True),request['request']))
 return dict(ok=True,result=result)


def fail(server,request):
 if set(request)!={'command','request'}:raise ValueError('Invalid failed move request')
 row=current_request(server,request['request'])
 if row[6]:return dict(ok=True,result=json.loads(row[6]))
 result=dict(outcome='native_move_failed',individual=row[1],basis='host_executor_failure_no_world_change')
 with server.db:server.db.execute('UPDATE actor_move_requests SET result=? WHERE id=?',(json.dumps(result,sort_keys=True),request['request']))
 return dict(ok=True,result=result)
