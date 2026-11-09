"""Private, save-bound native partner encounter reports. Never reward authority."""
import time
from .canonical_memory import enabled

# Exact Expansion f5b45730 include/constants/battle.h outcomes for ordinary wilds.
OUTCOMES={1:'won',2:'lost',3:'drew',4:'ran',5:'player teleported',6:'wild Pokemon fled',7:'caught',9:'forfeited',10:'wild Pokemon teleported'}

def install(db):
 db.execute('CREATE TABLE IF NOT EXISTS canonical_partner_memory(trainer TEXT,actor TEXT,run TEXT,outcome INTEGER,reported REAL)')

def admit(server,conn,run):
 conn.pop('cast_partner_pending',None)
 if enabled(server,conn['id'],'canon_steven'):
  conn['cast_partner_pending']=dict(run=run,expires=time.monotonic()+1800)

def finish(server,conn,run,key,value):
 if key!='steven' or value not in {str(k) for k in OUTCOMES}:raise ValueError('Invalid partner encounter report.')
 pending=conn.get('cast_partner_pending')
 if not pending or pending['run']!=run or conn.get('core_active_run')!=run or pending['expires']<time.monotonic():
  raise ValueError('No matching partner invitation in this connection and save.')
 conn.pop('cast_partner_pending',None) # At most one report, no reward or public event.
 if not enabled(server,conn['id'],'canon_steven'):return dict(ok=True)
 with server.db:
  server.db.execute('INSERT INTO canonical_partner_memory VALUES(?,?,?,?,?)',(conn['id'],'canon_steven',run,int(value),time.time()))
  server.db.execute('DELETE FROM canonical_partner_memory WHERE trainer=? AND actor=? AND rowid NOT IN (SELECT rowid FROM canonical_partner_memory WHERE trainer=? AND actor=? ORDER BY rowid DESC LIMIT 16)',(conn['id'],'canon_steven',conn['id'],'canon_steven'))
 return dict(ok=True)

def context(server,trainer,actor,run):
 return [dict(outcome=OUTCOMES[n],basis='client_reported_native_partner_cleanup',limits='An unverified game-client encounter report, not individual performance, friendship, earned NPC training or a reward claim.')
         for (n,) in server.db.execute('SELECT outcome FROM canonical_partner_memory WHERE trainer=? AND actor=? AND run=? ORDER BY rowid DESC LIMIT 4',(trainer,actor,run))]
