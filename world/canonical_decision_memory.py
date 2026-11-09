"""Private facts about one's own shared decisions, never inferred agreement."""
import json
from .canonical_memory import enabled


def install(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS canonical_decision_pending(
        session TEXT,trainer TEXT,actor TEXT,run TEXT,
        PRIMARY KEY(session,trainer));
      CREATE TABLE IF NOT EXISTS canonical_decision_memory(
        session TEXT,trainer TEXT,actor TEXT,run TEXT,seq INTEGER,fact TEXT,
        PRIMARY KEY(session,trainer));
    ''')


def bind(server,conn,actor,session):
    # Bind when this player actually acts, never borrow the speaker's lineage.
    run=conn.get('core_active_run')
    server.db.execute('DELETE FROM canonical_decision_pending WHERE session=? AND trainer=?',(session,conn['id']))
    if run and enabled(server,conn['id'],actor):
        server.db.execute('INSERT INTO canonical_decision_pending VALUES(?,?,?,?)',(session,conn['id'],actor,run))


def commit(server,session,proposal,choice,advice,seq):
    actor=session['actor'];identifier=session['id']
    rows=server.db.execute('SELECT trainer,run FROM canonical_decision_pending WHERE session=? AND actor=?',(identifier,actor)).fetchall()
    for trainer,run in rows:
        if not enabled(server,trainer,actor):continue
        speaker=trainer==session['speaker']
        if not speaker and trainer not in advice:continue
        fact=dict(question=proposal['question'],role='speaker' if speaker else 'listener',
                  own_answer=proposal['options'][choice if speaker else advice[trainer]],
                  speaker_answer=proposal['options'][choice],
                  limits='An explicit fictional conversation choice or suggestion, not agreement, personality or an accomplished activity.')
        server.db.execute('INSERT OR IGNORE INTO canonical_decision_memory VALUES(?,?,?,?,?,?)',
                          (identifier,trainer,actor,run,seq,json.dumps(fact,sort_keys=True)))
        server.db.execute('''DELETE FROM canonical_decision_memory WHERE trainer=? AND actor=? AND rowid NOT IN
          (SELECT rowid FROM canonical_decision_memory WHERE trainer=? AND actor=? ORDER BY seq DESC LIMIT 16)''',(trainer,actor,trainer,actor))
    server.db.execute('DELETE FROM canonical_decision_pending WHERE session=?',(identifier,))


def context(server,trainer,actor,run):
    return [json.loads(row[0]) for row in server.db.execute('''SELECT fact FROM canonical_decision_memory
      WHERE trainer=? AND actor=? AND run=? ORDER BY seq DESC LIMIT 4''',(trainer,actor,run))]
