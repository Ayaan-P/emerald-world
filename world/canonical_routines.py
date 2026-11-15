"""Durable quiet-world deliberation for already enrolled canonical actors.

A scheduled turn is an opportunity to decide, never evidence that anything
happened. Only the existing configured author worker can consume it.
"""
import json
import time
import uuid


def validate(routine):
    if routine is None:return
    if (type(routine) is not dict or set(routine)!={'interval_seconds'}
            or type(routine['interval_seconds']) is not int
            or not 60<=routine['interval_seconds']<=86400):
        raise ValueError('routine requires a 60..86400 second decision interval')


def setup(queue):
    queue.db.executescript('''
      CREATE TABLE IF NOT EXISTS canonical_routines(
        world TEXT, actor TEXT, next_due REAL, interval_seconds INTEGER,
        PRIMARY KEY(world,actor));
      CREATE TABLE IF NOT EXISTS canonical_routine_budget(
        world TEXT, actor TEXT, day INTEGER, attempts INTEGER,
        PRIMARY KEY(world,actor));
    ''')


def enqueue(queue,sub,character,*,defer=False):
    """Called inside the reaction queue transaction. No catch-up bursts."""
    routine=character.get('routine')
    if not character.get('canonical') or not routine or character.get('status')!='active':
        queue.db.execute('DELETE FROM canonical_routines WHERE world=? AND actor=?',(sub['world'],sub['id']))
        return None
    validate(routine);interval=routine['interval_seconds'];now=time.time();key=(sub['world'],sub['id'])
    row=queue.db.execute('SELECT next_due,interval_seconds FROM canonical_routines WHERE world=? AND actor=?',key).fetchone()
    if not row or row[1]!=interval or defer:
        due=max(row[0] if row else now,now+interval)
        queue.db.execute('INSERT OR REPLACE INTO canonical_routines VALUES(?,?,?,?)',(*key,due,interval))
        return None
    if now<row[0]:return None
    day=int(now//86400)
    budget=queue.db.execute('SELECT day,attempts FROM canonical_routine_budget WHERE world=? AND actor=?',key).fetchone()
    attempts=budget[1] if budget and budget[0]>=day else 0
    day=max(day,budget[0]) if budget else day
    if attempts>=8:return None
    identifier=uuid.uuid4().hex
    packet=dict(world_id=sub['world'],id=sub['id'],expected_version=character['version'],
        evidence=character['evidence'][-1],purpose=sub['purpose'],canonical=True,
        routine=dict(due=row[0],interval_seconds=interval))
    queue.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
        (identifier,sub['id'],'Reconsider your own current goal during this quiet-world decision window. Choose one supported action or wait. Elapsed time is not evidence of travel, learning, friendship, construction, or a victory.',
         'character','queued',now,json.dumps(packet)))
    queue.db.execute('UPDATE canonical_routines SET next_due=? WHERE world=? AND actor=?',(now+interval,*key))
    queue.db.execute('INSERT OR REPLACE INTO canonical_routine_budget VALUES(?,?,?,?)',(*key,day,attempts+1))
    return identifier


def check(packet,character):
    routine=packet.get('routine')
    if routine is None:return False
    current=character.get('routine')
    if (not character.get('canonical') or not current or type(routine) is not dict
            or set(routine)!={'due','interval_seconds'} or routine['interval_seconds']!=current['interval_seconds']
            or type(routine['due']) not in (int,float) or not 0<=routine['due']<=time.time()):
        raise ValueError('scheduled character decision changed or is not due')
    return True
