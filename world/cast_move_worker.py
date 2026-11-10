"""Session practice worker extension: bounded native reminder jobs and recovery."""
import json
from .companion_moves import MoveJobs,choices

def step(ledger,engine,request,snapshot,turn_limit,period_hours,now):
 db=ledger.db;world=snapshot['world_id'];jobs=MoveJobs(ledger)
 db.execute('CREATE TABLE IF NOT EXISTS cast_move_dispatch(world TEXT,id TEXT,status TEXT,payload TEXT,PRIMARY KEY(world,id))')
 # Only retry authority application of a durable native result, never execution.
 for key,payload in db.execute("SELECT id,payload FROM cast_move_dispatch WHERE world=? AND status='awaiting_reconciliation'",(world,)):
  result=request(json.loads(payload))
  if result.get('ok') is not True:return dict(status='blocked',reason='Native move result awaits authority reconciliation',request=key)
  with db:db.execute("UPDATE cast_move_dispatch SET status='completed' WHERE world=? AND id=?",(world,key))
  return dict(status='move_reconciled',result=result)
 for actor,row in sorted(snapshot['actors'].items()):
  for task in row['intentions']:
   if task['kind']!='moves':continue
   key=task['id']
   if db.execute('SELECT 1 FROM cast_move_dispatch WHERE world=? AND id=?',(world,key)).fetchone():continue
   budget=db.execute('SELECT started,used FROM practice_budget WHERE world=? AND actor=?',(world,actor)).fetchone()
   if budget and now<budget[0]+period_hours*3600 and budget[1]>=turn_limit:continue
   try:
    response=request(dict(command='character_practice_source',actor=actor,individual=task['target']))
    if response.get('ok') is not True:raise ValueError('Companion source unavailable')
    source=response['source'];saved=source['trained']
    if source['world_id']!=world or source['version']!=row['version'] or source['token']!=task['token'] or not saved or saved['engine']!=engine.digest:raise ValueError('Full native source changed or wrong engine')
    try:local=ledger.get(actor,task['target'])
    except ValueError:
     with db:db.execute('INSERT INTO companions VALUES(?,?,?,?,?)',(actor,task['target'],engine.digest,1,json.dumps(saved['state'],sort_keys=True)))
     local=ledger.get(actor,task['target'])
    if local['engine']!=engine.digest or local['state']!=saved['state']:raise ValueError('Local and world individual states diverged')
    with db:
     db.execute('BEGIN IMMEDIATE')
     budget=db.execute('SELECT started,used FROM practice_budget WHERE world=? AND actor=?',(world,actor)).fetchone()
     if budget and now<budget[0]+period_hours*3600 and budget[1]>=turn_limit:raise ValueError('Host period budget exhausted')
     started,used=(now,0) if not budget or now>=budget[0]+period_hours*3600 else budget
     db.execute('INSERT INTO practice_budget VALUES(?,?,?,?) ON CONFLICT(world,actor) DO UPDATE SET started=excluded.started,used=excluded.used',(world,actor,started,used+1))
     db.execute("INSERT INTO cast_move_dispatch VALUES(?,?,'running',NULL)",(world,key))
    before=local['state'];line=engine.exchange(f"MOVES1 {before['size']} {before['blob']}");choices(line)
    args=task['args'];after=None
    if 'move' in args:
     job=jobs.queue(actor,task['target'],local['revision'],args['move'],args['slot'])
     after=jobs.execute(job,engine)['state']
    payload=dict(command='character_moves_finish',request=key,engine=engine.digest,before=before,after=after,choices=line)
    with db:db.execute("UPDATE cast_move_dispatch SET status='awaiting_reconciliation',payload=? WHERE world=? AND id=?",(json.dumps(payload,sort_keys=True),world,key))
    result=request(payload)
    if result.get('ok') is not True:return dict(status='blocked',request=key,reason='Native move result awaits authority reconciliation')
    with db:db.execute("UPDATE cast_move_dispatch SET status='completed' WHERE world=? AND id=?",(world,key))
    return dict(status='native_moves_completed',result=result)
   except Exception as exc:
    with db:db.execute("UPDATE cast_move_dispatch SET status='failed' WHERE world=? AND id=? AND status='running'",(world,key))
    try:request(dict(command='character_moves_fail',request=key))
    except Exception:pass
    return dict(status='blocked',request=key,reason=str(exc))
 return None
