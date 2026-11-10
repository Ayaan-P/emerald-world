"""New fictional residents at verified ordinary Hoenn sites; no canonical relocation."""
import ast,copy,hashlib,inspect,json,re
from .native_resident_sites import catalog


def discover(server):
 try:maps=catalog()
 except ValueError as exc:return dict(maps={},unavailable=str(exc))
 return dict(maps=maps,limits='One new resident per eligible residence. No travel, takeover of stock actors, plot events or player progress. Native asset pin required.')

def project(result,request):
 import copy
 result=copy.deepcopy(result);state=result['state'];identity=request['object']['id']
 state.setdefault('world_native_residents',{}).setdefault(identity,copy.deepcopy(request['site']))
 cast=state.setdefault('world_characters',{});cast.setdefault(identity,copy.deepcopy(request['character']))
 if cast[identity]['status']=='active' and not any(o['id']==identity for o in result.get('objects',[])):
  result.setdefault('objects',[]).append(copy.deepcopy(request['object']))
 state.setdefault('world_native_resident_receipts',{}).setdefault(request['request'],identity)
 return result

def validate(server,objects,state):
 before=server.module_state.get('world_native_residents',{});registered=state.get('world_native_residents',{})
 if not before and not registered:return
 if type(registered) is not dict or len(registered)>32 or any(registered.get(k)!=v for k,v in before.items()):raise ValueError('Resident anchors cannot be removed or rewritten')
 maps=catalog();claimed=set();byid={o['id']:o for o in objects}
 from .characters import records
 cast=records(state)
 for identity,site in registered.items():
  if type(site) is not dict or set(site)!={'map','x','y'}:raise ValueError('Invalid resident anchor')
  entry=maps.get(site['map'])
  if not entry or [site['x'],site['y']] not in entry['sites'] or site['map'] in claimed:raise ValueError('Resident site unavailable or already occupied')
  claimed.add(site['map']);obj=byid.get(identity);character=cast.get(identity)
  if not character:raise ValueError('Resident must retain its persistent identity')
  if character['status']!='active':
   if obj:raise ValueError('Inactive resident must not render')
   continue
  if not obj or 'region_revision' in obj or [obj['group'],obj['num'],obj['x'],obj['y']]!=[entry['group'],entry['num'],site['x'],site['y']]:raise ValueError('Resident moved outside the verified anchor')
  if any(o['id']!=identity and (o['group'],o['num'])==(entry['group'],entry['num']) for o in objects):raise ValueError('Resident residence must not receive other dynamic objects')
  old=next((o for o in server.objects if o['id']==identity),None)
  if old!=obj:
   if any(not p.get('closing') and p.get('state') and p['state'][:2]==[entry['group'],entry['num']] for p in server.peers.values()):raise ValueError('Players must leave before a new or changed resident is admitted')
  if any(tuple(t[:2])==(entry['group'],entry['num']) for t in getattr(server,'tiles',[])):raise ValueError('Modified terrain invalidates resident sites')

def prepare(server,actor,row,args):
 if set(args)!={'map','definition'} or type(args['definition']) is not str or len(args['definition'])>700:raise ValueError('Supply an eligible map and bounded resident definition')
 entry=catalog().get(args['map'])
 if not entry:raise ValueError('Map has no reviewed resident sites')
 d=json.loads(args['definition'])
 if type(d) is not dict or set(d)!={'id','name','role','goals','team','x','y','gfx','text'}:raise ValueError('Use id,name,role,goals,team,x,y,gfx,text')
 identity=d['id']
 if type(identity) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',identity) or identity.startswith('canon_'):raise ValueError('Use a fresh original character ID')
 from .canonical_cast import BINDINGS
 from .characters import records
 from .prop_custody import inventory
 if identity in records(server.module_state) or any(o['id']==identity for o in server.objects) or any(p['object']==identity for p in inventory(server)):raise ValueError('Identity is already used')
 if type(d['name']) is not str or d['name'].strip().casefold() in [b['name'].casefold() for b in BINDINGS.values()] or identity in [b['wire'] for b in BINDINGS.values()]:raise ValueError('Do not duplicate original canonical actors')
 team=d['team']
 if type(team) is not list or any(type(m) is not dict or set(m)!={'species','level'} for m in team):raise ValueError('Use authored starting species/level pairs, never imported ownership claims')
 c=dict(version=1,name=d['name'],role=d['role'],goals=d['goals'],team=[dict(m,individual='partner_'+str(i+1)) for i,m in enumerate(team)],relationships={},status='active',object_id=identity,evidence=list(row['evidence']),reason='New authored resident; no prior journey, catch or relationship asserted.')
 obj=dict(id=identity,group=entry['group'],num=entry['num'],**{k:d[k] for k in ('x','y','gfx','text')})
 request=dict(object=obj,character=c,site=dict(map=args['map'],x=d['x'],y=d['y']))
 request['request']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
 return request

def source(old,requests,state):
 # Separate, bounded retained dispatcher. Never edits the existing population
 # v1 helper or substitutes an unreviewed source match.
 helper=inspect.getsource(project).replace('def project(','def _ew_resident_project(',1)
 wrapper='def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy(_ew_resident_seed)\n    result=_ew_resident_previous(context,state)\n    for request in _ew_resident_requests:\n        result=_ew_resident_project(result,request)\n    return result\n'
 tree=ast.parse(old);nodes=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('_ew_resident_requests','_ew_resident_seed')]
 if nodes:
  if len(nodes)!=2 or {n.targets[0].id for n in nodes}!={'_ew_resident_requests','_ew_resident_seed'}:raise ValueError('Resident dispatcher changed')
  functions=[ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)]
  if any(ast.dump(ast.parse(code).body[0],include_attributes=False) not in functions for code in (helper,wrapper)):raise ValueError('Resident projector changed; explicit consolidation required')
  values={n.targets[0].id:ast.literal_eval(n.value) for n in nodes};prior=values['_ew_resident_requests']
  if type(prior) is not list or len(prior)+len(requests)>32:raise ValueError('Resident catalog capacity reached')
  lines=old.splitlines(keepends=True)
  for n in sorted(nodes,key=lambda n:n.lineno,reverse=True):
   value=prior+requests if n.targets[0].id=='_ew_resident_requests' else state
   lines[n.lineno-1:n.end_lineno]=[f'{n.targets[0].id}={value!r}\n']
  return ''.join(lines)
 if any(isinstance(n,ast.Name) and n.id.startswith('_ew_resident_') for n in ast.walk(tree)):raise ValueError('Reserved resident dispatcher names in use')
 return old+f'\n_ew_resident_previous=update\n_ew_resident_seed={state!r}\n_ew_resident_requests={requests!r}\n'+helper+'\n'+wrapper

def spawn(server,actor,row,args):
 from .actor_population import stage
 request=prepare(server,actor,row,args)
 proposed=project(dict(state=server.module_state,objects=server.objects),request)
 validate(server,proposed['objects'],proposed['state'])
 return stage(server,actor,row,[request],projector=project,source_builder=source)

def poll(server,actor,row,pending):
 request=pending['population'][0];identity=request['object']['id']
 if server.module_state.get('world_native_resident_receipts',{}).get(request['request'])!=identity or next((o for o in server.objects if o['id']==identity),None)!=request['object']:raise ValueError('Resident not admitted; no creation claimed')
 return dict(outcome='population_admitted',kind='character',object=identity,map=request['site']['map'],basis='new_authored_native_resident_not_travel_or_capture')


def validate_terrain(state,tiles):
 if type(state) is not dict:return
 registered=state.get('world_native_residents',{})
 if not registered:return
 maps=catalog()
 if type(registered) is not dict or any(type(s) is not dict or set(s)!={'map','x','y'} or type(s['map']) is not str or s['map'] not in maps for s in registered.values()):raise ValueError('Invalid resident anchor catalog')
 reserved={(maps[s['map']]['group'],maps[s['map']]['num']) for s in registered.values()}
 if any((t['group'],t['num']) in reserved for t in tiles):raise ValueError('Resident anchors forbid mutable terrain in their residence')
