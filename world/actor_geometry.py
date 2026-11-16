"""Observation-bound additive ground edits through existing immutable publication."""
import hashlib,json


def open_ground(server,actor,row,args):
    from .actor_runtime import Committed,_receipt
    from .characters import records
    from .shared_cave import SharedCave
    from .character_rebinding import prepare
    keys={'observation','x','y','width','height'}
    if set(args)!=keys or any(type(args[k]) is not int for k in keys) or not 1<=args['width']<=5 or not 1<=args['height']<=5:
        raise ValueError('Ground editing needs an observation receipt and a bounded integer rectangle')
    saved=server.db.execute("SELECT result FROM actor_tool_receipts WHERE actor=? AND seq=? AND status='succeeded'",(actor,args['observation'])).fetchone()
    event=server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(args['observation'],)).fetchone()
    if not saved or not event or json.loads(event[0]).get('tool')!='world.observe':
        raise ValueError('Use this actor own successful observation receipt')
    observation=json.loads(saved[0]);revision=observation['revision']
    obj=next((o for o in server.objects if o['id']==actor),None);current=records(server.module_state).get(actor)
    if (not current or current['status']!='active' or current['version']!=observation['actor_version'] or not obj
        or obj.get('region_revision')!=revision or (obj['x'],obj['y'])!=(observation['x'],observation['y'])):
        raise ValueError('Actor or observed location changed; observe again')
    if not server.archive_generated_areas or not server.shared_cave or server.shared_cave.identity!=revision:
        raise ValueError('Observed map is not the active archived shared map')
    saved=server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
    if not saved or hashlib.sha256(saved[0]).hexdigest()!=revision:raise ValueError('Durable map changed')
    cave=SharedCave(saved[0])
    if cave.version != 16:raise ValueError('Only plain shared XL geometry is supported; preserve immutable regions and other format data')
    cells={(c['x'],c['y']):c['walkable'] for c in observation['cells']}
    patch={(x,y) for x in range(args['x'],args['x']+args['width']) for y in range(args['y'],args['y']+args['height'])}
    protected={(1,1),(cave.side-2,cave.side-2),(cave.side-2,cave.side-3)}
    if not patch<=cells.keys() or patch&protected or any(not 0<x<cave.side-1 or not 0<y<cave.side-1 for x,y in patch):
        raise ValueError('Patch must remain inside the observed interior, away from native endpoints')
    changes=sorted(point for point in patch if not cells[point])
    if not changes:raise ValueError('Observed patch has no ground to open')
    rows=[bytearray(r) for r in cave._rows]
    for x,y in changes:rows[y][x]=ord('.')
    blob=saved[0][:8]+b''.join(rows);candidate=SharedCave(blob)
    continuation=prepare(server,revision,candidate.identity)
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Ground editing requires the durable plan executor')
    _,record,plan,step=execution;committed=[]
    result=dict(previous_revision=revision,revision=candidate.identity,x=obj['x'],y=obj['y'],
        opened=[list(p) for p in changes],observation=args['observation'],outcome='connected_ground_committed')
    def persist(identity,place):
        if identity!=candidate.identity:raise ValueError('Unexpected geometry commit')
        result['place_id']=place
        committed.append(_receipt(server,actor,record,plan,step,'succeeded',result))
    label=server.db.execute('SELECT label FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()[0]
    server._replace_cave(blob,label=label,previous_revision=revision,expected_world_id=server.memory.world_id,
        expected_sequence=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0],
        history_evidence=list(row['evidence']),character_continuation=continuation,actor_tool_commit=persist)
    return Committed(committed[0],result)
