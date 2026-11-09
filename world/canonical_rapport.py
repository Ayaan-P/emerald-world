"""Standing, save-specific private interpretation of actual conversation choices.

No background model startup, public author access, or passive-greeting loop.
"""
import json,secrets,time


def install(db):
    # Earlier candidates admitted one outstanding reply per trainer/actor.
    # Preserve rows atomically while making simultaneous save scopes independent.
    schema=db.execute("SELECT sql FROM sqlite_master WHERE name='canonical_reflections'").fetchone()
    if schema and 'UNIQUE(trainer,actor)' in ''.join(schema[0].split()):
        db.execute('SAVEPOINT rapport_migration')
        try:
            db.execute('ALTER TABLE canonical_reflections RENAME TO canonical_reflections_single_actor')
            db.execute('CREATE TABLE canonical_reflections(id TEXT PRIMARY KEY,trainer TEXT,actor TEXT,run TEXT,fingerprint TEXT,context TEXT,status TEXT,created REAL,lease TEXT,reply TEXT,interpretation TEXT,version INTEGER,UNIQUE(trainer,actor,run))')
            db.execute('INSERT INTO canonical_reflections SELECT * FROM canonical_reflections_single_actor')
            db.execute('DROP TABLE canonical_reflections_single_actor')
            db.execute('RELEASE rapport_migration')
        except Exception:
            db.execute('ROLLBACK TO rapport_migration');db.execute('RELEASE rapport_migration');raise
    db.executescript('''
      CREATE TABLE IF NOT EXISTS canonical_rapport(
        trainer TEXT,actor TEXT,run TEXT,grant_id TEXT,last_seq INTEGER,day TEXT,used INTEGER,
        PRIMARY KEY(trainer,actor,run));
      CREATE TABLE IF NOT EXISTS canonical_rapport_jobs(id TEXT PRIMARY KEY,grant_id TEXT);
    ''')


def grant(server,trainer,actor,run):
    return server.db.execute('SELECT grant_id,last_seq,day,used FROM canonical_rapport WHERE trainer=? AND actor=? AND run=?',(trainer,actor,run)).fetchone()


def snapshot(server,trainer,actor,run,request):
    from .canonical_reflection import snapshot as base_snapshot
    if server.db.execute('SELECT 1 FROM canonical_questions WHERE id=?',(request,)).fetchone():
        from .canonical_questions import snapshot as question_snapshot
        return question_snapshot(server,trainer,actor,run,request)
    automatic=server.db.execute('SELECT grant_id FROM canonical_rapport_jobs WHERE id=?',(request,)).fetchone()
    if not automatic:return base_snapshot(server,trainer,actor,run)
    consent=grant(server,trainer,actor,run)
    if not consent or consent[0]!=automatic[0]:raise ValueError('Standing private grant was withdrawn')
    return base_snapshot(server,trainer,actor,run,decision_only=True)


def stop(server,trainer,actor,run=None):
    params=[trainer,actor];suffix=''
    if run is not None:suffix=' AND run=?';params.append(run)
    ids=[r[0] for r in server.db.execute('SELECT grant_id FROM canonical_rapport WHERE trainer=? AND actor=?'+suffix,params)]
    for identity in ids:
        server.db.execute('DELETE FROM canonical_reflections WHERE id IN (SELECT id FROM canonical_rapport_jobs WHERE grant_id=?)',(identity,))
        server.db.execute('DELETE FROM canonical_rapport_jobs WHERE grant_id=?',(identity,))
    server.db.execute('DELETE FROM canonical_rapport WHERE trainer=? AND actor=?'+suffix,params)


def enable(server,trainer,actor,run):
    # Reconfirmation does not reset a same-day usage count.
    old=grant(server,trainer,actor,run)
    if old is None and server.db.execute('SELECT count(*) FROM canonical_rapport WHERE trainer=? AND actor=?',(trainer,actor)).fetchone()[0]>=16:
        raise ValueError('Automatic response save limit reached. Stop an old save grant or forget this actor first.')
    day=time.strftime('%Y-%m-%d',time.gmtime())
    stop(server,trainer,actor,run)
    server.db.execute('INSERT INTO canonical_rapport VALUES(?,?,?,?,?,?,?)',
                      (trainer,actor,run,secrets.token_hex(16),0,day,old[3] if old and old[2]==day else 0))
    return enqueue(server,trainer,actor,run,initial=True)


def enqueue(server,trainer,actor,run,*,initial=False):
    from .canonical_memory import enabled
    from .canonical_reflection import snapshot as base_snapshot
    consent=grant(server,trainer,actor,run)
    if not consent or not enabled(server,trainer,actor):return False
    latest=server.db.execute('SELECT coalesce(max(seq),0) FROM canonical_decision_memory WHERE trainer=? AND actor=? AND run=?',(trainer,actor,run)).fetchone()[0]
    if not initial and latest<=consent[1]:return False
    old=server.db.execute('SELECT status FROM canonical_reflections WHERE trainer=? AND actor=? AND run=?',(trainer,actor,run)).fetchone()
    if old and old[0] in ('pending','running'):return False # Never mutate an in-flight model grant.
    day=time.strftime('%Y-%m-%d',time.gmtime());used=consent[3] if consent[2]==day else 0
    if used>=4:
        # Do not catch up expired decisions tomorrow without a new player action.
        server.db.execute('UPDATE canonical_rapport SET last_seq=? WHERE trainer=? AND actor=? AND run=?',(latest,trainer,actor,run))
        return False
    try:_,fingerprint,context=base_snapshot(server,trainer,actor,run,decision_only=True)
    except ValueError:return False
    identifier=secrets.token_hex(16)
    server.db.execute('DELETE FROM canonical_rapport_jobs WHERE id IN (SELECT id FROM canonical_reflections WHERE trainer=? AND actor=? AND run=?)',(trainer,actor,run))
    server.db.execute('DELETE FROM canonical_reflections WHERE trainer=? AND actor=? AND run=?',(trainer,actor,run))
    server.db.execute('INSERT INTO canonical_reflections VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                      (identifier,trainer,actor,run,fingerprint,json.dumps(context,sort_keys=True),'pending',time.time(),None,None,None,None))
    server.db.execute('INSERT INTO canonical_rapport_jobs VALUES(?,?)',(identifier,consent[0]))
    server.db.execute('UPDATE canonical_rapport SET last_seq=?,day=?,used=? WHERE trainer=? AND actor=? AND run=?',(latest,day,used+1,trainer,actor,run))
    return True


def reconsider(server,trainer,actor,run,request):
    # A new committed choice during generation may supersede the old summary.
    # Only a NEW decision sequence can enqueue another job, never an API failure.
    if server.db.execute('SELECT 1 FROM canonical_rapport_jobs WHERE id=?',(request,)).fetchone():
        enqueue(server,trainer,actor,run)
