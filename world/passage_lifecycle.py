"""Revision-bound paired passage availability, never destination replacement."""
import json

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS passage_lifecycle(connection TEXT PRIMARY KEY,owner TEXT,revision INTEGER,enabled INTEGER,definition TEXT)')

def definition(server,key):
 value=server.module_state.get('world_place_connections',{}).get(key)
 if not value or len(value.get('links',[]))!=2 or len(value.get('objects',[]))!=2:raise ValueError('Choose an admitted paired passage')
 if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='cave_links'").fetchone():raise ValueError('Passage not installed')
 for link in value['links']:
  row=server.db.execute('SELECT source,place,destination FROM cave_links WHERE object=?',(link['object'],)).fetchone()
  if not row or tuple(row)!=tuple(link[k] for k in ('source','place','destination')):raise ValueError('Passage installation changed')
  obj=next((o for o in server.objects if o['id']==link['object']),None)
  if not obj or obj.get('kind')!='prop' or obj.get('portable') or obj.get('region_revision')!=link['source']:raise ValueError('Actual passage endpoint unavailable')
 return value

def owners(server,key):
 result=set()
 # Only successful authority tool receipts or the original network author,
 # never an actor-supplied ownership assertion.
 for actor,raw in server.db.execute("SELECT actor,result FROM actor_tool_receipts WHERE status='succeeded'"):
  receipt=json.loads(raw)
  if receipt.get('outcome')=='paired_cave_connection_installed' and receipt.get('connection')==key:result.add(actor)
 if server.db.execute("SELECT 1 FROM sqlite_master WHERE name='authored_region_networks'").fetchone():
  for actor,raw in server.db.execute('SELECT actor,request FROM authored_region_networks'):
   if any(c.get('id')==key for c in json.loads(raw).get('connections',[])):result.add(actor)
 return result

def status(server,obj):
 if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='passage_lifecycle'").fetchone():return dict(enabled=True,revision=0)
 for key,owner,revision,enabled,raw in server.db.execute('SELECT * FROM passage_lifecycle'):
  value=json.loads(raw)
  if any(link['object']==obj for link in value['links']):
   if server.module_state.get('world_place_connections',{}).get(key)!=value:return dict(enabled=False,revision=revision,connection=key,changed=True)
   return dict(enabled=bool(enabled),revision=revision,connection=key,owner=owner)
 return dict(enabled=True,revision=0)

def program_revision(server,obj):
 from .actor_objects import digest
 base=[obj,server.candidate.sha256 if server.candidate else None];revision=status(server,obj['id'])['revision']
 if revision:base.append(revision)
 return digest(base)

def caption(server,obj):
 return 'Passage closed' if not status(server,obj['id'])['enabled'] else obj['text']

def busy(server,value):
 regions={l['source'] for l in value['links']};objects={l['object'] for l in value['links']}
 for peer in server.peers.values():
  pending=peer.get('cave_link_pending')
  if pending and (pending.get('source') in regions or getattr(pending.get('target'),'identity',None) in regions):return 'A player transfer involving these places is still pending'
 from .characters import records
 cast=records(server.module_state)
 for actor,plan,raw in server.db.execute("SELECT actor,plan,result FROM actor_tool_receipts WHERE status='pending'"):
  if (cast.get(actor,{}).get('plan') or {}).get('id')!=plan:continue
  pending=json.loads(raw)
  if pending.get('link') in objects:return 'An NPC traversal is still pending'
  if pending.get('journey') and server.db.execute("SELECT 1 FROM sqlite_master WHERE name='actor_linked_journeys'").fetchone():
   row=server.db.execute('SELECT data FROM actor_linked_journeys WHERE id=? AND actor=?',(pending['journey'],actor)).fetchone()
   if row:
    data=json.loads(row[0])
    if any(e['object'] in objects for e in data['edges'][data['index']:]):return 'A current NPC journey still depends on this passage'
 return None

def catalog(server):
 setup(server.db);result=[]
 for key in sorted(server.module_state.get('world_place_connections',{})):
  try:value=definition(server,key)
  except ValueError:continue
  state=status(server,value['links'][0]['object'])
  result.append(dict(connection=key,owners=sorted(owners(server,key)),revision=state['revision'],enabled=state['enabled'],links=value['links'],blocked=busy(server,value)))
 return result

def configure(server,actor,row,args):
 setup(server.db)
 if set(args)!={'connection','revision','operation'} or type(args['connection']) is not str or type(args['revision']) is not int or args['operation'] not in ('close','open'):raise ValueError('Choose exact passage revision and close/open')
 key=args['connection'];value=definition(server,key);state=status(server,value['links'][0]['object'])
 if state.get('changed'):raise ValueError('Passage definition changed; lifecycle preserves the original endpoints')
 if owners(server,key)!={actor}:raise ValueError('Unambiguous original passage ownership required')
 if state['revision']!=args['revision']:raise ValueError('Passage revision changed; inspect again')
 if server.job is not None or server.deployment is not None:raise ValueError('Wait for current mechanic admission')
 reason=busy(server,value)
 if reason:raise ValueError(reason+'; finish or explicitly cancel it first')
 enabled=args['operation']=='open'
 if enabled==state['enabled']:raise ValueError('Passage already has this state')
 seq=server.memory.append('paired_passage_availability_changed',dict(character_id=actor,connection=key,previous_revision=state['revision'],enabled=enabled,links=value['links'],basis='authority_route_availability',limits='Both directions only. No destination changed, traveler moved, place deleted, private return warp or regional menu revoked.'))
 server.db.execute('INSERT INTO passage_lifecycle VALUES(?,?,?,?,?) ON CONFLICT(connection) DO UPDATE SET revision=excluded.revision,enabled=excluded.enabled',(key,actor,seq,int(enabled),json.dumps(value,sort_keys=True)))
 server.revision=seq
 return dict(outcome='paired_passage_opened' if enabled else 'paired_passage_closed',connection=key,revision=seq,links=value['links'])

def bind(server,pending,obj):
 state=status(server,obj)
 if not state['enabled']:raise ValueError('Passage is closed')
 pending['passage_object']=obj;pending['passage_revision']=state['revision']

def validate_pending(server,pending):
 if 'passage_object' not in pending:return # Existing non-managed transport fixtures/legacy offers.
 state=status(server,pending['passage_object'])
 if not state['enabled'] or state['revision']!=pending['passage_revision']:raise ValueError('Passage changed; cancel and inspect again')
