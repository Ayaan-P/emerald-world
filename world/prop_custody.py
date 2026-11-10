"""Authority custody of existing portable props, never native bag items."""
import copy,json


def install(db):
    from .actor_cargo import setup
    setup(db)
    db.execute('CREATE TABLE IF NOT EXISTS world_prop_custody(id TEXT PRIMARY KEY,owner TEXT,object TEXT NOT NULL,version INTEGER NOT NULL)')


def inventory(server):
    install(server.db)
    return [dict(object=i,owner=o,version=v,revision=json.loads(raw)['region_revision'])
            for i,o,raw,v in server.db.execute('SELECT id,owner,object,version FROM world_prop_custody ORDER BY id')]


def project(server,result):
    """Apply custody over authored output. An older source cannot duplicate cargo."""
    install(server.db)
    rows=server.db.execute('SELECT id,owner,object,version FROM world_prop_custody').fetchall()
    if not rows:return result
    from .mechanics import validate_objects
    validate_objects(result.get('objects',[]))
    result=copy.deepcopy(result)
    objects={o['id']:o for o in result.get('objects',[])}
    actors=result['state'].get('world_characters',{})
    controls=result['state'].get('world_object_controls',{})
    for identity,owner,raw,_ in rows:
        if identity in actors:raise ValueError('A custodied prop cannot become a character')
        if owner is not None:
            from .player_cargo import is_player
            if not is_player(server.db,owner) and (owner not in actors or actors[owner].get('status')=='retired'):raise ValueError('Place carried props before retiring or removing their carrier')
            carrier=objects.get(owner)
            if carrier and carrier.get('region_revision')!=json.loads(raw)['region_revision']:
                from .actor_cargo import matching
                if not matching(server,result['state'],result.get('objects',[]),owner):raise ValueError('Place carried props before changing immutable map scope')
            objects.pop(identity,None)
        else:
            if identity not in objects:raise ValueError('A placed custodied prop cannot silently disappear')
            obj=objects[identity]
            if obj.get('kind')!='prop':raise ValueError('A custodied prop must retain its kind')
            obj=dict(obj)
            # Custody, not stale author source, owns the relocated map binding.
            for key in ('group','num','region_revision'):obj[key]=json.loads(raw)[key]
            override=controls.get(identity,{}).get('object',{})
            if set(override)-{'x','y','gfx','text'}:raise ValueError('Invalid prop position override')
            obj.update(override);objects[identity]=obj
    result['objects']=list(objects.values())
    return result


def actor_position(server,actor):
    from .characters import records
    from .character_walks import walking
    row=records(server.module_state).get(actor)
    obj=next((o for o in server.objects if o['id']==actor),None)
    if not row or row['status']!='active' or not obj or not obj.get('region_revision') or walking(server.module_state,actor):
        raise ValueError('A stationary active world actor on an exact map is required')
    if any(p.get('character_pending',{}).get('id')==actor for p in server.peers.values() if type(p.get('character_pending')) is dict):
        raise ValueError('Actor is busy with a player battle')
    return obj


def commit(server,actor,record,operation,identity,obj,owner,version,state):
    from .actor_runtime import Committed,_receipt
    from .region_characters import validate_region_objects
    from .characters import validate_transition
    from .mechanics import validate_objects
    execution=server.actor_tool_execution
    if not execution or execution[0]!=actor:raise ValueError('Custody requires the durable plan executor')
    if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('Mechanic work is pending')
    result=dict(object=identity,owner=owner,version=version,revision=obj['region_revision'],operation=operation,
                outcome='authority_prop_custody_committed',limits='Existing world prop only; no native bag, item, resource quantity or carrying animation.')
    with server.db:
        server.db.execute('INSERT OR REPLACE INTO world_prop_custody VALUES(?,?,?,?)',(identity,owner,json.dumps(obj,sort_keys=True),version))
        visible=server.objects+([obj] if owner is None else [])
        projected=project(server,dict(state=state,objects=visible,tiles=[]));objects=validate_objects(projected['objects'])
        state_json,_=server._validated(projected)
        validate_transition(server.module_state,state,objects,server.db);validate_region_objects(server,objects,state)
        source=server.db.execute('SELECT sha256 FROM module WHERE singleton=1').fetchone()
        if not source or source[0]!=server.candidate.sha256:raise ValueError('Durable mechanic changed')
        server.db.execute('UPDATE module SET state=?,objects=? WHERE singleton=1',(state_json,json.dumps(objects)))
        seq=_receipt(server,actor,record,execution[2],execution[3],'succeeded',result)
    server.module_state=state;server.objects=objects
    return Committed(seq,result)


def take(server,actor,row,args):
    from .actor_objects import digest
    if set(args)!={'object','object_revision'}:raise ValueError('Take requires an observed portable prop and revision')
    install(server.db);source=actor_position(server,actor)
    obj=next((o for o in server.objects if o['id']==args['object']),None)
    if (not obj or obj.get('kind')!='prop' or obj.get('portable') is not True
        or digest(obj)!=args['object_revision']
        or any(source.get(k)!=obj.get(k) for k in ('group','num','region_revision'))
        or abs(source['x']-obj['x'])+abs(source['y']-obj['y'])!=1):raise ValueError('Portable prop is stale, unavailable or not adjacent')
    prior=server.db.execute('SELECT owner,version FROM world_prop_custody WHERE id=?',(obj['id'],)).fetchone()
    if prior and prior[0] is not None:raise ValueError('Prop already has a carrier')
    if server.db.execute('SELECT count(*) FROM world_prop_custody WHERE owner=?',(actor,)).fetchone()[0]>=4:raise ValueError('Actor already carries four props')
    if not prior and server.db.execute('SELECT count(*) FROM world_prop_custody').fetchone()[0]>=32:raise ValueError('World prop custody capacity reached')
    return commit(server,actor,row,'take',obj['id'],obj,actor,(prior[1]+1 if prior else 1),copy.deepcopy(server.module_state))


def place(server,actor,row,args):
    if set(args)!={'object','version','x','y'} or any(type(args[k]) is not int for k in ('version','x','y')):raise ValueError('Place requires owned prop version and integer destination')
    install(server.db);source=actor_position(server,actor)
    held=server.db.execute('SELECT owner,object,version FROM world_prop_custody WHERE id=?',(args['object'],)).fetchone()
    if not held or held[0]!=actor or held[2]!=args['version']:raise ValueError('Prop ownership or version changed')
    obj=json.loads(held[1])
    if (any(source.get(k)!=obj.get(k) for k in ('group','num','region_revision'))
        or abs(source['x']-args['x'])+abs(source['y']-args['y'])!=1):raise ValueError('Place beside the actor on the same exact generated map')
    obj.update(x=args['x'],y=args['y']);state=copy.deepcopy(server.module_state)
    control=state.setdefault('world_object_controls',{}).setdefault(obj['id'],{'state':{}})
    control['object']={k:obj[k] for k in ('x','y','gfx','text')}
    return commit(server,actor,row,'place',obj['id'],obj,None,held[2]+1,state)
