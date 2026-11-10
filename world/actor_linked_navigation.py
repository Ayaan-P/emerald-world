"""Durable destination routing over real cave links and existing movement executors."""
from collections import deque
import hashlib,json
from .characters import records
from .cave_links import destination
from . import actor_navigation,actor_cave_travel

def graph(server):
 if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='cave_links'").fetchone():return []
 result=[]
 for identity,source,place,target in server.db.execute('SELECT object,source,place,destination FROM cave_links ORDER BY object'):
  prop=next((o for o in server.objects if o['id']==identity),None)
  if not prop or prop.get('kind')!='prop' or prop.get('portable') or prop.get('region_revision')!=source:continue
  try:destination(server,place,target)
  except ValueError:continue
  source_place=server.db.execute('SELECT place_id FROM world_region_revisions WHERE revision=?',(source,)).fetchone()
  if not source_place:continue
  try:destination(server,source_place[0],source)
  except ValueError:continue
  from .passage_lifecycle import status
  lifecycle=status(server,identity)
  if not lifecycle['enabled']:continue
  edge=dict(object=identity,source=source,place=place,destination=target)
  if lifecycle['revision']:edge['passage_revision']=lifecycle['revision']
  result.append(edge)
 return result

def route(server,source,target):
 edges=graph(server);queue=deque([source]);paths={source:[]}
 while queue:
  at=queue.popleft()
  if at==target:return paths[at]
  for edge in edges:
   if edge['source']!=at or edge['destination'] in paths:continue
   paths[edge['destination']]=paths[at]+[edge];queue.append(edge['destination'])
 raise ValueError('No installed directed cave-link route to this destination')

def save(server,identity,data):
 server.db.execute('UPDATE actor_linked_journeys SET data=? WHERE id=?',(json.dumps(data,sort_keys=True),identity))

def start(server,actor,row,args):
 from .actor_runtime import Pending
 if set(args)!={'place','revision','x','y'} or any(type(args[k]) is not int for k in ('x','y')):raise ValueError('Supply exact destination place/revision and integer x/y')
 cave=destination(server,args['place'],args['revision'])
 if not cave.walkable(args['x'],args['y']) or (args['x'],args['y']) in ((1,1),(29,29),(29,28)):raise ValueError('Choose a walkable non-warp destination')
 obj=next((o for o in server.objects if o['id']==actor),None)
 if not obj or not obj.get('region_revision'):raise ValueError('Actor must occupy a supported generated cave')
 execution=server.actor_tool_execution
 if not execution or execution[0]!=actor:raise ValueError('Durable capability execution required')
 identity=hashlib.sha256(json.dumps([actor,execution[2]['id'],execution[3]['id']],sort_keys=True).encode()).hexdigest()
 edges=route(server,obj['region_revision'],cave.identity)
 server.db.execute('CREATE TABLE IF NOT EXISTS actor_linked_journeys(id TEXT PRIMARY KEY,actor TEXT,data TEXT)')
 data=dict(target=args,edges=edges,index=0,active=None,completed=[],expected=dict(revision=obj['region_revision'],x=obj['x'],y=obj['y'],version=records(server.module_state)[actor]['version']))
 server.db.execute('INSERT INTO actor_linked_journeys VALUES(?,?,?)',(identity,actor,json.dumps(data,sort_keys=True)))
 return Pending(dict(journey=identity),lambda:None)

def poll(server,actor,row,pending):
 found=server.db.execute('SELECT actor,data FROM actor_linked_journeys WHERE id=?',(pending['journey'],)).fetchone()
 if not found or found[0]!=actor:raise ValueError('Unknown linked journey')
 data=json.loads(found[1]);obj=next((o for o in server.objects if o['id']==actor),None);current=records(server.module_state).get(actor,{})
 if not obj or current.get('status')!='active':raise ValueError('Actor unavailable; journey interrupted')
 if data['active']:
  active=data['active']
  result=(actor_navigation.poll if active['kind']=='navigate' else actor_cave_travel.poll)(server,actor,row,active['pending'])
  if result is None:return None
  if active['kind']=='navigate' and (obj.get('region_revision')!=result['revision'] or [obj['x'],obj['y']]!=[result['x'],result['y']]):raise ValueError('Actor left the completed leg; inspect and replan')
  data['completed'].append(dict(kind=active['kind'],result=result))
  if active['kind']=='traverse':data['index']+=1
  data['active']=None
  data['expected']=dict(revision=obj['region_revision'],x=obj['x'],y=obj['y'],version=current['version'])
  save(server,pending['journey'],data)
  return None
 if data['expected']!=dict(revision=obj.get('region_revision'),x=obj['x'],y=obj['y'],version=current['version']):
  raise ValueError('Actor moved or changed outside this journey; inspect and replan')
 target=data['target'];destination(server,target['place'],target['revision'])
 if data['index']<len(data['edges']):
  edge=data['edges'][data['index']]
  if edge not in graph(server) or obj['region_revision']!=edge['source']:raise ValueError('Route link changed; inspect and replan')
  prop=next(o for o in server.objects if o['id']==edge['object'])
  if abs(obj['x']-prop['x'])+abs(obj['y']-prop['y'])==1:
   from .passage_lifecycle import program_revision
   operation=actor_cave_travel.traverse(server,actor,row,dict(object=prop['id'],revision=program_revision(server,prop)))
   kind='traverse'
  else:
   paths=[]
   for x,y in ((prop['x']-1,prop['y']),(prop['x']+1,prop['y']),(prop['x'],prop['y']-1),(prop['x'],prop['y']+1)):
    try:paths.append(actor_navigation.route(server,actor,[x,y],edge['source'])[2])
    except ValueError:continue
   if not paths:raise ValueError('No current path to next link; inspect and replan')
   path=min(paths,key=lambda p:(len(p),p[-1]));operation=actor_navigation.stage(server,actor,current,obj,path,edge['source']);kind='navigate'
 else:
  if obj['region_revision']!=target['revision']:raise ValueError('Journey destination scope changed')
  if [obj['x'],obj['y']]==[target['x'],target['y']]:
   return dict(outcome='authority_multiplace_arrival',place=target['place'],revision=target['revision'],x=obj['x'],y=obj['y'],
       completed_legs=data['completed'],limits='Committed authority movement and cave-link transitions, not rendered animation or player travel.')
  operation=actor_navigation.start(server,actor,row,dict(revision=target['revision'],x=target['x'],y=target['y']));kind='navigate'
 data['active']=dict(kind=kind,pending=operation.data);save(server,pending['journey'],data)
 operation.dispatch()
 return None
