"""Cast intentions execute explicitly assigned shared story actions, not player turns."""
import time
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
    return (event.get('event')=='canonical_world_action_committed' and event.get('publication')=='public_cast_world_action'
            and event.get('outcome')=='shared_story_state_committed'
            and (event.get('character_id')==identity or bool(set(event.get('places',[]))&set(row.get('places',[])))))
