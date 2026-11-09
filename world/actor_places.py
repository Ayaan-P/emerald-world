"""Create a new selectable immutable region without switching the shared map."""
import json
import time


def create(server, actor, row, args):
    from .actor_runtime import Committed, _receipt
    from .cave_blueprint import proposal_from_blueprint
    from .shared_cave import SharedCave
    if set(args) != {'label','blueprint'} or type(args['blueprint']) is not str or len(args['blueprint']) > 700:
        raise ValueError('Supply a label and bounded cave blueprint JSON string')
    label=args['label']
    if type(label) is not str or not 1<=len(label)<=20 or not label.strip() or any(not(c.isascii() and (c.isalnum() or c in " .,'!?-")) for c in label):
        raise ValueError('Use a 1..20 character literal region menu label')
    if not server.archive_generated_areas:
        raise ValueError('Persistent generated area archive is required')
    try: blueprint=json.loads(args['blueprint'])
    except (TypeError,ValueError):raise ValueError('Invalid cave blueprint JSON')
    proposal=proposal_from_blueprint(blueprint,side=31)
    blob=b'EWGMAP01'+''.join(proposal['rows']).encode('ascii')
    cave=SharedCave(blob)
    if server.db.execute('SELECT 1 FROM generated_area_archive WHERE identity=?',(cave.identity,)).fetchone():
        raise ValueError('This exact geometry already exists; reuse its existing place rather than inventing another identity')
    if server.db.execute('SELECT count(*) FROM world_region_revisions').fetchone()[0]>=32:
        raise ValueError('Opened region capacity reached')
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:
        raise ValueError('Place creation requires the durable plan executor')
    _,record,plan,step=execution
    with server.lock, server.db:
        server.db.execute('INSERT INTO generated_area_archive VALUES (?,?,?,?,?)',
            (cave.identity,label,'cave',blob,int(time.time())))
        opened=server._pin_region(cave.identity)
        result=dict(place_id=opened['place_id'],revision=cave.identity,label=label,side=31,
            outcome='region_opened',required_client_capability='REGION1',entry='REGION1 selection then existing cave entrance',
            walkable_tiles=sum(r.count('.') for r in proposal['rows']))
        seq=_receipt(server,actor,record,plan,step,'succeeded',result)
    server.revision=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
    return Committed(seq,result)
