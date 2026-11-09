"""Negotiated immutable cave links with CAVELINK1 and optional CAVELINKW1.

This module intentionally does not relax REGION SELECT or shared-XL admission.
"""
import hashlib,time
from .shared_cave import SharedCave

def destination(server,place,revision):
 row=server.db.execute('SELECT a.template,r.revision FROM world_region_revisions r JOIN generated_area_archive a ON a.identity=r.revision WHERE r.place_id=?',(place,)).fetchone()
 if not row or row[1]!=revision or hashlib.sha256(row[0]).hexdigest()!=revision:raise ValueError('Exact opened cave unavailable')
 cave=SharedCave(row[0])
 if cave.version not in (1,10):raise ValueError('Physical links initially support format-1 or Expansion format-10 caves only')
 return cave

def offer(server,conn,seq,source,target_place,target_revision):
 if not conn.get('cave_link_capable') or not conn.get('region_capable') or conn.get('cave_link_pending'):raise ValueError('Cave link transport unavailable')
 state=conn.get('state');cave=server._connection_cave(conn)
 if (not cave or cave.version not in (1,10) or cave.identity!=source or conn.get('cave_ack')!=source
     or not state or not state[6] or tuple(state[:2])!=server.cave_map
     or time.monotonic()-conn.get('state_time',0)>5 or server.link_protocol.busy(conn['id'])
     or server.rally.current(conn) is not None):raise ValueError('Fresh source cave admission required')
 target=destination(server,target_place,target_revision)
 if (cave.version==10 or target.version==10) and not conn.get('cave_link_wildlife'):raise ValueError('Wildlife cave transfer unavailable')
 if target.identity==source or not server._props_compatible(conn,target):raise ValueError('Destination unsupported')
 conn['cave_link_pending']=dict(seq=seq,source=source,target=target,place=target_place,
     source_place=conn.get('region_place'),source_cave=conn.get('region_cave'),state=list(state),
     expires=time.monotonic()+30,phase='offered')
 # Caller performs actual object/facing validation before calling offer.
 # Source region_cave/cave_ack remain untouched while destination is downloaded.
 return target.frames()

def acknowledge(server,conn,seq,revision):
 pending=conn.get('cave_link_pending')
 if not pending or pending['seq']!=seq or pending['target'].identity!=revision or pending['phase']!='offered':raise ValueError('Unexpected cave transfer acknowledgement')
 if time.monotonic()-conn.get('state_time',0)>5 or server.link_protocol.busy(conn['id']) or server.rally.current(conn) is not None or time.monotonic()>pending['expires'] or conn.get('cave_ack')!=pending['source'] or conn.get('state')!=pending['state']:raise ValueError('Source changed before transfer commit')
 destination(server,pending['place'],revision)
 pending['phase']='committed';pending['expires']=time.monotonic()+30
 conn['region_cave']=pending['target'];conn['region_place']=pending['place']
 conn['cave_offer']=conn['cave_ack']=revision;conn['cave_transfer_pending']=False
 conn['state']=None # Never publish old coordinates in the newly selected region.
 conn['state_time']=0
 return dict(seq=seq,revision=revision)

def abort(server,conn,seq):
 pending=conn.get('cave_link_pending')
 if not pending or pending['seq']!=seq:raise ValueError('Unknown transfer')
 conn['region_cave']=pending['source_cave'];conn['region_place']=pending['source_place']
 conn['cave_offer']=conn['cave_ack']=pending['source'];conn['cave_transfer_pending']=False
 conn['state']=None;conn['state_time']=0 # New native STATE needed, never revive stale readiness.
 conn['cave_link_pending']=None

def install(server,actor,row,args):
 from .actor_observation import observe
 from .actor_objects import digest
 if set(args)!={'object','revision','place','destination'}:raise ValueError('Exact observed prop and opened destination required')
 obj=next((o for o in server.objects if o['id']==args['object']),None)
 seen=observe(server,actor,row,dict(radius=4))
 entry=next((e for e in seen['entities'] if e['id']==args['object']),{})
 if not obj or obj.get('kind')!='prop' or obj.get('portable') or entry.get('program_revision')!=args['revision']:raise ValueError('Observed anchored prop required')
 if server.module_state.get('world_object_actions',{}).get(obj['id']) or obj['id'] in server.module_state.get('world_object_programs',{}):raise ValueError('Existing object behavior is preserved')
 source=SharedCave(server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(obj['region_revision'],)).fetchone()[0])
 if source.version not in (1,10):raise ValueError('Source must be an immutable supported cave')
 target=destination(server,args['place'],args['destination'])
 if target.identity==source.identity:raise ValueError('Choose a different cave')
 server.db.execute('CREATE TABLE IF NOT EXISTS cave_links(object TEXT PRIMARY KEY,source TEXT,place TEXT,destination TEXT)')
 if server.db.execute('SELECT 1 FROM cave_links WHERE object=?',(obj['id'],)).fetchone():raise ValueError('Link already exists')
 server.db.execute('INSERT INTO cave_links VALUES(?,?,?,?)',(obj['id'],source.identity,args['place'],target.identity))
 return dict(outcome='cave_link_installed',object=obj['id'],source=source.identity,place=args['place'],destination=target.identity,requires='CAVELINK1 client, native confirmation and completed transfer; no travel occurred')

def interact(server,conn,obj,seq):
 if not conn.get('cave_link_capable'):return False
 if not server.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cave_links'").fetchone():return False
 link=server.db.execute('SELECT source,place,destination FROM cave_links WHERE object=?',(obj['id'],)).fetchone()
 if not link or link[0]!=obj.get('region_revision'):return False
 offer(server,conn,seq,*link)
 conn['cave_link_pending']['phase']='consent'
 label=server.db.execute('SELECT label FROM generated_area_archive WHERE identity=?',(link[2],)).fetchone()[0] or 'Cave'
 label=''.join(c if c.isascii() and (c.isalnum() or c in " .,'!?-") else ' ' for c in label).strip()[:20] or 'Cave'
 server._queue(conn,f'LINK OFFER {seq} {link[0]} {link[1]} {link[2]} {label.encode().hex()}\n')
 return True

def line(server,conn,fields):
 if not conn.get('cave_link_capable') or len(fields)<3:raise ValueError('Link protocol unavailable')
 seq=int(fields[2]);p=conn.get('cave_link_pending')
 if not p or p['seq']!=seq:raise ValueError('Unknown cave transfer')
 if time.monotonic()>p['expires']:
  if p['phase']=='committed':conn['closing']=True
  else:abort(server,conn,seq)
  raise ValueError('Transfer expired; no arrival inferred')
 if fields[1]=='ACCEPT' and len(fields)==3 and p['phase']=='consent':
  if time.monotonic()>p['expires']:raise ValueError('Link consent expired')
  p['phase']='offered'
  for frame in p['target'].frames().splitlines():server._queue(conn,'LINK DATA '+str(seq)+' '+frame+'\n')
 elif fields[1]=='ACK' and len(fields)==4:
  acknowledge(server,conn,seq,fields[3]);server._queue(conn,f'LINK COMMIT {seq} {fields[3]}\n');server._broadcast()
 elif fields[1]=='ABORT' and len(fields)==3:
  abort(server,conn,seq);server._queue(conn,f'LINK ABORTED {seq}\n');server._broadcast()
 elif fields[1]=='ARRIVED' and len(fields)==4 and p['phase']=='committed' and fields[3]==p['target'].identity:
  state=conn.get('state')
  if not state or not state[6] or tuple(state[:2])!=server.cave_map or state[2:4]!=[1,1]:raise ValueError('Destination arrival not observed')
  with server.db:server._event('cave_link_arrival',dict(player=conn['id'],source=p['source'],destination=p['target'].identity,place=p['place']))
  conn['cave_link_pending']=None;server._queue(conn,f'LINK DONE {seq}\n')
 else:raise ValueError('Invalid cave transfer phase')

def state_guard(conn,state):
 p=conn.get('cave_link_pending')
 if p and p['phase']=='committed' and state[6] and state[2:4]!=[1,1]:raise ValueError('Transfer awaits exact destination entry')
