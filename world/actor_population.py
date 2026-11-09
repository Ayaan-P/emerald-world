"""Stage generic authored population through normal world mechanic admission."""
import copy,hashlib,inspect,json,re


def population_step(result,request):
    import copy
    result=copy.deepcopy(result);state=result['state'];obj=request['object'];identity=obj['id']
    receipts=state.setdefault('world_population_receipts',{})
    if request['character'] is not None:
        cast=state.setdefault('world_characters',{})
        if identity not in cast:cast[identity]=copy.deepcopy(request['character'])
        active=cast[identity]['status']=='active'
    else:active=True
    if active and not any(o['id']==identity for o in result.get('objects',[])):
        result.setdefault('objects',[]).append(copy.deepcopy(obj))
    receipts.setdefault(request['request'],dict(object=identity,revision=obj['region_revision']))
    return result


def spawn(server,actor,row,args):
    from .actor_runtime import Pending
    from .canonical_cast import BINDINGS
    from .characters import records,validate_transition
    from .region_characters import validate_region_objects
    from .prop_custody import inventory
    if set(args)!={'revision','definition'} or type(args['definition']) is not str or len(args['definition'])>700:
        raise ValueError('Supply exact revision and bounded population definition JSON')
    try: definition=json.loads(args['definition'])
    except (ValueError,TypeError):raise ValueError('Invalid population definition JSON')
    common={'id','kind','x','y','gfx','text'}
    if type(definition) is not dict or definition.get('kind') not in ('character','prop'):
        raise ValueError('Population kind must be character or prop')
    character=definition['kind']=='character'
    if set(definition)!=common|({'name','role','goals','team'} if character else {'portable'}):
        raise ValueError('Population fields do not match the supported kind')
    identity=definition['id']
    if type(identity) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',identity):raise ValueError('Use a stable lowercase object identity')
    if (identity.startswith('canon_') or identity in records(server.module_state)
        or any(o['id']==identity for o in server.objects) or any(p['object']==identity for p in inventory(server))):
        raise ValueError('Object identity already exists or is reserved')
    if character and (type(definition['name']) is str and definition['name'].strip().casefold() in [b['name'].casefold() for b in BINDINGS.values()] or identity in [b['wire'] for b in BINDINGS.values()]):
        raise ValueError('Use original canonical bindings, never spawn a duplicate familiar actor')
    revision=args['revision']
    saved=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
    if not saved:raise ValueError('Exact archived geometry is unavailable')
    from .shared_cave import SharedCave
    cave=SharedCave(saved[0])
    if cave.identity!=revision or cave.version not in (1,10,16):raise ValueError('Population supports immutable plain/wildlife caves and shared XL only')
    group,num=server.cave_map if cave.version in (1,10) else server.wilds_map
    obj=dict(id=identity,group=group,num=num,region_revision=revision,**{k:definition[k] for k in ('x','y','gfx','text')})
    record=None
    if character:
        if type(definition['team']) is list and all(type(m) is dict and 'individual' not in m for m in definition['team']):
            definition['team']=[dict(m,individual='partner_'+str(i+1)) for i,m in enumerate(definition['team'])]
        record=dict(version=1,name=definition['name'],role=definition['role'],goals=definition['goals'],team=definition['team'],
            relationships={},status='active',object_id=identity,evidence=list(row['evidence']),reason='Created by an admitted population plan; no prior experiences asserted.')
    else:obj.update(kind='prop',portable=definition['portable'])
    if any(not p.get('closing') and p.get('state') and p['state'][6] and server._region_scope(p)==revision and p['state'][2:4]==[obj['x'],obj['y']] for p in server.peers.values()):
        raise ValueError('Population placement overlaps a ready player')
    if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('A current idle mechanic source is required')
    if len(server.module_state.get('world_population_receipts',{}))>=16:raise ValueError('Consolidate population source before adding more objects')
    request=dict(object=obj,character=record)
    request['request']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
    proposed=population_step(dict(state=server.module_state,objects=server.objects,tiles=[]),request)
    server._validated(proposed);validate_transition(server.module_state,proposed['state'],proposed['objects'],server.db)
    validate_region_objects(server,proposed['objects'],proposed['state'])
    suffix=request['request'][:16]
    helper=inspect.getsource(population_step).replace('def population_step(',f'def _population_{suffix}(',1)
    source=(server.candidate.source+'\n'+f'_population_previous_{suffix}=update\n'+helper+'\n'+
        f'def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy({server.module_state!r})\n    return _population_{suffix}(_population_previous_{suffix}(context,state),{request!r})\n')
    if len(source.encode())>256*1024:raise ValueError('Consolidate mechanic source before population')
    sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('population_'+sha+'.py')
    try:
        with path.open('x') as f:f.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Population candidate conflict')
    def dispatch():server.deployment=(None,path,None)
    return Pending(dict(request=request['request'],object=obj,character=record),dispatch)


def poll(server,actor,row,pending):
    from .characters import records
    receipt=server.module_state.get('world_population_receipts',{}).get(pending['request'])
    obj=next((o for o in server.objects if o['id']==pending['object']['id']),None)
    if not receipt or obj!=pending['object'] or (pending['character'] is not None and records(server.module_state).get(obj['id'])!=pending['character']):
        raise ValueError('Population was not admitted; no creation claimed')
    return dict(object=obj['id'],revision=obj['region_revision'],x=obj['x'],y=obj['y'],kind='character' if pending['character'] is not None else 'prop',outcome='population_admitted')
