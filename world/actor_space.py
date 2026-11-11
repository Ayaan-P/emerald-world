"""Add compiler-generated connected space without erasing the existing place."""
import hashlib
import json


def extend(server, actor, row, args):
    from .actor_runtime import Committed, _receipt
    from .characters import records
    from .character_rebinding import prepare
    from .route_landscape import compile_plan
    from .shared_cave import SharedCave
    if set(args) != {'revision', 'blueprint'} or type(args['blueprint']) is not str or len(args['blueprint']) > 800:
        raise ValueError('Supply exact revision and a bounded route blueprint JSON string')
    try:
        blueprint = json.loads(args['blueprint'])
    except (ValueError, TypeError):
        raise ValueError('Invalid route blueprint JSON')
    proposed, report = compile_plan(blueprint)
    obj = next((o for o in server.objects if o['id'] == actor), None)
    character = records(server.module_state).get(actor)
    revision = args['revision']
    if not character or character['status'] != 'active' or not obj or obj.get('region_revision') != revision:
        raise ValueError('Actor must be active in the exact place being extended')
    if not server.archive_generated_areas or not server.shared_cave or server.shared_cave.identity != revision:
        raise ValueError('Only the active archived shared place can be extended')
    saved = server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
    if not saved or hashlib.sha256(saved[0]).hexdigest() != revision:
        raise ValueError('Durable geometry changed')
    old = SharedCave(saved[0]); generated = SharedCave(proposed)
    if old.version != 16:
        raise ValueError('Only plain XL geometry; wildlife and other format data must be preserved')
    # A reservation is a no-build area, not permission to remove old floor.
    for x, y, width, height in blueprint['reservations']:
        if any(old.walkable(xx, yy) for xx in range(x, x+width) for yy in range(y, y+height)):
            raise ValueError('Reservations cannot overwrite existing walkable space')
    rows = [bytearray(r) for r in old._rows]
    opened = 0
    for y in range(1, old.side-1):
        for x in range(1, old.side-1):
            if generated.walkable(x, y) and not old.walkable(x, y):
                rows[y][x] = ord('.'); opened += 1
    if not opened:
        raise ValueError('Blueprint adds no new navigable space')
    blob = saved[0][:8] + b''.join(rows)
    candidate = SharedCave(blob)  # Native format, endpoints and connectivity validator.
    continuation = prepare(server, revision, candidate.identity)
    execution = getattr(server, 'actor_tool_execution', None)
    if not execution or execution[0] != actor:
        raise ValueError('Space authoring requires the durable plan executor')
    _, record, plan, step = execution
    result = dict(previous_revision=revision, revision=candidate.identity, opened_tiles=opened,
                  landmarks=report['landmarks'], routes=len(report['routes']),
                  outcome='connected_space_committed')
    committed = []
    def persist(identity, place):
        if identity != candidate.identity:
            raise ValueError('Unexpected geometry commit')
        result['place_id'] = place
        committed.append(_receipt(server, actor, record, plan, step, 'succeeded', result))
    label = server.db.execute('SELECT label FROM generated_area_archive WHERE identity=?', (revision,)).fetchone()[0]
    server._replace_cave(blob, label=label, previous_revision=revision,
        expected_world_id=server.memory.world_id,
        expected_sequence=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0],
        history_evidence=list(row['evidence']), character_continuation=continuation,
        actor_tool_commit=persist)
    return Committed(committed[0], result)
