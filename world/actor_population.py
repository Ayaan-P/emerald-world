"""Stage generic authored population through normal world mechanic admission."""
import ast,copy,hashlib,inspect,json,re


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


def prepare(server,actor,row,args,*,state=None,objects=None):
    from .canonical_cast import BINDINGS
    from .characters import records
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
    state=server.module_state if state is None else state
    objects=server.objects if objects is None else objects
    identity=definition['id']
    if type(identity) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',identity):raise ValueError('Use a stable lowercase object identity')
    if (identity.startswith('canon_') or identity in records(state)
        or any(o['id']==identity for o in objects) or any(p['object']==identity for p in inventory(server))):
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
    request=dict(object=obj,character=record)
    request['request']=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
    return request


def stage(server,actor,row,requests):
    from .actor_runtime import Pending
    from .characters import validate_transition
    from .region_characters import validate_region_objects
    if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('A current idle mechanic source is required')
    proposed=dict(state=copy.deepcopy(server.module_state),objects=copy.deepcopy(server.objects),tiles=[])
    for request in requests:proposed=population_step(proposed,request)
    server._validated(proposed);validate_transition(server.module_state,proposed['state'],proposed['objects'],server.db)
    validate_region_objects(server,proposed['objects'],proposed['state'])
    source=dispatch_source(server.candidate.source,requests,server.module_state)
    if len(source.encode())>256*1024:raise ValueError('Population source budget reached')
    sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('population_'+sha+'.py')
    try:
        with path.open('x') as f:f.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Population candidate conflict')
    def dispatch():server.deployment=(None,path,None)
    return Pending(dict(population=requests),dispatch)


def spawn(server,actor,row,args):
    return stage(server,actor,row,[prepare(server,actor,row,args)])


def populate_group(server,actor,row,args):
    if set(args)!={'revision','definitions'} or type(args['definitions']) is not str or len(args['definitions'])>700:
        raise ValueError('Supply exact revision and bounded population list JSON')
    try:definitions=json.loads(args['definitions'])
    except ValueError:raise ValueError('Invalid population list JSON') from None
    if type(definitions) is not list or not 2<=len(definitions)<=4:raise ValueError('Supply two to four independently defined NPCs or props')
    state=copy.deepcopy(server.module_state);objects=copy.deepcopy(server.objects);requests=[]
    for definition in definitions:
        request=prepare(server,actor,row,dict(revision=args['revision'],definition=json.dumps(definition)),state=state,objects=objects)
        proposed=population_step(dict(state=state,objects=objects),request)
        state,objects=proposed['state'],proposed['objects'];requests.append(request)
    return stage(server,actor,row,requests)


def poll(server,actor,row,pending):
    from .characters import records
    requests=pending.get('population',[pending]);admitted=[]
    for request in requests:
        receipt=server.module_state.get('world_population_receipts',{}).get(request['request'])
        obj=next((o for o in server.objects if o['id']==request['object']['id']),None)
        if not receipt or obj!=request['object'] or (request['character'] is not None and records(server.module_state).get(obj['id'])!=request['character']):
            raise ValueError('Population was not admitted; no creation claimed')
        admitted.append(dict(object=obj['id'],revision=obj['region_revision'],x=obj['x'],y=obj['y'],kind='character' if request['character'] is not None else 'prop',outcome='population_admitted'))
    return admitted[0] if len(admitted)==1 else dict(outcome='population_group_admitted',members=admitted,limits='Atomic authored population, not simulated births, catches, travel or completed model turns.')


def dispatch_source(old,requests,state):
    """Keep one verified projector; growth represents retained entities, not wrappers.

    Legacy append-only projectors remain untouched. Entity, per-map and state
    budgets still apply; this is not an unlimited population or save migration.
    """
    helper=inspect.getsource(population_step).replace('def population_step(','def _ew_population_step_v1(',1)
    wrapper="def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy(_ew_population_seed_v1)\n    result=_ew_population_previous_v1(context,state)\n    for request in _ew_population_catalog_v1:\n        result=_ew_population_step_v1(result,request)\n    return result\n"
    tree=ast.parse(old)
    def assignments(name):
        return [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
    catalogs=assignments('_ew_population_catalog_v1')
    if catalogs:
        seeds=assignments('_ew_population_seed_v1')
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        matches=lambda code:any(ast.dump(n,include_attributes=False)==ast.dump(ast.parse(code).body[0],include_attributes=False) for n in funcs)
        if len(catalogs)!=1 or len(seeds)!=1 or any(len(n.targets)!=1 for n in catalogs+seeds) or not matches(helper) or not matches(wrapper):
            raise ValueError('Population dispatcher changed; explicit consolidation required')
        catalog=ast.literal_eval(catalogs[0].value);ast.literal_eval(seeds[0].value)
        if type(catalog) is not list:raise ValueError('Invalid retained population catalog')
        known={r['request'] for r in catalog}
        if any(r['request'] in known for r in requests):raise ValueError('Population request already retained')
        lines=old.splitlines(keepends=True)
        for node,value in sorted([(catalogs[0],catalog+requests),(seeds[0],state)],key=lambda x:x[0].lineno,reverse=True):
            lines[node.lineno-1:node.end_lineno]=[f'{node.targets[0].id}={value!r}\n']
        return ''.join(lines)
    if any(isinstance(n,ast.Name) and n.id.startswith('_ew_population_') for n in ast.walk(tree)):
        raise ValueError('Reserved population dispatcher names already in use')
    return old+f'\n_ew_population_previous_v1=update\n_ew_population_seed_v1={state!r}\n_ew_population_catalog_v1={requests!r}\n'+helper+'\n'+wrapper
