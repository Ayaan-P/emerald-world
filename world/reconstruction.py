"""Vacancy-bound terrain work; old native empty-area transaction stays authoritative."""
import hashlib,json


def setup(server):
    server.db.execute('CREATE TABLE IF NOT EXISTS terrain_reconstructions(id TEXT PRIMARY KEY,actor TEXT,plan TEXT,step TEXT,request TEXT,status TEXT,result TEXT)')


def queue(server,actor,row,args):
    from .actor_environment import inspected_change
    from .actor_runtime import Pending
    from .shared_terrain import validate,encode
    observation,tiles=inspected_change(server,actor,args)
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Reconstruction requires an actual durable actor plan')
    _,record,plan,step=execution;cave=server.shared_cave
    if not cave or cave.version!=9 or cave.identity!=observation['identity']:raise ValueError('Inspected event outdoor area changed')
    revision,payload=server._active_terrain()
    if revision!=observation['terrain_revision']:raise ValueError('Terrain changed; inspect again')
    merged=validate(cave,payload);seen=set()
    for t in tiles:
        point=(t['x'],t['y'])
        if point in seen or type(t['terrain']) is not str or t['terrain'] not in ('grass','tall_grass','water','original'):raise ValueError('Distinct supported terrain cells required')
        seen.add(point)
        if t['terrain']=='original':merged.pop(point,None)
        else:merged[point]={'grass':0,'tall_grass':1,'water':2}[t['terrain']]
    encode(cave,merged) # Connected geometry and protected static cast/endpoints, before offering work.
    identity=hashlib.sha256(json.dumps([server.memory.world_id,actor,plan['id'],step['id']]).encode()).hexdigest()[:24]
    request=dict(world=server.memory.world_id,observation=args['observation'],identity=cave.identity,revision=revision,place_id=observation['place_id'],tiles=tiles,evidence=list(row['evidence']))
    encoded=json.dumps(request,sort_keys=True);setup(server)
    prior=server.db.execute('SELECT request FROM terrain_reconstructions WHERE id=?',(identity,)).fetchone()
    if prior and prior[0]!=encoded:raise ValueError('Reconstruction identity reused with different work')
    if not prior:
        if server.db.execute("SELECT count(*) FROM terrain_reconstructions WHERE actor=? AND status='pending'",(actor,)).fetchone()[0]>=16 or server.db.execute("SELECT count(*) FROM terrain_reconstructions WHERE status='pending'").fetchone()[0]>=128:raise ValueError('Cancel an existing pending reconstruction first')
        server.db.execute('INSERT INTO terrain_reconstructions VALUES(?,?,?,?,?,?,NULL)',(identity,actor,plan['id'],step['id'],encoded,'pending'))
        server.revision=server.memory.append('terrain_reconstruction_planned',dict(character_id=actor,id=identity,place_id=request['place_id'],revision=revision,tiles=tiles,limits='Intention only. Existing occupants stay; no construction until vacant.'))
    return Pending(dict(reconstruction=identity),lambda:None)


def poll(server,actor,row,pending):
    setup(server);identity=pending['reconstruction']
    saved=server.db.execute('SELECT actor,request,status,result FROM terrain_reconstructions WHERE id=?',(identity,)).fetchone()
    if not saved or saved[0]!=actor:raise ValueError('Own reconstruction unavailable')
    request=json.loads(saved[1])
    if saved[2] in ('committed','conflict'):return json.loads(saved[3])
    if saved[2]!='pending':raise ValueError('Reconstruction '+saved[2])
    def reject(reason):
        result=dict(outcome='reconstruction_conflict',reconstruction=identity,changed=False,reason=reason)
        server.db.execute("UPDATE terrain_reconstructions SET status='conflict',result=? WHERE id=?",(json.dumps(result),identity))
        server.memory.append('terrain_reconstruction_stopped',dict(character_id=actor,id=identity,reason=reason))
        return result
    cave=server.shared_cave
    if request['world']!=server.memory.world_id or not cave or cave.identity!=request['identity'] or server._active_terrain()[0]!=request['revision']:
        return reject('World, destination or terrain revision changed; no automatic rebase')
    peers=[p for p in server.peers.values() if not p.get('closing') and p.get('cave_capable') and not p.get('region_cave')]
    if any(p.get('in_generated_cave') or p.get('state') is not None and tuple(p['state'][:2]) in (server.cave_map,server.wilds_map) for p in peers):return None
    result={}
    def persist(actual):
        result.update(outcome='deferred_terrain_committed',reconstruction=identity,identity=actual['identity'],terrain_revision=actual['revision'],changed=actual['changed'],place_id=request['place_id'])
        server.db.execute("UPDATE terrain_reconstructions SET status='committed',result=? WHERE id=?",(json.dumps(result,sort_keys=True),identity))
        server.memory.append('terrain_reconstruction_finished',dict(character_id=actor,**result,limits='Authority terrain commit, not proof of native rendering or fictional labor.'))
    try:
        server.set_shared_geometry(request['identity'],request['tiles'],expected_world_id=request['world'],expected_revision=request['revision'],history_evidence=request['evidence'],actor_tool_commit=persist)
    except ValueError as exc:return reject(str(exc)[:200])
    return result


def cancel(server,actor,row,args):
    if set(args)!={'id'} or type(args['id']) is not str:raise ValueError('Choose own reconstruction ID')
    return cancel_id(server,args['id'],actor)


def cancel_id(server,identity,actor=None):
    setup(server);saved=server.db.execute('SELECT actor,status FROM terrain_reconstructions WHERE id=?',(identity,)).fetchone()
    if not saved or actor is not None and saved[0]!=actor:raise ValueError('Reconstruction unavailable')
    if saved[1]!='pending':raise ValueError('Only pending work can be cancelled; committed terrain is not rolled back')
    server.db.execute("UPDATE terrain_reconstructions SET status='cancelled' WHERE id=?",(identity,))
    server.revision=server.memory.append('terrain_reconstruction_cancelled',dict(id=identity,character_id=saved[0],by='host' if actor is None else 'actor'))
    return dict(outcome='reconstruction_cancelled',reconstruction=identity,changed=False)


def catalog(server):
    setup(server)
    return [dict(id=i,actor=a,plan=p,step=s,status=status,**{k:v for k,v in json.loads(req).items() if k in ('identity','revision','place_id','tiles')}) for i,a,p,s,req,status in server.db.execute('SELECT id,actor,plan,step,request,status FROM terrain_reconstructions ORDER BY rowid DESC LIMIT 32')]


def command(server,conn,words):
    from .guilds import GuildError
    if words:raise GuildError('Use /guild reconstruction to see planned and completed terrain work.')
    items=catalog(server)[:6]
    return ['Terrain plans wait until everyone leaves; no live construction.']+[f"{r['id']} {r['actor'][:24]}: {r['status']}, {len(r['tiles'])} cells" for r in items] if items else ['No reconstruction plans.']
