"""Explicit player-authored private dialogue turns, never public world author input."""
import hashlib,json,re,secrets,time

def install(db):
 db.execute('CREATE TABLE IF NOT EXISTS canonical_questions(id TEXT PRIMARY KEY,trainer TEXT,actor TEXT,run TEXT,context TEXT)')

def snapshot(server,trainer,actor,run,identifier):
 from .canonical_memory import enabled
 from .canonical_cast import records
 row=server.db.execute('SELECT context FROM canonical_questions WHERE id=? AND trainer=? AND actor=? AND run=?',(identifier,trainer,actor,run)).fetchone()
 if not row or not enabled(server,trainer,actor):raise ValueError('Private question is no longer available.')
 context=json.loads(row[0]);current=records(server.module_state).get(actor)
 if not current or current['version']!=context['current_version']:raise ValueError('Character changed after the question.')
 if not server.db.execute('SELECT 1 FROM canonical_encounters WHERE trainer=? AND actor=? AND run=?',(trainer,actor,run)).fetchone():raise ValueError('Save encounter memory is no longer available.')
 return run,hashlib.sha256(json.dumps([run,context],sort_keys=True).encode()).hexdigest(),context

def ask(server,conn,run,key,encoded):
 from .canonical_cast import BINDINGS,records,check_actor_location
 from .canonical_memory import enabled
 actor='canon_'+key
 if actor not in BINDINGS or conn.get('core_active_run')!=run:raise ValueError('Talk to this original actor in the current save first.')
 reached=conn.get('canonical_location') or {};row=records(server.module_state).get(actor)
 if not row or reached.get('actor')!=actor or reached.get('run')!=run or reached.get('version')!=row['version'] or reached.get('expires',0)<time.monotonic():raise ValueError('Talk to the current original actor before asking.')
 check_actor_location(server,conn,actor)
 if not enabled(server,conn['id'],actor):raise ValueError('Enable this actor private encounter memory before asking.')
 if not re.fullmatch('[0-9a-f]{2,192}',encoded) or len(encoded)%2:raise ValueError('Question must be 1..96 plain ASCII characters.')
 words=bytes.fromhex(encoded).decode('ascii',errors='replace')
 if not words.strip() or any(not 32<=ord(c)<=126 for c in words):raise ValueError('Question must be plain ASCII.')
 # Do not replace an in-flight or unseen answer, including one from standing consent.
 if server.db.execute("SELECT 1 FROM canonical_reflections WHERE trainer=? AND actor=? AND run=? AND status IN ('pending','running','ready')",(conn['id'],actor,run)).fetchone():raise ValueError('A private answer is pending. Talk again or use reflect cancel before asking another question.')
 from .canonical_reflection import snapshot as base
 _,_,context=base(server,conn['id'],actor,run,decision_only=True)
 context['player_words']=words
 context['dialogue_scope']='Snapshot at this explicit private question. Not permission to change game state or disclose other players.'
 identifier=secrets.token_hex(16)
 with server.db:
  server.db.execute('DELETE FROM canonical_questions WHERE trainer=? AND actor=? AND run=?',(conn['id'],actor,run))
  server.db.execute('INSERT INTO canonical_questions VALUES(?,?,?,?,?)',(identifier,conn['id'],actor,run,json.dumps(context,sort_keys=True)))
  _,fingerprint,context=snapshot(server,conn['id'],actor,run,identifier)
  server.db.execute('DELETE FROM canonical_reflections WHERE trainer=? AND actor=? AND run=?',(conn['id'],actor,run))
  server.db.execute('INSERT INTO canonical_reflections VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(identifier,conn['id'],actor,run,fingerprint,json.dumps(context,sort_keys=True),'pending',time.time(),None,None,None,None))
 return dict(ok=True)


def cancel(server,trainer,actor,run):
 server.db.execute('DELETE FROM canonical_reflections WHERE id IN (SELECT id FROM canonical_questions WHERE trainer=? AND actor=? AND run=?)',(trainer,actor,run))
 server.db.execute('DELETE FROM canonical_questions WHERE trainer=? AND actor=? AND run=?',(trainer,actor,run))
