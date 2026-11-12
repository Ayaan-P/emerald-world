"""Authority-owned NPC traversal of existing physical cave links, not player warps."""
import copy,hashlib,json
from .characters import records
from .character_walks import walking

def observed_link(server,obj):
 if not server.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cave_links'").fetchone():return None
 link=server.db.execute('SELECT source,place,destination FROM cave_links WHERE object=?',(obj['id'],)).fetchone()
 if not link or link[0]!=obj.get('region_revision'):return None
 from .passage_lifecycle import status
 if not status(server,obj['id'])['enabled']:return None
 return dict(place=link[1],destination=link[2],operation='world.traverse_link')

def traverse(server,actor,row,args):
 from .actor_runtime import Pending
 from .passage_lifecycle import program_revision
 from .cave_links import destination
 from .region_characters import validate_region_objects
 from .character_actions import compile_actions
 if set(args)!={'object','revision'}:raise ValueError('Choose an observed link object and its program_revision')
 current=records(server.module_state).get(actor)
 source=next((o for o in server.objects if o['id']==actor),None)
 prop=next((o for o in server.objects if o['id']==args['object']),None)
 link=observed_link(server,prop) if prop else None
 if (not current or current['status']!='active' or not source or not prop or not link
     or walking(server.module_state,actor) or prop.get('kind')!='prop' or prop.get('portable')
     or program_revision(server,prop)!=args['revision']
     or any(source.get(k)!=prop.get(k) for k in ('group','num','region_revision'))
     or abs(source['x']-prop['x'])+abs(source['y']-prop['y'])!=1):
  raise ValueError('Actor must be idle and adjacent to the exact observed physical link')
 if any(type(p.get('character_pending')) is dict and p['character_pending'].get('id')==actor for p in server.peers.values()):
  raise ValueError('Actor has an outstanding player battle')
 cave=destination(server,link['place'],link['destination'])
 # A small entrance neighborhood, never the player warp tile or a blocked route.
 candidates=[]
 for y in range(1,5):
  for x in range(1,5):
   if (x,y)==(1,1) or not cave.walkable(x,y):continue
   if any(p.get('ready') and p.get('generated_place',{}).get('revision')==cave.identity and (p.get('x'),p.get('y'))==(x,y) for p in server.inspect()['players']):continue
   after=dict(source,region_revision=cave.identity,x=x,y=y)
   objects=[after if o['id']==actor else o for o in server.objects]
   try:validate_region_objects(server,objects,server.module_state)
   except ValueError:continue
   # Explicit occupancy avoids overlap with other stationary NPCs.
   if any(o['id']!=actor and o.get('region_revision')==cave.identity and (o['x'],o['y'])==(x,y) for o in server.objects):continue
   candidates.append(after)
 if not candidates:raise ValueError('Destination entrance neighborhood is occupied or unsafe; inspect and replan')
 after=min(candidates,key=lambda o:(o['x']+o['y'],o['y'],o['x']))
 action=dict(id=actor,expected_version=current['version'],evidence=current['evidence'],
     reason='Traverse an existing physical cave link under authority ownership.',changes={},object=after,preconditions=dict(source=source,prop=prop,arrival=after))
 context=server.inspect();context['runtime']=dict(previous_source=server.candidate.source)
 context['recalled_history']=dict(events=[dict(json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in current['evidence']])
 compiled=compile_actions([action],context)
 definition=hashlib.sha256(json.dumps([action],sort_keys=True).encode()).hexdigest()
 from .actor_cargo import freeze
 freeze(server,definition,actor,source,after)
 sha=hashlib.sha256(compiled.encode()).hexdigest();path=server.runtime.candidates/('cave_travel_'+sha+'.py')
 try:
  with path.open('x') as f:f.write(compiled)
 except FileExistsError:
  if path.is_symlink() or path.read_text()!=compiled:raise ValueError('Travel candidate conflict')
 return Pending(dict(definition=definition,version=current['version']+1,source=source,object=after,link=prop['id'],place=link['place']),
     lambda:setattr(server,'deployment',(None,path,None)))

def poll(server,actor,row,pending):
 from .character_dispatch import admitted
 if not admitted(server,pending['definition']):raise ValueError('Cave traversal was not admitted; no arrival occurred')
 obj=next((o for o in server.objects if o['id']==actor),None)
 current=records(server.module_state).get(actor,{})
 if obj!=pending['object'] or current.get('version')!=pending['version']:raise ValueError('Actor changed after traversal; inspect current location')
 return dict(outcome='authority_cave_arrival',source=pending['source']['region_revision'],destination=obj['region_revision'],
     place=pending['place'],x=obj['x'],y=obj['y'],link=pending['link'],version=current['version'],
     limits='Same persistent actor moved between cave scopes. Native observers receive source removal/destination appearance; no portal animation or player travel claimed.')
