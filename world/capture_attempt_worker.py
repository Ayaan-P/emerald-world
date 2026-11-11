"""Offline experimental first-throw jobs, not enabled autonomous world capture.

Native must be built with WORLD_CHARACTER_CAPTURE_EXPERIMENT=1 and separately
validated by the host. This ledger never imports a companion into a live world.
Failed throws are unresolved, not escaped/won battles.
"""
import hashlib,json,re,secrets,sqlite3,subprocess,tempfile,uuid
from pathlib import Path
from .companion_practice import state
from .shared_cave import SharedCave

class Engine:
 def __init__(self,path,digest):
  self.path=Path(path).resolve(strict=True);self.digest=digest
  if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Exact executable SHA256 required')
 def run(self,line):
  if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.digest:raise ValueError('Executable changed')
  with tempfile.TemporaryDirectory(prefix='npc-capture-') as directory:
   run=subprocess.run([str(self.path),'--character-practice'],input=line+'\n',text=True,capture_output=True,timeout=30,cwd=directory,env={'LANG':'C','LC_ALL':'C'})
  if run.returncode or len(run.stdout)>4096:raise ValueError('Native attempt failed; no capture committed')
  return run.stdout

def response(text):
 parts=text.split()
 if len(parts)!=10 or parts[0]!='ATTEMPT1' or parts[1] not in ('0','1') or not re.fullmatch('[0-9]{1,2}',parts[2]):raise ValueError('Invalid native attempt response')
 return dict(caught=parts[1]=='1',remaining=int(parts[2]),state=state('STATE1 '+' '.join(parts[3:])))

class Ledger:
 def __init__(self,path):
  self.db=sqlite3.connect(path)
  self.db.executescript('''
  CREATE TABLE IF NOT EXISTS capture_stock(actor TEXT,ball INTEGER,quantity INTEGER,PRIMARY KEY(actor,ball));
  CREATE TABLE IF NOT EXISTS capture_jobs(id TEXT PRIMARY KEY,actor TEXT,engine TEXT,request TEXT,status TEXT,result TEXT);
  CREATE TABLE IF NOT EXISTS capture_results(id TEXT PRIMARY KEY,actor TEXT,revision TEXT,state TEXT);
  ''')
 def close(self):self.db.close()
 def supply(self,actor,ball,quantity):
  # Explicit host provisioning only; no default supply or agent minting.
  if not re.fullmatch('[A-Za-z0-9_-]{1,24}',actor) or ball not in (1,2,3) or type(quantity) is not int or not 0<=quantity<=99:raise ValueError('Bounded host-owned stock required')
  if self.db.execute("SELECT 1 FROM capture_jobs WHERE actor=? AND status IN ('queued','running')",(actor,)).fetchone():raise ValueError('Finish/review existing jobs before replacing stock')
  with self.db:self.db.execute('INSERT INTO capture_stock VALUES(?,?,?) ON CONFLICT(actor,ball) DO UPDATE SET quantity=excluded.quantity',(actor,ball,quantity))
 def queue(self,actor,companion,habitat,owner,name,ball,engine):
  cave=SharedCave(habitat)
  if cave.version!=10 or type(owner) is not int or not 0<=owner<=0xffffffff or not re.fullmatch('[A-Za-z]{1,7}',name):raise ValueError('Expansion cave and explicit bounded fictional owner required')
  parsed=state('STATE1 '+' '.join(str(companion[k]) for k in ('size','species','level','personality','owner','exp','blob')))
  if parsed['size']!=100:raise ValueError('Exact current native Pokemon ABI required')
  if not re.fullmatch('[0-9a-f]{64}',engine):raise ValueError('Exact native executable digest required')
  job=uuid.uuid4().hex
  with self.db:
   if self.db.execute("SELECT 1 FROM capture_jobs WHERE actor=? AND status IN ('queued','running')",(actor,)).fetchone():raise ValueError('Actor already has an unresolved attempt')
   stock=self.db.execute('SELECT quantity FROM capture_stock WHERE actor=? AND ball=?',(actor,ball)).fetchone()
   if not stock or not stock[0]:raise ValueError('No host-provisioned ball available')
   seed=secrets.randbits(32)
   request=dict(source=parsed,revision=cave.identity,wildlife=cave.wildlife.hex(),owner=owner,name=name,ball=ball,stock=stock[0],seed=seed)
   # Reserve before external work; uncertain execution never creates a free retry.
   self.db.execute('UPDATE capture_stock SET quantity=quantity-1 WHERE actor=? AND ball=?',(actor,ball))
   self.db.execute('INSERT INTO capture_jobs VALUES(?,?,?,?,?,NULL)',(job,actor,engine,json.dumps(request,sort_keys=True),'queued'))
  return job
 def execute(self,job,engine,*,validated_native=False):
  if not validated_native:raise ValueError('Exact-binary linked capture QA is required; experiment remains disabled')
  with self.db:
   if self.db.execute("UPDATE capture_jobs SET status='running' WHERE id=? AND engine=? AND status='queued'",(job,engine.digest)).rowcount!=1:raise ValueError('Job unavailable or wrong engine')
  actor,request=self.db.execute('SELECT actor,request FROM capture_jobs WHERE id=?',(job,)).fetchone();r=json.loads(request)
  line=f"ENCOUNTER1 {r['source']['size']} {r['seed']} {r['owner']} {r['ball']} {r['stock']} {r['wildlife']} {r['source']['blob']} FIRST_THROW_ONLY {r['name']}"
  try:
   result=response(engine.run(line));mon=result['state'];wild=bytes.fromhex(r['wildlife'])
   slots={(int.from_bytes(wild[i:i+2],'little'),wild[i+2]) for i in range(1,37,3)}
   if result['remaining']!=r['stock']-1 or (mon['species'],mon['level']) not in slots or mon['size']!=100 or (result['caught'] and mon['owner']!=r['owner']):raise ValueError('Native result inconsistent with frozen attempt')
   result.update(outcome='native_captured_in_private_party' if result['caught'] else 'not_caught_unresolved',revision=r['revision'],balls_used=1,world_imported=False)
   with self.db:
    self.db.execute("UPDATE capture_jobs SET status='completed',result=? WHERE id=?",(json.dumps(result,sort_keys=True),job))
    if result['caught']:self.db.execute('INSERT INTO capture_results VALUES(?,?,?,?)',(job,actor,r['revision'],json.dumps(mon,sort_keys=True)))
   return result
  except Exception:
   with self.db:self.db.execute("UPDATE capture_jobs SET status='failed' WHERE id=?",(job,))
   raise

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--db',required=True)
 sub=parser.add_subparsers(dest='command',required=True)
 p=sub.add_parser('supply');p.add_argument('actor');p.add_argument('ball',type=int);p.add_argument('quantity',type=int)
 p=sub.add_parser('queue');p.add_argument('actor');p.add_argument('--companion',required=True);p.add_argument('--habitat',required=True)
 p.add_argument('--owner',required=True,type=int);p.add_argument('--name',required=True);p.add_argument('--ball',required=True,type=int);p.add_argument('--sha256',required=True)
 p=sub.add_parser('run');p.add_argument('job');p.add_argument('--engine',required=True);p.add_argument('--sha256',required=True);p.add_argument('--validated-native',action='store_true')
 p=sub.add_parser('show');p.add_argument('job')
 args=parser.parse_args();ledger=Ledger(args.db)
 try:
  if args.command=='supply':ledger.supply(args.actor,args.ball,args.quantity);result=dict(stock_set=True)
  elif args.command=='queue':result=dict(job=ledger.queue(args.actor,json.loads(Path(args.companion).read_text()),Path(args.habitat).read_bytes(),args.owner,args.name,args.ball,args.sha256))
  elif args.command=='run':result=ledger.execute(args.job,Engine(args.engine,args.sha256),validated_native=args.validated_native)
  else:
   row=ledger.db.execute('SELECT status,result FROM capture_jobs WHERE id=?',(args.job,)).fetchone()
   if not row:raise ValueError('Unknown job')
   result=dict(status=row[0],result=json.loads(row[1]) if row[1] else None)
  print(json.dumps(result,sort_keys=True))
 finally:ledger.close()
if __name__=='__main__':main()
