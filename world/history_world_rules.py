"""Bounded persistent reactions to public facts, using existing world executors."""
import json,re,time,sqlite3

TOOLS=('world.configure_outbreak','world.configure_fishing','world.set_weather')
EVENTS=('canonical_trainer_result','landmark_discovery_shared','public_story_choice_committed','character_journey_arrived','player_addressed_character','spatial_public_speech')


def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS history_world_rules(actor TEXT,id TEXT,definition TEXT,cursor INTEGER,enabled INTEGER,window REAL,used INTEGER,next_at REAL,PRIMARY KEY(actor,id))')
 db.execute('CREATE TABLE IF NOT EXISTS history_world_rule_runs(actor TEXT,id TEXT,event_seq INTEGER,status TEXT,result TEXT,receipt INTEGER,PRIMARY KEY(actor,id,event_seq))')
 db.execute('CREATE TABLE IF NOT EXISTS history_world_rule_scheduler(singleton INTEGER PRIMARY KEY,last_actor TEXT,last_id TEXT)')


def publish(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id','rule'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']) or type(args['rule']) is not str or len(args['rule'])>650:raise ValueError('Use a rule ID and bounded literal rule JSON')
 d=json.loads(args['rule'])
 if type(d) is not dict or set(d)!={'event','where','tool','args','cooldown','per_hour'}:raise ValueError('Use event/where/tool/args/cooldown/per_hour')
 if d['event'] not in EVENTS or d['tool'] not in TOOLS:raise ValueError('Use a discovered public trigger and reviewed world operation')
 if type(d['where']) is not dict or len(d['where'])>4 or any(type(k) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,63}',k) or type(v) not in (str,int,bool) or (type(v) is str and len(v)>100) for k,v in d['where'].items()):raise ValueError('Use up to four literal top-level equality filters')
 if type(d['args']) is not dict or any(type(k) is not str or type(v) not in (str,int,bool) for k,v in d['args'].items()):raise ValueError('Operation arguments are fixed literal scalars, never event interpolation')
 if type(d['cooldown']) is not int or not 60<=d['cooldown']<=86400 or type(d['per_hour']) is not int or not 1<=d['per_hour']<=12:raise ValueError('Cooldown 60..86400 seconds and 1..12 attempts per rolling hour')
 from .actor_runtime import CAPABILITIES,actor_records
 cap=CAPABILITIES[d['tool']];record=actor_records(server).get(actor)
 if not record or ('canonical' if record.get('canonical') else 'world') not in cap.kinds or cap.poll is not None:raise ValueError('Operation is unavailable to this actor')
 if set(d['args'])!=set(cap.arguments):raise ValueError('Supply exactly the operation arguments in discovery')
 encoded=json.dumps(d,sort_keys=True);old=server.db.execute('SELECT definition FROM history_world_rules WHERE actor=? AND id=?',(actor,args['id'])).fetchone()
 if old:
  if old[0]!=encoded:raise ValueError('Rule identities are immutable; pause an old rule before authoring a different ID')
  return dict(outcome='rule_already_registered',rule=args['id'])
 if server.db.execute('SELECT count(*) FROM history_world_rules WHERE enabled=1').fetchone()[0]>=32 or server.db.execute('SELECT count(*) FROM history_world_rules WHERE actor=? AND enabled=1',(actor,)).fetchone()[0]>=2:raise ValueError('Pause an existing rule before adding another active reaction')
 head=server.memory.history(limit=1)['through']
 server.db.execute('INSERT INTO history_world_rules VALUES(?,?,?,?,1,0,0,0)',(actor,args['id'],encoded,head))
 seq=server.memory.append('history_world_rule_registered',dict(character_id=actor,rule=args['id'],definition=d,after=head,basis='literal_future_public_event_reaction',limits='Registration is not an effect. Each attempt revalidates the current actor and native operation guards; no model call.'))
 server.revision=seq
 return dict(outcome='world_reaction_registered',rule=args['id'],after=head,receipt=seq)


def pause(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id'} or not server.db.execute('SELECT 1 FROM history_world_rules WHERE actor=? AND id=?',(actor,args['id'])).fetchone():raise ValueError('Choose your own existing rule')
 server.db.execute('UPDATE history_world_rules SET enabled=0 WHERE actor=? AND id=?',(actor,args['id']))
 return dict(outcome='world_reaction_paused',rule=args['id'])


def discover(server):
 setup(server.db)
 return dict(triggers=list(EVENTS),operations=list(TOOLS),rules=[dict(actor=a,id=k,definition=json.loads(d),cursor=c,enabled=bool(e),used=u,window=w,next_at=n) for a,k,d,c,e,w,u,n in server.db.execute('SELECT * FROM history_world_rules ORDER BY enabled DESC,actor,id LIMIT 128')],limits='Future public events only. Fixed arguments, no code or event-text execution. Max two active rules per actor and 32 total; each persists across plans, but actor retirement disables it. Attempts, not successes, consume the recurring budget. Native guards still apply.')


def _tick(server,*,now=None):
 if server.job is not None or server.deployment is not None:return
 now=time.time() if now is None else now
 if now<getattr(server,'history_rule_next',0):return
 server.history_rule_next=now+5;setup(server.db)
 from .actor_runtime import CAPABILITIES,actor_records
 records=actor_records(server)
 cursor=server.db.execute('SELECT last_actor,last_id FROM history_world_rule_scheduler WHERE singleton=1').fetchone()
 rules=server.db.execute('SELECT * FROM history_world_rules WHERE enabled=1 ORDER BY actor,id').fetchall()
 if cursor:rules=[r for r in rules if tuple(r[:2])>tuple(cursor)]+[r for r in rules if tuple(r[:2])<=tuple(cursor)]
 for actor,key,raw,after,enabled,window,used,next_at in rules:
  record=records.get(actor)
  if not record or record.get('status','active')!='active':
   with server.db:server.db.execute('UPDATE history_world_rules SET enabled=0 WHERE actor=? AND id=?',(actor,key))
   continue
  d=json.loads(raw)
  if now>=window+3600:window=now;used=0
  if now<next_at or used>=d['per_hour']:continue
  page=server.memory.history(after=after,limit=64)
  event=next((e for e in page['events'] if e.get('event')==d['event'] and all(type(e.get(k)) is type(v) and e.get(k)==v for k,v in d['where'].items())),None)
  if event is None:
   with server.db:server.db.execute('UPDATE history_world_rules SET cursor=? WHERE actor=? AND id=?',(page['cursor'],actor,key))
   continue
  cap=CAPABILITIES[d['tool']];status='succeeded';old_revision=server.revision
  with server.db:
   # sqlite context managers do not BEGIN until DML; releasing an outermost
   # savepoint would otherwise commit the effect before its causal receipt.
   if not server.db.in_transaction:server.db.execute('BEGIN')
   server.db.execute('SAVEPOINT history_rule_effect')
   try:
    if cap.poll is not None or ('canonical' if record.get('canonical') else 'world') not in cap.kinds:raise ValueError('Operation unavailable for current actor')
    result=cap.execute(server,actor,record,d['args'])
    if type(result) is not dict:raise ValueError('World executor did not return a synchronous result')
    server.db.execute('RELEASE history_rule_effect')
   except (ValueError,TypeError,KeyError) as exc:
    server.db.execute('ROLLBACK TO history_rule_effect');server.db.execute('RELEASE history_rule_effect');server.revision=old_revision
    status='blocked';result=dict(reason=str(exc)[:240],effect_applied=False)
   seq=server.memory.append('history_world_rule_result',dict(character_id=actor,rule=key,trigger=event['seq'],tool=d['tool'],status=status,result=result,basis='current_validated_world_executor',limits='Trigger remains its original reported provenance. No fictional cause, observed encounter, victory or native rendering asserted.'))
   server.db.execute('INSERT INTO history_world_rule_runs VALUES(?,?,?,?,?,?)',(actor,key,event['seq'],status,json.dumps(result,sort_keys=True),seq))
   server.db.execute('UPDATE history_world_rules SET cursor=?,window=?,used=?,next_at=? WHERE actor=? AND id=?',(event['seq'],window,used+1,now+d['cooldown'],actor,key))
   server.db.execute('INSERT OR REPLACE INTO history_world_rule_scheduler VALUES(1,?,?)',(actor,key));server.revision=seq
  return dict(actor=actor,rule=key,trigger=event['seq'],status=status,receipt=seq,result=result)


def tick(server,*,now=None):
 before=server.revision
 try:return _tick(server,now=now)
 except (ValueError,TypeError,KeyError,sqlite3.Error) as exc:
  server.revision=before
  return dict(status='uncommitted',reason=str(exc)[:240],effect_applied=False)


def control(server,request):
 if set(request)!={'command','action'} or request['action'] not in ('status','pause_all'):raise ValueError('Use world_reactions status or pause_all on the private owner admin socket')
 setup(server.db)
 if request['action']=='pause_all':
  with server.db:server.db.execute('UPDATE history_world_rules SET enabled=0')
 return dict(ok=True,**discover(server))
