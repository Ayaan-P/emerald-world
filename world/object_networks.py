"""Linked, agent-authored prop mechanisms using existing native object actions."""
import copy,hashlib,inspect,json,re


def project(result, server=None):
    if not result['state'].get('world_object_networks'):return result
    result=copy.deepcopy(result);state=result['state'];controls=state.setdefault('world_object_controls',{})
    for key,network in state.get('world_object_networks',{}).items():
        program=network['program'];ids=network['objects'];status=state.setdefault('world_object_network_state',{}).setdefault(key,dict(phase=program['initial'],turn=0))
        updates=[controls[i]['state'] for i in ids if i in controls and controls[i]['state'].get('turn',0)>status['turn']]
        if len(updates)>1:raise ValueError('Conflicting network interactions')
        if updates:
            update=updates[0]
            if update['turn']!=status['turn']+1 or update['phase'] not in program['states']:raise ValueError('Invalid network transition')
            status.update(update)
            if server is not None:
                holds=getattr(server,'_spatial_mechanism_holds',{})
                for timer in list(holds):
                    if timer[0]==key:holds.pop(timer,None)
        if not updates and server is not None:
            from .spatial_mechanisms import transition
            target=transition(server,key,network,status)
            if target is not None and target!=status['phase']:
                status.update(phase=target,turn=status['turn']+1)
        node=program['states'][status['phase']]
        objects={o['id']:o for o in result['objects']}
        for identity in ids:
            if identity not in objects or objects[identity].get('kind')!='prop' or objects[identity].get('portable'):raise ValueError('Network member unavailable')
            obj=objects[identity];appearance=node['objects'][identity]
            obj.update(appearance)
            controls[identity]=dict(state=dict(status),object=dict(appearance))
            state.setdefault('world_object_actions',{})[identity]={action:action for action in node['on'].get(identity,{})}
            defaults=state.setdefault('world_object_player_use',{})
            if node['use'].get(identity):defaults[identity]=node['use'][identity]
            else:defaults.pop(identity,None)
    return result


def handler(identity,action,state,request):
    program=request['program'];phase=state.get('phase',program['initial']);node=program['states'][phase]
    target=node['on'][identity][action];appearance=program['states'][target]['objects'][identity]
    return dict(state=dict(phase=target,turn=state.get('turn',0)+1),**appearance)


def install(server,actor,row,args):
    from .actor_runtime import Pending
    from .actor_observation import observe
    from .actor_objects import digest
    from .region_characters import validate_region_objects
    if set(args)!={'definition'} or type(args['definition']) is not str or len(args['definition'])>2600:raise ValueError('Supply bounded linked mechanism JSON')
    request=json.loads(args['definition'])
    if type(request) is not dict:raise ValueError('Mechanism must be an object')
    program=request.get('program');ids=request.get('objects')
    if set(request)!={'id','objects','program'} or type(request['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',request['id']) or type(ids) is not list or not 2<=len(ids)<=4 or any(type(i) is not str for i in ids) or len(set(ids))!=len(ids):raise ValueError('Mechanism requires stable id and two to four distinct props')
    if request['id'] in server.module_state.get('world_object_networks',{}):raise ValueError('Existing mechanism preserved')
    seen=observe(server,actor,row,dict(radius=4));visible={e['id'] for e in seen['entities']}
    objects={o['id']:o for o in server.objects}
    for i in ids:
        obj=objects.get(i,{})
        if i not in visible or obj.get('kind')!='prop' or obj.get('portable') or i in server.module_state.get('world_object_controls',{}) or server.module_state.get('world_object_actions',{}).get(i):raise ValueError('Only observed unused anchored props may join')
        if server.db.execute("SELECT 1 FROM sqlite_master WHERE name='cave_links'").fetchone() and server.db.execute('SELECT 1 FROM cave_links WHERE object=?',(i,)).fetchone():raise ValueError('Link behavior preserved')
    if type(program) is not dict or set(program)!={'initial','states'} or type(program['states']) is not dict or not 1<=len(program['states'])<=6 or type(program['initial']) is not str or program['initial'] not in program['states']:raise ValueError('Invalid state graph')
    name=lambda s:type(s) is str and bool(re.fullmatch('[a-z][a-z0-9_]{0,15}',s))
    for phase,node in program['states'].items():
        if not name(phase) or type(node) is not dict or set(node) not in ({'objects','on','use'},{'objects','on','use','when'}) or any(type(node[k]) is not dict for k in ('objects','on','use')) or set(node['objects'])!=set(ids) or set(node['on'])-set(ids) or set(node['use'])-set(ids):raise ValueError('State must describe every member and its actions')
        for i,appearance in node['objects'].items():
            if type(appearance) is not dict or set(appearance)!={'x','y','gfx','text'} or any(type(appearance[k]) is not int for k in ('x','y','gfx')) or appearance['gfx'] not in (0,1) or type(appearance['text']) is not str or not 1<=len(appearance['text'])<=28 or any(not 32<=ord(c)<127 for c in appearance['text']):raise ValueError('Unsupported appearance')
            if abs(appearance['x']-objects[i]['x'])+abs(appearance['y']-objects[i]['y'])>1:raise ValueError('Each object remains within one tile of its anchor')
            actions=node['on'].get(i,{})
            if type(actions) is not dict or len(actions)>4 or any(not name(a) or not name(t) or t not in program['states'] for a,t in actions.items()) or type(node['use'].get(i,'')) is not str or node['use'].get(i,'') and node['use'][i] not in actions:raise ValueError('Invalid interaction transition')
        trial=[dict(o,**node['objects'][o['id']]) if o['id'] in ids else o for o in server.objects]
        validate_region_objects(server,trial,server.module_state)
    from .spatial_mechanisms import validate as validate_spatial
    from .shared_cave import SharedCave
    first=objects[ids[0]]
    archived=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(first['region_revision'],)).fetchone()
    if not archived:raise ValueError('Mechanism geometry unavailable')
    cave=SharedCave(archived[0])
    for phase,node in program['states'].items():
        validate_spatial(node.get('when',[]),program['states'],cave,[(objects[i]['x'],objects[i]['y']) for i in ids])
        if any(r['to']==phase for r in node.get('when',[])):raise ValueError('Spatial transitions must change phase')
        for rule in node.get('when',[]):
            for member in ids:
                a=node['objects'][member];b=program['states'][rule['to']]['objects'][member]
                if abs(a['x']-b['x'])+abs(a['y']-b['y'])>1:raise ValueError('A spatial transition moves each member at most one tile')
    for node in program['states'].values():
        for actions in node['on'].values():
            for target in actions.values():
                for member in ids:
                    a=node['objects'][member];b=program['states'][target]['objects'][member]
                    if abs(a['x']-b['x'])+abs(a['y']-b['y'])>1:raise ValueError('A transition moves each member at most one tile')
    if server.job is not None or server.deployment is not None:raise ValueError('Wait for mechanic admission')
    suffix=digest(request)[:16];old=server.candidate.source
    helper=inspect.getsource(handler).replace('def handler(',f'def _network_handler_{suffix}(',1)
    fallback='actor_interact' if 'def actor_interact(' in old else 'None'
    source=old+f'\n_network_previous_{suffix}=update\n_network_fallback_{suffix}={fallback}\n'+helper+f'''
def update(context,state):
    result=_network_previous_{suffix}(context,state)
    result['state'].setdefault('world_object_networks',{{}}).setdefault({request['id']!r},{request!r})
    return result
def actor_interact(identity,action,state):
    if identity in {ids!r}:return _network_handler_{suffix}(identity,action,state,{request!r})
    if _network_fallback_{suffix} is None:raise ValueError('Unknown object')
    return _network_fallback_{suffix}(identity,action,state)
'''
    if len(source.encode())>256*1024:raise ValueError('Mechanic source capacity')
    sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('network_'+sha+'.py')
    if path.exists():
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Candidate conflict')
    else:path.write_text(source)
    return Pending(dict(network=request['id'],definition=request),lambda:setattr(server,'deployment',(None,path,None)))


def poll(server,actor,row,pending):
    if server.module_state.get('world_object_networks',{}).get(pending['network'])!=pending['definition']:raise ValueError('Mechanism was not admitted')
    return dict(outcome='interactive_network_admitted',network=pending['network'],objects=pending['definition']['objects'],limits='Real shared prop states through native A or actor tools; no items/rewards or scripted story.')
