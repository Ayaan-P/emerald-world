"""A committed intention can prompt planning, never prove its own accomplishment.

Uses the shared eight-turn/day quiet deliberation budget. No timer, new worker,
physical activity, model result or receipt is synthesized here.
"""
import time


def goal_event(event,identity):
    after=event.get('after');before=event.get('before') or {}
    return (event.get('event')=='canonical_actor_changed'
        and event.get('character_id')==identity
        and event.get('source')=='authored_public_activity_interpretation'
        and type(after) is dict and type(before) is dict
        and type(after.get('version')) is int and after['version']>=1
        and type(after.get('goal')) is str and bool(after['goal'])
        and before.get('goal')!=after['goal'])


def relevant(event,identity,row):
    return goal_event(event,identity) and event['after']['version']==row.get('version') and event['after']['goal']==row.get('goal')


def evidence(event,identity,row):
    # Only the immediate next authored revision may plan from this commitment.
    # Further decisions need their own new goal or actual action/outcome evidence.
    return goal_event(event,identity) and row.get('version')==event['after']['version']+1


def reserve(queue,world,identity):
    """Caller holds queue transaction; shares budget with existing quiet turns."""
    day=int(time.time()//86400)
    old=queue.db.execute('SELECT day,attempts FROM canonical_routine_budget WHERE world=? AND actor=?',(world,identity)).fetchone()
    attempts=old[1] if old and old[0]>=day else 0
    day=max(day,old[0]) if old else day
    if attempts>=8:return False
    queue.db.execute('INSERT OR REPLACE INTO canonical_routine_budget VALUES(?,?,?,?)',(world,identity,day,attempts+1))
    return True
