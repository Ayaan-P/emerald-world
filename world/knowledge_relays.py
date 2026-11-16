"""Physical report relays retain original observation provenance; no invented sight."""
import json,time
from .actor_social import participants

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_knowledge_routes(delivery INTEGER PRIMARY KEY,origin TEXT,observation INTEGER,previous INTEGER,hops INTEGER)')
 db.execute('CREATE TABLE IF NOT EXISTS actor_knowledge_notices(delivery INTEGER PRIMARY KEY,origin TEXT,text TEXT,created REAL)')

def lineage(server,delivery,sender,observation):
 setup(server.db)
 row=server.db.execute('SELECT origin,observation,previous,hops FROM actor_knowledge_routes WHERE delivery=?',(delivery,)).fetchone()
 if row:return dict(observer=row[0],observation=row[1],previous_delivery=row[2],hops=row[3])
 return dict(observer=sender,observation=observation,previous_delivery=None,hops=1)

def relay(server,actor,row,args):
 if set(args)!={'target','expected_version','delivery'} or type(args['delivery']) is not int:raise ValueError('Supply a received report delivery and inspected recipient')
 setup(server.db)
 _,obj,target,other=participants(server,actor,args)
 if abs(obj['x']-other['x'])+abs(obj['y']-other['y'])!=1:raise ValueError('Reports require an actual adjacent meeting')
 saved=server.db.execute('SELECT sender,observation,snapshot FROM actor_knowledge WHERE recipient=? AND delivered=?',(actor,args['delivery'])).fetchone()
 if not saved:raise ValueError('This character did not receive that report')
 sender,observation,raw=saved;source=lineage(server,args['delivery'],sender,observation)
 if args['target']==source['observer']:return dict(outcome='report_already_known',recipient=args['target'],observation=observation,basis='original_observer')
 old=server.db.execute('SELECT delivered FROM actor_knowledge WHERE recipient=? AND observation=? ORDER BY delivered LIMIT 1',(args['target'],observation)).fetchone()
 if old:return dict(outcome='report_already_known',recipient=args['target'],observation=observation,delivery=old[0])
 snapshot=json.loads(raw)
 seq=server.memory.append('character_report_relayed',dict(character_id=actor,recipient=args['target'],recipient_version=target['version'],
     observer=source['observer'],observation=observation,previous_delivery=args['delivery'],hops=source['hops']+1,
     observed_revision=snapshot['observed_revision'],revision=snapshot['revision'],meeting_revision=obj['region_revision'],
     publication='public_world_observation',basis='adjacent_received_report_relay',limits='Dated original observation passed along unchanged; not relay sight, recipient belief or a current-world fact.'))
 server.db.execute('INSERT INTO actor_knowledge VALUES(?,?,?,?,?)',(args['target'],actor,observation,seq,raw))
 server.db.execute('INSERT INTO actor_knowledge_routes VALUES(?,?,?,?,?)',(seq,source['observer'],observation,args['delivery'],source['hops']+1))
 origin={k:obj[k] for k in ('group','num','x','y','region_revision')};origin['radius']=3
 server.db.execute('INSERT INTO actor_knowledge_notices VALUES(?,?,?,?)',(seq,json.dumps(origin),f"{actor} passes a dated report to {args['target']}.",time.time()))
 server.revision=seq
 return dict(outcome='dated_report_relayed',delivery=seq,recipient=args['target'],observer=source['observer'],observation=observation,hops=source['hops']+1)

def flush(server):
 # Existing server loop calls this after the actor transaction commits. Never
 # announce a rolled-back handoff or replay old notifications to late joiners.
 setup(server.db)
 from .spatial_speech import footprint,player_near
 for seq,raw,text,created in server.db.execute('SELECT * FROM actor_knowledge_notices ORDER BY delivery LIMIT 8').fetchall():
  with server.db:server.db.execute('DELETE FROM actor_knowledge_notices WHERE delivery=?',(seq,))
  if not 0<=time.time()-created<=5:continue
  origin=json.loads(raw)
  try:cells=footprint(server,origin)
  except ValueError:continue
  for peer in list(server.peers.values()):
   if player_near(server,peer,origin,cells):server.guild_chat.message(peer,'World',text)

def relevant(event,actor):
 return event.get('event')=='character_report_relayed' and event.get('recipient')==actor and event.get('publication')=='public_world_observation' and event.get('basis')=='adjacent_received_report_relay'
