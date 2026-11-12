"""Bounded authored cave graphs over existing region and physical-link admission."""
import copy,hashlib,inspect,json,time

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS authored_region_networks(id TEXT PRIMARY KEY,actor TEXT,request TEXT)')

def apply_network(result,request):
 import copy
 result=copy.deepcopy(result)
 records=result['state'].setdefault('world_place_connections',{})
 for connection in request['connections']:
  records.setdefault(connection['id'],copy.deepcopy(connection))
  for obj in connection['objects']:
   if not any(o['id']==obj['id'] for o in result.get('objects',[])):result.setdefault('objects',[]).append(copy.deepcopy(obj))
 result['state'].setdefault('world_region_networks',{})[request['id']]=copy.deepcopy(request)
 return result

def catalog(server):
 setup(server.db)
 return [dict(id=k,actor=a,places=json.loads(r)['places'],links=len(json.loads(r)['connections']),
              admitted=server.module_state.get('world_region_networks',{}).get(k)==json.loads(r),
              limits='Opened places may exist before passage admission completes; no visit or journey inferred.')
         for k,a,r in server.db.execute('SELECT id,actor,request FROM authored_region_networks ORDER BY id LIMIT 32')]

def start(server,actor,row,args):
 from .actor_runtime import Pending
 from .cave_blueprint import proposal_from_blueprint
 from .shared_cave import SharedCave
 from .place_connections import prepare_connection
 if set(args)!={'network'} or type(args['network']) is not str or len(args['network'])>850:raise ValueError('Use bounded connected network JSON')
 try:doc=json.loads(args['network'])
 except ValueError:raise ValueError('Invalid network JSON') from None
 if type(doc) is not dict or set(doc)!={'places','links'} or type(doc['places']) is not list or not 2<=len(doc['places'])<=4:raise ValueError('Use two to four places and an undirected connected link graph')
 links=doc['links'];n=len(doc['places'])
 if type(links) is not list or not n-1<=len(links)<=4 or any(type(e) is not list or len(e)!=2 or any(type(i) is not int or not 0<=i<n for i in e) or e[0]==e[1] for e in links):raise ValueError('Use valid distinct place-index pairs')
 edges=[tuple(sorted(e)) for e in links]
 if len(set(edges))!=len(edges):raise ValueError('Duplicate passage pair')
 seen={0}
 for _ in range(n):
  for a,b in edges:
   if a in seen or b in seen:seen.update((a,b))
 if len(seen)!=n:raise ValueError('All places must be connected')
 if not server.archive_generated_areas or server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('Idle durable mechanic and area archive required')
 if not getattr(server,'actor_tool_execution',None) or server.actor_tool_execution[0]!=actor:raise ValueError('Durable actor executor required')
 setup(server.db);key=hashlib.sha256(json.dumps([actor,doc],sort_keys=True).encode()).hexdigest()
 old=server.db.execute('SELECT request FROM authored_region_networks WHERE id=? AND actor=?',(key,actor)).fetchone()
 if old:request=json.loads(old[0])
 else:
  if server.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0]+n>32:raise ValueError('Opened region capacity reached')
  caves=[];labels=[]
  for place in doc['places']:
   if type(place) is not dict or set(place)!={'label','blueprint'}:raise ValueError('Each place needs label and normal cave blueprint')
   label=place['label']
   if type(label) is not str or not 1<=len(label)<=20 or not label.strip() or any(not(c.isascii() and (c.isalnum() or c in " .,'!?-")) for c in label):raise ValueError('Use literal region labels')
   proposal=proposal_from_blueprint(place['blueprint'],side=31)
   cave=SharedCave(b'EWGMAP01'+''.join(proposal['rows']).encode('ascii'))
   if any(c.identity==cave.identity for c in caves) or server.db.execute('SELECT 1 FROM generated_area_archive WHERE identity=?',(cave.identity,)).fetchone():raise ValueError('Reuse existing places rather than duplicating exact geometry')
   caves.append(cave);labels.append(label)
  places=[]
  for cave,label in zip(caves,labels):
   server.db.execute('INSERT INTO generated_area_archive VALUES(?,?,?,?,?)',(cave.identity,label,'cave',b'EWGMAP01'+b''.join(cave._rows),int(time.time())))
   opened=server._pin_region(cave.identity);places.append(dict(place_id=opened['place_id'],revision=cave.identity,label=label))
  connections=[];occupied=list(server.objects)
  for a,b in edges:
   pair=sorted([caves[a].identity,caves[b].identity]);identity=hashlib.sha256(json.dumps(pair).encode()).hexdigest()
   arguments=dict(source=places[a]['place_id'],source_revision=caves[a].identity,target=places[b]['place_id'],target_revision=caves[b].identity)
   connection=prepare_connection(server,[caves[a],caves[b]],arguments,identity,occupied)
   occupied.extend(connection['objects']);connections.append(connection)
  request=dict(id=key,places=places,connections=connections)
  server.db.execute('INSERT INTO authored_region_networks VALUES(?,?,?)',(key,actor,json.dumps(request,sort_keys=True)))
 if server.module_state.get('world_region_networks',{}).get(key)==request:return Pending(request,lambda:None)
 suffix=hashlib.sha256((server.candidate.source+key).encode()).hexdigest()[:16]
 helper=inspect.getsource(apply_network).replace('def apply_network(','def _network_'+suffix+'(',1)
 source=server.candidate.source+'\n_network_previous_'+suffix+'=update\n'+helper+f'\ndef update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy({server.module_state!r})\n    return _network_{suffix}(_network_previous_{suffix}(context,state),{request!r})\n'
 if len(source.encode())>256*1024:raise ValueError('Consolidate source before publishing this network')
 proposed=apply_network(dict(state=server.module_state,objects=server.objects,tiles=[]),request);server._validated(proposed)
 sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('network_'+sha+'.py')
 try:
  with path.open('x') as f:f.write(source)
 except FileExistsError:
  if path.is_symlink() or path.read_text()!=source:raise ValueError('Candidate conflict')
 return Pending(request,lambda:setattr(server,'deployment',(None,path,None)))

def poll(server,actor,row,pending):
 from .place_connections import poll as install
 if server.module_state.get('world_region_networks',{}).get(pending['id'])!=pending:raise ValueError('Network passages not admitted; opened places retained. Reissue the same network to resume.')
 for connection in pending['connections']:install(server,actor,row,connection)
 return dict(outcome='connected_region_network_installed',network=pending['id'],places=pending['places'],entry_place=pending['places'][0]['place_id'],entry_revision=pending['places'][0]['revision'],passages=2*len(pending['connections']),limits='Plain 31x31 caves, actual REGION1 menus and CAVELINK1 passage props. No outdoor admission, seamless travel, visits or simulated construction.')
