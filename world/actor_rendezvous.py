"""Seek a persistent world character through actual geometry and installed links."""
import hashlib,json
from .characters import records
from . import actor_navigation as navigation,actor_cave_travel as travel
from .actor_linked_navigation import route as linked_route

def actors(server,actor,target):
 rows=records(server.module_state);objects={o['id']:o for o in server.objects}
 if actor==target or any(rows.get(k,{}).get('status')!='active' or k not in objects or not objects[k].get('region_revision') for k in (actor,target)):raise ValueError('Two active generated-world characters required; canonical actors are not relocated')
 return rows[actor],objects[actor],rows[target],objects[target]

def start(server,actor,row,args):
 from .actor_runtime import Pending
 if set(args)!={'target'} or type(args['target']) is not str:raise ValueError('Choose a persistent world character ID')
 actors(server,actor,args['target'])
 _,_,plan,step=server.actor_tool_execution
 key=hashlib.sha256(json.dumps([actor,plan['id'],step['id']]).encode()).hexdigest()
 server.db.execute('CREATE TABLE IF NOT EXISTS actor_rendezvous(id TEXT PRIMARY KEY,actor TEXT,data TEXT)')
 server.db.execute('INSERT INTO actor_rendezvous VALUES(?,?,?)',(key,actor,json.dumps(dict(target=args['target'],active=None,legs=[],expected=None))))
 return Pending(dict(rendezvous=key),lambda:None)

def poll(server,actor,row,pending):
 found=server.db.execute('SELECT actor,data FROM actor_rendezvous WHERE id=?',(pending['rendezvous'],)).fetchone()
 if not found or found[0]!=actor:raise ValueError('Rendezvous unavailable')
 data=json.loads(found[1]);current,obj,target,other=actors(server,actor,data['target'])
 def position():return [obj['region_revision'],obj['x'],obj['y'],current['version']]
 def save():server.db.execute('UPDATE actor_rendezvous SET data=? WHERE id=?',(json.dumps(data,sort_keys=True),pending['rendezvous']))
 if data['active']:
  active=data['active'];result=(navigation.poll if active['kind']=='navigate' else travel.poll)(server,actor,row,active['pending'])
  if result is None:return None
  if active['kind']=='navigate' and (obj['region_revision']!=result['revision'] or [obj['x'],obj['y']]!=[result['x'],result['y']]):raise ValueError('Actor left completed leg; inspect and replan')
  data['legs'].append(dict(kind=active['kind'],result=result));data['active']=None;data['expected']=position();save();return None
 if data['expected'] is not None and data['expected']!=position():raise ValueError('Actor changed outside rendezvous; inspect and replan')
 from .character_walks import walking
 if any(p.get('character_pending',{}).get('id') in (actor,data['target']) for p in server.peers.values() if type(p.get('character_pending')) is dict):return None
 same=all(obj.get(k)==other.get(k) for k in ('group','num','region_revision'))
 if same and abs(obj['x']-other['x'])+abs(obj['y']-other['y'])==1 and not walking(server.module_state,actor) and not walking(server.module_state,data['target']):
  return dict(outcome='authority_rendezvous',target=data['target'],target_version=target['version'],revision=obj['region_revision'],x=obj['x'],y=obj['y'],target_x=other['x'],target_y=other['y'],legs=data['legs'],limits='Actual adjacent idle authority objects; no recipient agreement, conversation or rendered claim. Use current version for a separate voluntary interaction.')
 if len(data['legs'])>=16:raise ValueError('Target pursuit exceeded sixteen completed legs; choose a fresh plan, no meeting asserted')
 if same:
  destination=other;revision=obj['region_revision']
 else:
  edges=linked_route(server,obj['region_revision'],other['region_revision'])
  destination=next(o for o in server.objects if o['id']==edges[0]['object']);revision=obj['region_revision']
  if abs(obj['x']-destination['x'])+abs(obj['y']-destination['y'])==1:
   from .passage_lifecycle import program_revision
   operation=travel.traverse(server,actor,row,dict(object=destination['id'],revision=program_revision(server,destination)))
   data['active']=dict(kind='traverse',pending=operation.data);save();operation.dispatch();return None
 # If already beside a moving recipient, let it finish its real movement before
 # choosing a new path. No freezing, forced dialogue or remote meeting.
 if same and abs(obj['x']-other['x'])+abs(obj['y']-other['y'])==1:return None
 paths=[]
 for x,y in ((destination['x']-1,destination['y']),(destination['x']+1,destination['y']),(destination['x'],destination['y']-1),(destination['x'],destination['y']+1)):
  try:paths.append(navigation.route(server,actor,[x,y],revision)[2])
  except ValueError:continue
 if not paths:raise ValueError('No current reachable adjacent tile; no meeting asserted')
 path=min(paths,key=lambda p:(len(p),p[-1]));operation=navigation.stage(server,actor,current,obj,path,revision)
 data['active']=dict(kind='navigate',pending=operation.data);save();operation.dispatch();return None
