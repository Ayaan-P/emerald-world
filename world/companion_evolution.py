"""Host-only, default-off evolution of a benched world-owned individual.

The author cannot supply a new species. An exact validated native executable
chooses it, after an actual reconciled practice level increase. No player saves.
"""
import hashlib,json
from .companion_exchange import snapshot,identity
from .companion_practice import state as parse_state


def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS companion_evolutions(practice TEXT PRIMARY KEY,fingerprint TEXT,seq INTEGER)')


def source(server,actor,individual,practice):
 setup(server.db)
 current=snapshot(server,actor,individual)
 trained=current['trained']
 if not trained:raise ValueError('Evolution requires existing full native state')
 row=server.db.execute('SELECT actor,individual,seq FROM character_training_receipts WHERE job=?',(practice,)).fetchone()
 if not row or row[:2]!=(actor,individual):raise ValueError('Exact reconciled practice receipt required')
 events=server.memory.history(after=row[2]-1,limit=1)['events']
 event=events[0] if events else {}
 # The public record is evidence of practice, not a claimed battle victory.
 data=event.get('payload',event.get('data',{}))
 if event.get('seq')!=row[2] or event.get('event')!='character_practice_completed':raise ValueError('Practice history unavailable')
 if not data:data=event
 before=data.get('before_level');after=data.get('after_level')
 if type(before) is not int or type(after) is not int or not before<after or after!=trained['state']['level']:raise ValueError('Practice did not earn this level increase')
 if server.db.execute('SELECT 1 FROM companion_evolutions WHERE practice=?',(practice,)).fetchone():raise ValueError('Practice already used for evolution')
 result=dict(actor=actor,individual=individual,practice=practice,previous_level=before,current=current)
 result['token']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
 return result


def apply(server,request):
 setup(server.db)
 if set(request)!={'command','actor','individual','practice','token','engine','after'}:raise ValueError('Invalid evolution receipt')
 fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
 prior=server.db.execute('SELECT fingerprint,seq FROM companion_evolutions WHERE practice=?',(request['practice'],)).fetchone()
 if prior:
  if prior[0]!=fingerprint:raise ValueError('Evolution receipt changed')
  return dict(ok=True,seq=prior[1],already_applied=True)
 current=source(server,request['actor'],request['individual'],request['practice'])
 trained=current['current']['trained'];before=trained['state'];after=request['after']
 if current['token']!=request['token'] or trained['engine']!=request['engine']:raise ValueError('Evolution source or native build changed')
 if type(after) is not dict or set(after)!=set(before):raise ValueError('Full native state required')
 parse_state('STATE1 '+' '.join(str(after[k]) for k in ('size','species','level','personality','owner','exp','blob')))
 if any(after[k]!=before[k] for k in ('size','level','personality','owner','exp')) or after['species']==before['species']:raise ValueError('Evolution must preserve earned identity, level and experience')
 old=(before['species'],before['personality'],before['owner']);new=(after['species'],after['personality'],after['owner'])
 from .characters import records
 aliases=server.db.execute('SELECT actor,individual FROM character_companions WHERE species=? AND personality=? AND owner=?',old).fetchall()
 if any(any(m.get('individual')==key for m in records(server.module_state).get(actor,{}).get('team',[])) for actor,key in aliases):raise ValueError('All historical aliases must be off active teams')
 if server.db.execute('SELECT 1 FROM character_companions WHERE species=? AND personality=? AND owner=?',new).fetchone():raise ValueError('Target identity collides with existing individual')
 with server.db:
  # Update every historical alias; otherwise the old species could be reclaimed.
  server.db.execute('UPDATE character_companions SET species=? WHERE species=? AND personality=? AND owner=?',(after['species'],*old))
  for actor,key in aliases:
   raw=server.db.execute('SELECT member FROM character_companion_roster WHERE actor=? AND individual=?',(actor,key)).fetchone()
   if raw:
    member=json.loads(raw[0]);member['species']=after['species']
    server.db.execute('UPDATE character_companion_roster SET member=? WHERE actor=? AND individual=?',(json.dumps(member,sort_keys=True),actor,key))
   server.db.execute('UPDATE character_training SET state=? WHERE actor=? AND individual=?',(json.dumps(after,sort_keys=True),actor,key))
  server.db.execute('INSERT INTO companion_custody VALUES(?,?) ON CONFLICT(identity) DO UPDATE SET holder=excluded.holder',(identity(new),request['actor']))
  # Keep the old custody tombstone too: no old-species alias becomes unowned.
  server.db.execute('INSERT INTO companion_custody VALUES(?,?) ON CONFLICT(identity) DO UPDATE SET holder=excluded.holder',(identity(old),request['actor']))
  seq=server.memory.append('companion_evolved',dict(character_id=request['actor'],individual=request['individual'],practice=request['practice'],from_species=before['species'],to_species=after['species'],level=after['level'],basis='trusted_isolated_native_level_evolution'))
  server.db.execute('INSERT INTO companion_evolutions VALUES(?,?,?)',(request['practice'],fingerprint,seq));server.revision=seq
 return dict(ok=True,seq=seq)


def dispatch(ledger,engine,request,actor,individual,practice,*,validated_evolution=False):
 """One exact host job; retry pending reconciliation, never an uncertain runner."""
 if not validated_evolution:raise ValueError('Exact native evolution binary must pass linked QA before enabling')
 ledger.db.execute('CREATE TABLE IF NOT EXISTS evolution_jobs(practice TEXT PRIMARY KEY,actor TEXT,individual TEXT,status TEXT,payload TEXT)')
 job=ledger.db.execute('SELECT actor,individual,status,payload FROM evolution_jobs WHERE practice=?',(practice,)).fetchone()
 if job and job[:2]!=(actor,individual):raise ValueError('Practice job ownership changed')
 if job and job[2]=='completed':return dict(status='already_completed')
 if job and job[2]!='awaiting_reconciliation':raise ValueError('Interrupted or failed evolution needs host review; not replayed')
 if not job:
  response=request(dict(command='character_evolution_source',actor=actor,individual=individual,practice=practice))
  if not response.get('ok'):raise ValueError('Authority evolution source unavailable')
  src=response['source'];before=src['current']['trained'];local=ledger.get(actor,individual)
  if local['engine']!=engine.digest or before['engine']!=engine.digest or local['state']!=before['state']:raise ValueError('Host/world full state or engine differs')
  earned=ledger.db.execute('SELECT actor,individual,engine,status,source,result FROM jobs WHERE id=?',(practice,)).fetchone()
  if (not earned or earned[:4]!=(actor,individual,engine.digest,'completed') or json.loads(earned[5])!=before['state'] or json.loads(earned[4])['level']!=src['previous_level']):raise ValueError('Exact completed native practice job required')
  with ledger.db:ledger.db.execute('INSERT INTO evolution_jobs VALUES(?,?,?,?,NULL)',(practice,actor,individual,'running'))
  try:
   s=before['state'];after=engine.run(f"EVOLVE1 {s['size']} {src['previous_level']} {s['blob']}")
   if any(after[k]!=s[k] for k in ('size','level','exp','personality','owner')) or after['species']==s['species']:raise ValueError('Native evolution output inconsistent')
   payload=dict(command='character_evolution_apply',actor=actor,individual=individual,practice=practice,token=src['token'],engine=engine.digest,after=after)
   with ledger.db:ledger.db.execute("UPDATE evolution_jobs SET status='awaiting_reconciliation',payload=? WHERE practice=?",(json.dumps(payload,sort_keys=True),practice))
  except Exception:
   with ledger.db:ledger.db.execute("UPDATE evolution_jobs SET status='failed' WHERE practice=?",(practice,))
   raise
 else:payload=json.loads(job[3])
 local=ledger.get(actor,individual)
 earned=ledger.db.execute('SELECT result FROM jobs WHERE id=?',(practice,)).fetchone()
 if (engine.digest!=payload['engine'] or local['engine']!=engine.digest or not earned or local['state'] not in (json.loads(earned[0]),payload['after'])):raise ValueError('Pending evolution local state or binary changed')
 applied=request(payload)
 if not applied.get('ok'):raise ValueError('Native result retained; authority reconciliation refused')
 with ledger.db:
  ledger.db.execute('UPDATE companions SET revision=revision+1,state=? WHERE actor=? AND individual=? AND engine=?',(json.dumps(payload['after'],sort_keys=True),actor,individual,engine.digest))
  ledger.db.execute("UPDATE evolution_jobs SET status='completed' WHERE practice=?",(practice,))
 return dict(status='evolved',world_receipt=applied['seq'],individual=individual)


def main():
 import argparse
 from .companion_practice import Ledger,Engine
 from . import gm
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('db','engine','sha256','socket','actor','individual','practice'):p.add_argument('--'+name,required=True)
 p.add_argument('--validated-evolution',action='store_true',help='Attest exact binary passed isolated evolution QA; disabled otherwise')
 a=p.parse_args();ledger=Ledger(a.db)
 try:print(json.dumps(dispatch(ledger,Engine(a.engine,a.sha256),lambda body:gm.admin_request(a.socket,body,30),a.actor,a.individual,a.practice,validated_evolution=a.validated_evolution),sort_keys=True))
 finally:ledger.close()
if __name__=='__main__':main()
