"""Local owner review of real campaign dependencies, without executing an agent."""
import json
from .battle_campaigns import inspect_document, publish, routes

OWNER = 'local_content_workshop'


def catalog(server):
    from .characters import records
    from .campaign_mechanisms import catalog as mechanisms
    cast = records(server.module_state)
    return dict(opponents=[dict(id=o['id'], point=[o[k] for k in ('group','num','x','y')],
        revision=o.get('region_revision'), team=cast[o['id']]['team']) for o in server.objects
        if o['id'] in cast and cast[o['id']]['status']=='active' and cast[o['id']]['team']],
        mechanisms=mechanisms(server))


def inspect(server, plan):
    document, encoded = inspect_document(server, dict(campaign=json.dumps(plan)))
    old = server.db.execute('SELECT actor,document FROM battle_campaigns WHERE id=?', (document['id'],)).fetchone()
    if old and tuple(old) != (OWNER, encoded):
        raise ValueError('This adventure ID is already owned or contains different content')
    from .characters import records
    cast = records(server.module_state)
    objects = {o['id']: o for o in server.objects}
    stages = []
    for name, node in document['nodes'].items():
        tasks = node.get('roles', {'all': node})
        details = []
        for role, task in tasks.items():
            if 'opponent' in task:
                obj = objects.get(task['opponent'])
                if not obj:
                    raise ValueError('Battle opponent is currently absent: ' + task['opponent'])
                details.append(dict(role=role, kind='battle', actor=obj['id'], point=[obj[k] for k in ('group','num','x','y')],
                    revision=obj.get('region_revision'), team=cast[obj['id']]['team'], preparation=task.get('preparation', {})))
            elif 'visit' in task:
                details.append(dict(role=role, kind='visit', **task['visit']))
            else:
                goal = task.get('expedition', task.get('mechanism'))
                network = server.module_state['world_object_networks'][goal['network']]
                members = [objects[k] for k in network['objects']]
                details.append(dict(role=role, kind='expedition' if 'expedition' in task else 'mechanism', **goal,
                    objects=[dict(id=o['id'], point=[o[k] for k in ('group','num','x','y')], revision=o.get('region_revision')) for o in members]))
        stages.append(dict(id=name, tasks=details, routes=routes(node), loss_routes=routes(node,'loss')))
    return dict(id=document['id'], title=document['title'], entry=document['entry'], stages=stages,
        shared_only=any('roles' in n for n in document['nodes'].values()), installed=bool(old))


def install(server, plan, reviewed):
    # The preview is not permission to change a now-different dependency.
    if inspect(server, plan) != reviewed:
        raise ValueError('Adventure dependencies changed. Preview again')
    with server.db:
        publish(server, OWNER, {}, dict(campaign=json.dumps(plan)))
    result = inspect(server, plan)
    if not result['installed']:
        raise ValueError('Adventure installation was not confirmed')
    return result
