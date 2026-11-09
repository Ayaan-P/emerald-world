"""Explicit opt-in object handlers, executed by normal mechanic staging."""
import ast,copy,hashlib,inspect,json,re


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def offers(server,obj):
    from .characters import records
    if obj['id'] in records(server.module_state) or obj.get('kind')!='prop' or not obj.get('region_revision'):return {}
    manifest=server.module_state.get('world_object_actions',{})
    if type(manifest) is not dict:return {}
    actions=manifest.get(obj['id'],{})
    if type(actions) is not dict or len(actions)>8:return {}
    valid={k:v for k,v in actions.items() if type(k) is str and re.fullmatch('[a-z][a-z0-9_]{0,23}',k) and type(v) is str and 1<=len(v)<=80 and all(32<=ord(c)<127 for c in v)}
    if len(valid)!=len(actions) or not server.candidate:return {}
    try:
        if not any(isinstance(n,ast.FunctionDef) and n.name=='actor_interact' for n in ast.parse(server.candidate.source).body):return {}
    except SyntaxError:return {}
    return dict(actions=valid,object_revision=digest([obj,actions,server.candidate.sha256])) if valid else {}


def object_step(result,request,handler):
    # Copied into the sandboxed source; no server or native save access.
    import copy,hashlib,json
    result=copy.deepcopy(result);state=result['state']
    controls=state.setdefault('world_object_controls',{})
    for obj in result.get('objects',[]):
        if obj['id'] in controls:obj.update(copy.deepcopy(controls[obj['id']]['object']))
    receipts=state.setdefault('world_object_action_receipts',{})
    if request['id'] in receipts:return result
    if len(receipts)>=32:raise ValueError('Consolidate object interaction source before adding more requests')
    actors=state.get('world_characters',{});actor=actors.get(request['actor'],{})
    objects={o['id']:o for o in result.get('objects',[])}
    source=objects.get(request['actor']);target=objects.get(request['object'])
    actions=state.get('world_object_actions',{}).get(request['object'],{})
    if not target or target!=request['target'] or actions!=request['actions'] or request['object'] in actors:
        raise ValueError('Object interaction preconditions changed')
    if request.get('player_use'):
        if state.get('world_object_player_use',{}).get(request['object'])!=request['action']:
            raise ValueError('Default player-use action changed')
    elif (actor.get('status')!='active' or actor.get('version')!=request['version'] or not source
        or any(source.get(k)!=target.get(k) for k in ('group','num','region_revision'))
        or abs(source['x']-target['x'])+abs(source['y']-target['y'])!=1):
        raise ValueError('Object interaction preconditions changed')
    previous=controls.get(request['object'],{}).get('state',{})
    value=handler(request['object'],request['action'],copy.deepcopy(previous))
    if type(value) is not dict or set(value)!={'state','x','y','gfx','text'} or type(value['state']) is not dict or len(json.dumps(value['state'],allow_nan=False))>2048:
        raise ValueError('Object handler requires bounded own state and x/y/gfx/text')
    if (any(type(value[k]) is not int for k in ('x','y','gfx')) or abs(value['x']-target['x'])+abs(value['y']-target['y'])>1
        or value['gfx'] not in (0,1) or type(value['text']) is not str or not 1<=len(value['text'])<=28
        or any(not 32<=ord(c)<127 for c in value['text'])):raise ValueError('Object handler exceeds supported local object changes')
    after=dict(target,**{k:value[k] for k in ('x','y','gfx','text')})
    controls[request['object']]=dict(state=value['state'],object={k:after[k] for k in ('x','y','gfx','text')})
    result['objects']=[after if o['id']==request['object'] else o for o in result['objects']]
    receipts[request['id']]=dict(object=request['object'],action=request['action'],before=target,after=after,
        state_changed=previous!=value['state'],state_digest=hashlib.sha256(json.dumps(value['state'],sort_keys=True).encode()).hexdigest())
    return result


def use(server,actor,row,args):
    from .actor_runtime import Pending
    from .characters import records
    from .character_walks import walking
    if set(args)!={'object','action','object_revision'}:raise ValueError('Use an observed object action and revision')
    obj=next((o for o in server.objects if o['id']==args['object']),None)
    source=next((o for o in server.objects if o['id']==actor),None)
    current=records(server.module_state).get(actor,{})
    offer=offers(server,obj) if obj else {}
    if (not obj or not source or current.get('status')!='active' or walking(server.module_state,actor)
        or offer.get('object_revision')!=args['object_revision'] or args['action'] not in offer.get('actions',{})
        or any(source.get(k)!=obj.get(k) for k in ('group','num','region_revision'))
        or abs(source['x']-obj['x'])+abs(source['y']-obj['y'])!=1):raise ValueError('Object action unavailable, stale or not adjacent')
    execution=server.actor_tool_execution
    request=dict(actor=actor,version=current['version'],object=obj['id'],action=args['action'],target=copy.deepcopy(obj),actions=offer['actions'],plan=execution[2]['id'],step=execution[3]['id'])
    return stage(server,request)


def stage(server,request):
    from .actor_runtime import Pending
    obj=request['target']
    identity=digest(request);request['id']=identity;suffix=identity[:16]
    source_code=dispatch_source(server.candidate.source,request,server.module_state)
    if len(source_code.encode())>256*1024:raise ValueError('Consolidate source before another interaction')
    sha=hashlib.sha256(source_code.encode()).hexdigest();path=server.runtime.candidates/('object_'+sha+'.py')
    try:
        with path.open('x') as f:f.write(source_code)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source_code:raise ValueError('Object candidate conflict')
    def dispatch():server.deployment=(None,path,None)
    return Pending(dict(request=identity,object=obj['id'],revision=obj['region_revision'],before=copy.deepcopy(obj),state_digest=digest(server.module_state.get('world_object_controls',{}).get(obj['id'],{}).get('state',{}))),dispatch)


def poll(server,actor,row,pending):
    result=receipt(server.module_state,pending['request'])
    obj=next((o for o in server.objects if o['id']==pending['object']),None)
    control=server.module_state.get('world_object_controls',{}).get(pending['object'],{})
    if result and obj and result.get('before')==pending['before'] and result.get('after')==obj and obj.get('region_revision')==pending['revision']:
        return dict(object=pending['object'],before=pending['before'],after=copy.deepcopy(obj),revision=pending['revision'],state_changed=digest(control.get('state',{}))!=pending['state_digest'],state_digest=digest(control.get('state',{})),outcome='validated_object_state_committed')
    raise ValueError('Object handler was not admitted; no effect claimed')


def player_use(server,conn,obj):
    """Only called after production INTERACT_REGION admission; A is the use intent."""
    if obj.get('kind')!='prop':return
    defaults=server.module_state.get('world_object_player_use',{})
    if type(defaults) is not dict:return
    action=defaults.get(obj['id'])
    offer=offers(server,obj)
    if action is None:return  # Ordinary text-only props retain their old behavior.
    def notice(text):server.guild_chat.message(conn,conn['id'],text)
    if type(action) is not str or action not in offer.get('actions',{}):
        notice('This object action is unavailable.');return
    if server.job is not None or server.deployment is not None or getattr(server,'object_use_pending',None):
        notice('Object busy. Try again shortly.');return
    request=dict(actor='',version=0,object=obj['id'],action=action,target=copy.deepcopy(obj),actions=offer['actions'],
        player_use=True,nonce=digest([conn['id'],conn['seq'],server.candidate.sha256]))
    try:
        pending=stage(server,request)
        server.object_use_pending=dict(conn=conn,pending=pending.data,action=action)
        pending.dispatch()
        notice('Using object...')
    except ValueError:
        notice('Object action unavailable; nothing applied.')


def poll_player(server):
    pending=getattr(server,'object_use_pending',None)
    if not pending:return
    saved_receipt=receipt(server.module_state,pending['pending']['request'])
    if not saved_receipt and (server.job is not None or server.deployment is not None):return
    server.object_use_pending=None
    try:
        result=poll(server,'',{},pending['pending'])
        with server.db:
            server.memory.append('object_action_applied',dict(object=result['object'],action=pending['action'],revision=result['revision'],
                source='validated_player_object_use',state_digest=result['state_digest']))
        server.revision=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
        message='Object action applied.'
    except ValueError:message='Object action was not applied.'
    conn=pending['conn']
    if server.peers.get(conn.get('id')) is conn and not conn.get('closing'):
        server.guild_chat.message(conn,conn['id'],message)
        server._queue(conn,server._snapshot(conn))


def receipt(state,identity):
    return state.get('world_object_current_receipt',{}).get(identity) or state.get('world_object_action_receipts',{}).get(identity)


def dispatch_source(old,request,state):
    """Replace only our verified request literal; never rewrite arbitrary source.

    Old append-only handlers keep their receipts and never replay. New requests
    use one reusable function and one current receipt. Authority history remains.
    """
    helper=inspect.getsource(object_step).replace('def object_step(', 'def _ew_object_dispatch_v1(',1)
    helper=helper.replace("receipts=state.setdefault('world_object_action_receipts',{})", "receipts=state.setdefault('world_object_current_receipt',{})")
    helper=helper.replace("    if len(receipts)>=32:raise ValueError('Consolidate object interaction source before adding more requests')", "    receipts.clear()")
    wrapper="def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy(_ew_object_seed_v1)\n    return _ew_object_dispatch_v1(_ew_object_previous_v1(context,state),_ew_object_request_v1,actor_interact)\n"
    tree=ast.parse(old)
    assignments=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_ew_object_request_v1' for t in n.targets)]
    if assignments:
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        expected=ast.dump(ast.parse(helper).body[0],include_attributes=False)
        if len(assignments)!=1 or len(assignments[0].targets)!=1 or not any(ast.dump(n,include_attributes=False)==expected for n in functions) or not any(ast.dump(n,include_attributes=False)==ast.dump(ast.parse(wrapper).body[0],include_attributes=False) for n in functions):
            raise ValueError('Reusable object dispatcher changed; explicit mechanic consolidation required')
        seeds=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='_ew_object_seed_v1']
        if len(seeds)!=1:raise ValueError('Object dispatcher seed changed')
        lines=old.splitlines(keepends=True)
        for node,value in sorted([(assignments[0],request),(seeds[0],state)],key=lambda pair:pair[0].lineno,reverse=True):
            ast.literal_eval(node.value) # Never replace an executable expression.
            lines[node.lineno-1:node.end_lineno]=[f'{node.targets[0].id}={value!r}\n']
        return ''.join(lines)
    if any(isinstance(n,ast.Name) and n.id.startswith('_ew_object_') for n in ast.walk(tree)):
        raise ValueError('Reserved object dispatcher names are already in use')
    return old+f'\n_ew_object_previous_v1=update\n_ew_object_seed_v1={state!r}\n_ew_object_request_v1={request!r}\n'+helper+'\n'+wrapper


def archive_transition(server,before,state,objects):
    """Same transaction as admission; retain causal data before receipt rotation."""
    current=state.get('world_object_current_receipt',{})
    if current==before.get('world_object_current_receipt',{}):return
    if type(current) is not dict or len(current)!=1:raise ValueError('One current object receipt required')
    server.db.execute('CREATE TABLE IF NOT EXISTS object_transition_archive(id TEXT PRIMARY KEY,data TEXT,seq INTEGER)')
    identity,value=next(iter(current.items()))
    if type(value) is not dict:raise ValueError('Invalid object transition receipt')
    obj=next((o for o in objects if o['id']==value.get('object')),None)
    previous=next((o for o in server.objects if o['id']==value.get('object')),None)
    control=state.get('world_object_controls',{}).get(value.get('object'),{}).get('state',{})
    if not obj or obj.get('kind')!='prop' or value.get('before')!=previous or value.get('after')!=obj or value.get('state_digest')!=digest(control):raise ValueError('Object receipt does not match admitted state')
    encoded=json.dumps(value,sort_keys=True)
    prior=server.db.execute('SELECT data FROM object_transition_archive WHERE id=?',(identity,)).fetchone()
    if prior:
        if prior[0]!=encoded:raise ValueError('Object transition identity reused')
        return
    seq=server.memory.append('object_transition_committed',dict(object=obj['id'],request=identity,revision=obj.get('region_revision'),before=previous,after=obj,state_digest=value['state_digest'],source='validated_mechanic_admission'))
    server.db.execute('INSERT INTO object_transition_archive VALUES(?,?,?)',(identity,encoded,seq));server.revision=seq
