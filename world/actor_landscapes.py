"""Author real outdoor geometry using the existing shared XL destination."""
import json


def create(server, actor, row, args):
    from .actor_runtime import Committed, _receipt
    from .cave_blueprint import proposal_from_blueprint
    from .xl_wilds import encode
    from .route_landscape import compile_plan
    from .shared_cave import SharedCave
    if not {'label', 'layout', 'blueprint'} <= set(args) or set(args)-{'label','layout','blueprint','paint'}:
        raise ValueError('Supply label, layout and blueprint')
    label = args['label']
    if type(label) is not str or not 1 <= len(label) <= 20 or not label.strip() or any(not(c.isascii() and (c.isalnum() or c in " .,'!?-")) for c in label):
        raise ValueError('Use a literal 1..20 character label')
    if type(args['blueprint']) is not str or len(args['blueprint']) > 800:
        raise ValueError('Use bounded layout JSON')
    try:
        blueprint = json.loads(args['blueprint'])
    except (ValueError, TypeError):
        raise ValueError('Invalid layout JSON')
    if args['layout'] == 'clearings':
        blob, generated = compile_plan(blueprint)
        report = dict(landmarks=generated['landmarks'], routes=len(generated['routes']))
    elif args['layout'] == 'connected_shapes':
        blob = encode(proposal_from_blueprint(blueprint, side=127))
        report = {'style': blueprint.get('style', 'rooms')}
    else:
        raise ValueError('Supported layouts: clearings, connected_shapes')
    if 'paint' in args:
        if type(args['paint']) is not str or len(args['paint']) > 2000: raise ValueError('Use bounded paint JSON')
        try: paint=json.loads(args['paint'])
        except (ValueError,TypeError): raise ValueError('Invalid paint JSON') from None
        from .shared_outdoor_palette import encode as encode_painted
        cells=blob[8:]; proposal=dict(rows=[cells[i*127:(i+1)*127].decode('ascii') for i in range(127)],spawn=[1,1],exit=[125,125])
        blob=encode_painted(proposal,paint)
    cave = SharedCave(blob)
    if not server.archive_generated_areas or not server.persist_generated_cave:
        raise ValueError('Durable generated-area archive required')
    old = server.shared_cave.identity if server.shared_cave else None
    # Do not silently strand existing actors, props or held resources. This is
    # creation, not relocation or revision continuation. Existing places remain archived.
    if old and (any(o.get('region_revision') == old for o in server.objects) or
                server.db.execute('SELECT 1 FROM world_prop_custody WHERE json_extract(object,\'$.region_revision\')=?', (old,)).fetchone()):
        raise ValueError('Active destination has world objects; preserve it or explicitly relocate them first')
    if server.db.execute('SELECT 1 FROM generated_area_archive WHERE identity=?', (cave.identity,)).fetchone():
        raise ValueError('This layout already exists; do not create a duplicate place')
    execution = getattr(server, 'actor_tool_execution', None)
    if not execution or execution[0] != actor:
        raise ValueError('Landscape creation requires the durable plan executor')
    _, record, plan, step = execution
    result = dict(revision=cave.identity, side=127, layout=args['layout'],
                  walkable_tiles=sum(r.count(ord('.')) for r in cave._rows),
                  required_client_capability='CAVE17' if cave.version==17 else 'CAVE16', outcome='outdoor_destination_activated',
                  entry='Existing shared GeneratedWorld_Wilds entrance', report=report)
    committed = []
    def persist(identity, place):
        if identity != cave.identity:
            raise ValueError('Unexpected landscape commit')
        result['place_id'] = place
        committed.append(_receipt(server, actor, record, plan, step, 'succeeded', result))
    server._replace_cave(blob, label=label, expected_world_id=server.memory.world_id,
        expected_sequence=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0],
        history_evidence=list(row['evidence']), actor_tool_commit=persist)
    return Committed(committed[0], result)
