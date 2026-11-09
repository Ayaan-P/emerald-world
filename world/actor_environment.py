"""History-driven terrain authoring through the existing connected native overlay.

This is public world authoring, not fictional physical labor or actor perception.
"""
import json


def inspect_patch(server, actor, row, args):
    if (set(args) != {'x','y','width','height'} or any(type(v) is not int for v in args.values())
            or not 1 <= args['width'] <= 8 or not 1 <= args['height'] <= 8
            or args['x'] < 1 or args['y'] < 1
            or args['x']+args['width'] > 62 or args['y']+args['height'] > 62):
        raise ValueError('Inspect an interior rectangle at most 8 by 8')
    cave=server.shared_cave
    if cave is None or cave.version != 9:
        raise ValueError('Only the active archived 63x63 event outdoor area is supported')
    data=server.inspect_shared_terrain(cave.identity)
    tiles={(t['x'],t['y']):t['terrain'] for t in data['tiles']}
    protected={(1,1),(61,60),(61,61)} | {(p['x'],p['y']) for p in data['characters']}
    return dict(identity=cave.identity,terrain_revision=data['revision'],
        place_id=server.memory.place(cave.identity),basis='public_authority_map',
        cells=[dict(x=x,y=y,terrain=tiles.get((x,y),'original'),
                    original_walkable=cave.walkable(x,y),walkable=data['effective_rows'][y][x]=='.',
                    protected=(x,y) in protected)
               for y in range(args['y'],args['y']+args['height'])
               for x in range(args['x'],args['x']+args['width'])])


def reshape(server, actor, row, args):
    from .actor_runtime import Committed, _receipt
    if (set(args) != {'observation','tiles'} or type(args['observation']) is not int
            or type(args['tiles']) is not str or len(args['tiles']) > 700):
        raise ValueError('Use an own terrain inspection and bounded tile JSON')
    saved=server.db.execute("SELECT result FROM actor_tool_receipts WHERE actor=? AND seq=? AND status='succeeded'",(actor,args['observation'])).fetchone()
    event=server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(args['observation'],)).fetchone()
    if not saved or not event or json.loads(event[0]).get('tool') != 'world.inspect_environment':
        raise ValueError('Use this actor own successful environment inspection')
    observation=json.loads(saved[0])
    try: tiles=json.loads(args['tiles'])
    except ValueError: raise ValueError('Invalid tile JSON') from None
    allowed={(c['x'],c['y']) for c in observation['cells'] if not c['protected']}
    if (type(tiles) is not list or not tiles or any(type(t) is not dict or set(t)!={'x','y','terrain'}
            or type(t['x']) is not int or type(t['y']) is not int
            or (t['x'],t['y']) not in allowed for t in tiles)):
        raise ValueError('Only inspected unprotected tiles may change')
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0] != actor:
        raise ValueError('Terrain authoring requires the durable plan executor')
    _,record,plan,step=execution
    committed=[];result={}
    def persist(actual):
        result.update(outcome='connected_terrain_committed',identity=actual['identity'],
            terrain_revision=actual['revision'],changed=actual['changed'],
            observation=args['observation'],place_id=observation['place_id'])
        committed.append(_receipt(server,actor,record,plan,step,'succeeded',result))
    server.set_shared_geometry(observation['identity'],tiles,
        expected_world_id=server.memory.world_id,expected_revision=observation['terrain_revision'],
        history_evidence=list(row['evidence']),actor_tool_commit=persist)
    return Committed(committed[0],result)
