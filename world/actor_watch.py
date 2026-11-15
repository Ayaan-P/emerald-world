"""Wait on real locally observable conditions without repeated author calls."""
import json
from .actor_observation import observe


def start(server, actor, row, args):
    from .actor_runtime import Pending
    if set(args)!={'observation','target','condition'} or type(args['observation']) is not int or args['condition'] not in ('present','changed') or type(args['target']) is not str:
        raise ValueError('Supply own observation receipt, target identity and present/changed condition')
    saved=server.db.execute("SELECT result FROM actor_tool_receipts WHERE actor=? AND seq=? AND status='succeeded'",(actor,args['observation'])).fetchone()
    if not saved:raise ValueError('Own successful local observation required')
    baseline=json.loads(saved[0])
    if not all(k in baseline for k in ('entities','radius','revision','x','y','cells')):raise ValueError('Receipt is not a local observation')
    prior=next((e for e in baseline['entities'] if e['id']==args['target']),None)
    if args['condition']=='changed' and prior is None:raise ValueError('Changed requires an actually observed entity')
    if not any(o['id']==args['target'] for o in server.objects) or args['target']==actor:raise ValueError('Target must be an existing other world object')
    pending=dict(target=args['target'],condition=args['condition'],prior=prior,radius=baseline['radius'],revision=baseline['revision'],x=baseline['x'],y=baseline['y'])
    result=poll(server,actor,row,pending)
    return result if result is not None else Pending(pending,lambda:None)


def poll(server, actor, row, pending):
    current=observe(server,actor,row,dict(radius=pending['radius']))
    if any(current[k]!=pending[k] for k in ('revision','x','y')):raise ValueError('Observer moved or geometry changed; inspect and choose a new watch')
    entity=next((e for e in current['entities'] if e['id']==pending['target']),None)
    if entity is None or (pending['condition']=='changed' and entity==pending['prior']):return None
    return dict(outcome='local_condition_observed',target=entity['id'],condition=pending['condition'],revision=current['revision'],observed_revision=current['observed_revision'],entity=entity,
                semantics='Actual bounded local observation; not a meeting, consent, global tracking or inferred absence.')
