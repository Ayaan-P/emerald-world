"""Cast intentions execute explicitly assigned shared story actions, not player turns."""
import time
import json
from .opportunities import identity


def validate(action):
    if action is None:return
    if type(action) is not dict or set(action)!={'pack','scene','choice','place','revision'}:raise ValueError('World action needs exact pack, scene, choice, place and revision.')
    for key in ('pack','scene','choice'):identity(action[key])
    if type(action['place']) is not str or type(action['revision']) is not int or action['revision']<0:raise ValueError('Invalid world action location or revision.')


def step(server,*,now=None):
    now=time.monotonic() if now is None else now
    if server.job is not None or server.deployment is not None or now<getattr(server,'cast_world_action_next',0):return None
    server.cast_world_action_next=now+5
    from .canonical_cast import records
    waiting=None
    for actor,row in sorted(records(server.module_state).items()):
        action=row.get('world_action')
        if not action:continue
        for task in row.get('intentions',[]):
            if task['kind']!='world_action' or task['target']!=action['pack']:continue
            if server.db.execute('SELECT 1 FROM canonical_intent_receipts WHERE actor=? AND intention=?',(actor,task['id'])).fetchone():continue
            if server.db.execute('SELECT count(*) FROM canonical_intent_receipts WHERE actor=?',(actor,)).fetchone()[0]>=8:continue
            available=server.opportunities.actor_actions(actor)
            if not any(all(o[k]==action[k] for k in ('pack','scene','place','revision'))
                       and action['choice'] in o['choices'] for o in available):
                try:seq=obstructed(server,actor,row,task,action)
                except ValueError:
                    waiting=dict(status='waiting',actor=actor,intention=task['id'],reason='Could not persist the action observation.')
                    continue
                waiting=dict(status='waiting',actor=actor,intention=task['id'],
                             reason='Actor action is stale, unavailable or not assigned to this actor.',seq=seq)
                continue
            try:
                with server.db:
                    outcome=server.opportunities.actor_choose(actor,action)
                    seq=server.memory.append('canonical_world_action_committed',dict(character_id=actor,intention=task['id'],
                        character_version=row['version'],pack=action['pack'],scene=action['scene'],choice=action['choice'],
                        revision=outcome['revision'],changes=outcome['changes'],result=outcome['text'],based_on=row['evidence'],
                        places=['native:'+action['place']],publication='public_cast_world_action',
                        outcome='shared_story_state_committed',limits='Abstract shared story decision, not physical travel, native inventory, rewards or campaign progression.'))
                    server.db.execute('INSERT INTO canonical_intent_receipts VALUES(?,?,?)',(actor,task['id'],seq))
                server.revision=seq
                return dict(status='completed',actor=actor,intention=task['id'],seq=seq)
            except ValueError as exc:
                waiting=dict(status='waiting',actor=actor,intention=task['id'],reason=str(exc))
    return waiting


def relevant(event,identity,row):
    if obstruction_relevant(event,identity):return True
    return (event.get('event')=='canonical_world_action_committed' and event.get('publication')=='public_cast_world_action'
            and event.get('outcome')=='shared_story_state_committed'
            and (event.get('character_id')==identity or bool(set(event.get('places',[]))&set(row.get('places',[])))))


def obstructed(server,actor,row,task,action):
    """One factual failed-admission observation per exact retained request.

    This is not a failed battle, a broken promise, or blame attributed to anyone.
    Only public actor choices are inspected. Transaction/receipt errors are not
    interpreted as world events, and a later available request may still run.
    """
    document=json.dumps(action,sort_keys=True,separators=(',',':'))
    old=server.db.execute('SELECT seq FROM canonical_action_obstructions WHERE actor=? AND intention=? AND action=?',
                         (actor,task['id'],document)).fetchone()
    if old:return old[0]
    with server.db:
        seq=server.memory.append('canonical_action_obstructed',dict(character_id=actor,
            character_version=row['version'],intention=task['id'],action=action,
            places=['native:'+action['place']],publication='public_cast_action_observation',
            outcome='assigned_action_unavailable',based_on=row['evidence'],
            limits='The exact retained public action was unavailable when checked. No action completed, cause or blame inferred. Reconsider current available actions or withdraw; do not invent success.'))
        server.db.execute('INSERT INTO canonical_action_obstructions VALUES(?,?,?,?)',(actor,task['id'],document,seq))
    server.revision=seq
    return seq


def obstruction_relevant(event,actor):
    return (event.get('event')=='canonical_action_obstructed' and event.get('character_id')==actor
        and event.get('publication')=='public_cast_action_observation'
        and event.get('outcome')=='assigned_action_unavailable')
