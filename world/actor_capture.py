"""Host-gated asynchronous first-throw requests, never model-supplied outcomes."""
import hashlib,json
from concurrent.futures import ThreadPoolExecutor
from .capture_attempt_worker import Ledger,Engine
from . import character_capture
from .character_training import source

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS actor_capture_requests(id TEXT PRIMARY KEY,actor TEXT,individual TEXT,ball INTEGER,frozen TEXT,status TEXT,job TEXT,result TEXT)')

def request(server,actor,row,args):
 from .actor_runtime import Pending
 service=getattr(server,'capture_service',None)
 if service is None:raise ValueError('Capture disabled: host must configure an exact QA-validated experimental runner')
 if set(args)!={'individual','ball'} or type(args['individual']) is not str or type(args['ball']) is not int or args['ball'] not in (1,2,3):raise ValueError('Choose an owned companion and host-stocked basic ball')
 current=source(server,actor,args['individual'])
 if not current['trained'] or current['trained']['engine']!=service.engine.digest:raise ValueError('Exact-engine full companion state required')
 obj=next((o for o in server.objects if o['id']==actor),None)
 if not obj:raise ValueError('Actor unavailable')
 _,_,plan,step=server.actor_tool_execution
 key=hashlib.sha256(json.dumps([server.memory.world_id,actor,plan['id'],step['id']]).encode()).hexdigest()
 frozen=json.dumps(dict(source=current,object=obj),sort_keys=True)
 server.db.execute('INSERT INTO actor_capture_requests VALUES(?,?,?,?,?,?,NULL,NULL)',(key,actor,args['individual'],args['ball'],frozen,'requested'))
 return Pending(dict(request=key),lambda:None)

def poll(server,actor,row,pending):
 saved=server.db.execute('SELECT actor,result FROM actor_capture_requests WHERE id=?',(pending['request'],)).fetchone()
 if not saved or saved[0]!=actor:raise ValueError('Capture request unavailable')
 return json.loads(saved[1]) if saved[1] else None

def _execute(path,job,engine):
 ledger=Ledger(path)
 try:return ledger.execute(job,engine,validated_native=True)
 finally:ledger.close()

class Service:
 def __init__(self,path,engine,*,validated_native=False):
  if not validated_native:raise ValueError('Exact linked native capture QA attestation required')
  self.path=str(path);self.engine=engine;self.pool=ThreadPoolExecutor(max_workers=1);self.future=None;self.running=None
 def close(self):self.pool.shutdown(wait=True,cancel_futures=False)
 def tick(self,server):
  setup(server.db)
  if self.future is not None:
   if not self.future.done():return
   try:self.future.result()
   except Exception:pass # Ledger records failure; do not publish process output.
   self.future=None;self.running=None
  row=server.db.execute("SELECT id,actor,individual,ball,frozen,status,job FROM actor_capture_requests WHERE result IS NULL ORDER BY rowid LIMIT 1").fetchone()
  if not row:return
  key,actor,individual,ball,encoded,status,job=row
  ledger=Ledger(self.path)
  def finish(result):
   with server.db:server.db.execute("UPDATE actor_capture_requests SET status='finished',result=? WHERE id=?",(json.dumps(result,sort_keys=True),key))
  try:
   if status=='requested':
    # Only a still-pending plan can spend finite host-owned stock.
    live=server.db.execute("SELECT 1 FROM actor_tool_receipts WHERE actor=? AND status='pending' AND result=?",(actor,json.dumps(dict(request=key),sort_keys=True))).fetchone()
    if not live:raise ValueError('Plan no longer pending')
    current=dict(source=source(server,actor,individual),object=next((o for o in server.objects if o['id']==actor),None))
    if json.dumps(current,sort_keys=True)!=encoded:raise ValueError('Source or position changed')
    # Persist before cross-database work. A crash here is uncertain, never replayed.
    with server.db:server.db.execute("UPDATE actor_capture_requests SET status='dispatching' WHERE id=?",(key,))
    job=character_capture.queue(server,ledger,actor,individual,self.engine.digest,ball,'Trainer')
    with server.db:server.db.execute("UPDATE actor_capture_requests SET status='queued',job=? WHERE id=?",(job,key))
    self.future=self.pool.submit(_execute,self.path,job,self.engine);self.running=key
    return
   if status=='dispatching':raise ValueError('Interrupted dispatch requires host review; never automatically retried')
   state=ledger.db.execute('SELECT status,result FROM capture_jobs WHERE id=?',(job,)).fetchone()
   if not state or state[0]!='completed':raise ValueError('Interrupted or failed native attempt; no automatic retry')
   result=json.loads(state[1])
   if result['caught']:finish(character_capture.reconcile(server,ledger,job))
   else:finish(dict(outcome='not_caught_unresolved',balls_used=1,limits='One actual throw failed; no escape, victory or companion claimed.'))
  except (ValueError,KeyError):
   finish(dict(outcome='capture_not_imported',limits='Disabled, changed, interrupted or failed attempt. Host ledger retains any native result and spent stock; no retry or catch inferred.'))
  finally:ledger.close()

def available(server):
 service=getattr(server,'capture_service',None)
 if service is None:return dict(enabled=False,reason='Exact-binary host capture QA gate is not configured')
 ledger=Ledger(service.path)
 try:return dict(enabled=True,scope='Isolated first throw on format-10 habitat; not a full battle',stock=[dict(actor=a,ball=b,quantity=n) for a,b,n in ledger.db.execute('SELECT actor,ball,quantity FROM capture_stock ORDER BY actor,ball')])
 finally:ledger.close()
