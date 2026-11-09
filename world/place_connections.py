"""Author paired physical cave connections through normal object admission."""
import copy
import hashlib
import inspect
import json


def apply_connection(result, request):
    import copy
    result = copy.deepcopy(result)
    saved = result['state'].setdefault('world_place_connections', {})
    for obj in request['objects']:
        if not any(o['id'] == obj['id'] for o in result.get('objects', [])):
            result.setdefault('objects', []).append(copy.deepcopy(obj))
    saved.setdefault(request['id'], copy.deepcopy(request))
    return result


def connect(server, actor, row, args):
    from .actor_runtime import Pending
    from .cave_links import destination
    from .region_characters import validate_region_objects
    if set(args) != {'source', 'source_revision', 'target', 'target_revision'}:
        raise ValueError('Supply two exact opened place IDs and revisions')
    caves = [destination(server, args[k], args[k + '_revision']) for k in ('source', 'target')]
    if caves[0].identity == caves[1].identity:
        raise ValueError('Choose distinct destinations')
    if server.job is not None or server.deployment is not None or not server.candidate:
        raise ValueError('Current idle mechanic source required')
    pair = sorted([args['source_revision'], args['target_revision']])
    identity = hashlib.sha256(json.dumps(pair).encode()).hexdigest()
    saved = server.module_state.get('world_place_connections', {}).get(identity)
    if saved is not None:
        installed = server.db.execute("SELECT 1 FROM sqlite_master WHERE name='cave_links'").fetchone()
        if installed and all(server.db.execute('SELECT 1 FROM cave_links WHERE object=?',
                                              (link['object'],)).fetchone() for link in saved['links']):
            raise ValueError('This pair already has an authored connection')
        # Resume admitted objects after a failed installation/receipt, never respawn.
        return Pending(copy.deepcopy(saved), lambda: None)
    objects = []
    for i, cave in enumerate(caves):
        label = server.db.execute('SELECT label FROM generated_area_archive WHERE identity=?',
                                  (caves[1-i].identity,)).fetchone()[0] or 'Cave'
        text = ('To ' + ''.join(c if c.isascii() and (c.isalnum() or c in ' .-') else ' ' for c in label))[:28]
        obj = dict(id='passage_' + identity[:14] + str(i), kind='prop', portable=False,
                   group=server.cave_map[0], num=server.cave_map[1], region_revision=cave.identity,
                   gfx=0, text=text)
        if any(o['id'] == obj['id'] for o in server.objects):
            raise ValueError('Connection identity collision')
        # Choose a reachable, non-sealing tile near the entrance, not a warp.
        candidates = sorted(((x,y) for y in range(1,30) for x in range(1,30)
                             if cave.walkable(x,y)), key=lambda p:(p[0]+p[1],p[1],p[0]))
        for x,y in candidates:
            obj.update(x=x,y=y)
            proposed = dict(state=server.module_state, objects=server.objects+objects+[obj], tiles=[])
            try:
                server._validated(proposed)
                validate_region_objects(server, proposed['objects'], proposed['state'])
            except ValueError:
                continue
            objects.append(copy.deepcopy(obj))
            break
        else:
            raise ValueError('No safe connection placement; preserve population, players and routes')
    request = dict(id=identity, objects=objects, links=[
        dict(object=objects[i]['id'], source=caves[i].identity,
             place=args['target' if i==0 else 'source'], destination=caves[1-i].identity)
        for i in range(2)])
    helper = inspect.getsource(apply_connection).replace('def apply_connection(', 'def _connection_'+identity[:16]+'(', 1)
    suffix=identity[:16]
    source = (server.candidate.source+'\n'+f'_connection_previous_{suffix}=update\n'+helper+'\n'+
              f'def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy({server.module_state!r})\n    return _connection_{suffix}(_connection_previous_{suffix}(context,state),{request!r})\n')
    if len(source.encode()) > 256*1024:
        raise ValueError('Consolidate mechanic source before another connection')
    proposed=apply_connection(dict(state=server.module_state,objects=server.objects,tiles=[]),request)
    server._validated(proposed)
    sha=hashlib.sha256(source.encode()).hexdigest()
    path=server.runtime.candidates/('connection_'+sha+'.py')
    try:
        with path.open('x') as stream:stream.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Connection candidate conflict')
    def dispatch():server.deployment=(None,path,None)
    return Pending(request,dispatch)


def poll(server, actor, row, pending):
    from .cave_links import destination
    from .region_characters import validate_region_objects
    if server.module_state.get('world_place_connections',{}).get(pending['id']) != pending:
        raise ValueError('Connection population was not admitted')
    for obj in pending['objects']:
        if next((o for o in server.objects if o['id']==obj['id']),None)!=obj:
            raise ValueError('Connection object changed before installation')
    validate_region_objects(server,server.objects,server.module_state)
    for link in pending['links']:destination(server,link['place'],link['destination'])
    server.db.execute('CREATE TABLE IF NOT EXISTS cave_links(object TEXT PRIMARY KEY,source TEXT,place TEXT,destination TEXT)')
    for link in pending['links']:
        old=server.db.execute('SELECT source,place,destination FROM cave_links WHERE object=?',(link['object'],)).fetchone()
        values=tuple(link[k] for k in ('source','place','destination'))
        if old and tuple(old)!=values:raise ValueError('Connection was independently changed')
        server.db.execute('INSERT OR IGNORE INTO cave_links VALUES(?,?,?,?)',(link['object'],*values))
    return dict(outcome='paired_cave_connection_installed',connection=pending['id'],links=pending['links'],
                limits='Existing native A-button link consent and transfer; no actor or player travel asserted')
