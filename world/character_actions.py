"""History-grounded actions for existing NPCs, compiled through normal staging."""
import copy
import hashlib
import inspect
import json


def validate_actions(actions, context):
    from .characters import records
    from .mechanics import validate_objects
    from .build_catalog import catalog_maps
    data=context.get('data',context)
    state=data.get('state',{})
    cast=copy.deepcopy(records(state))
    if type(actions) is not list or not 1<=len(actions)<=8 or len(json.dumps(actions).encode())>16384:
        raise ValueError('one to eight character actions within 16 KiB required')
    if len(state.get('world_character_action_receipts',[]))>=32:
        raise ValueError('consolidate existing source before adding more character actions')
    known={e['seq'] for e in context.get('recalled_history',{}).get('events',[])+data.get('world_memory',{}).get('recent',[]) if type(e.get('seq')) is int}
    seen=set()
    for action in actions:
        if type(action) is not dict or set(action)-{'walk'}!={'id','expected_version','evidence','reason','changes','object'}:
            raise ValueError('invalid character action fields')
        identity=action['id']
        if type(identity) is not str or identity not in cast or identity in seen:
            raise ValueError('actions require distinct existing character identities')
        seen.add(identity)
        character=cast[identity]
        if type(action['expected_version']) is not int or action['expected_version']!=character['version']:
            raise ValueError('stale character action')
        if character['status']=='retired':raise ValueError('retired characters cannot act')
        evidence=action['evidence']
        if type(evidence) is not list or not evidence or any(type(seq) is not int or seq not in known for seq in evidence):
            raise ValueError('actions require inspected public history evidence')
        changes=action['changes']
        if type(changes) is not dict or set(changes)-{'goals','relationships','team','status','offer','intentions'}:
            raise ValueError('unsupported character action changes')
        if 'walk' in action:
            path=action['walk'];obj=action['object']
            original=next((o for o in data.get('objects',[]) if o['id']==identity),None)
            if (type(path) is not list or not 2<=len(path)<=6 or
                    any(type(p) is not list or len(p)!=2 or any(type(v) is not int for v in p) for p in path) or
                    len({tuple(p) for p in path})!=len(path) or
                    any(abs(a[0]-b[0])+abs(a[1]-b[1])!=1 for a,b in zip(path,path[1:])) or
                    original is None or obj is None or 'region_revision' not in obj or
                    character['status']!='active' or changes.get('status','active')!='active' or
                    path[0]!=[original['x'],original['y']] or path[-1]!=[obj['x'],obj['y']] or
                    any(original.get(k)!=obj.get(k) for k in ('group','num','region_revision'))):
                raise ValueError('walk requires 2..6 unique cardinal points in the current generated place')
        character.update(copy.deepcopy(changes),version=character['version']+1,evidence=evidence,reason=action['reason'])
        if character.get('offer') is None:character.pop('offer',None)
        obj=action['object']
        if character['status']=='active':
            if type(obj) is not dict or obj.get('id')!=identity:raise ValueError('active action needs matching rendered object')
            validate_objects([obj])

        elif obj is not None:raise ValueError('absent character action must remove object')
    records({'world_characters':cast})
    return copy.deepcopy(actions)


def action_step(actions, definition, result, context=None):
    """Trusted reducer embedded in source; controlled actors supersede old scripts."""
    import copy
    result=copy.deepcopy(result)
    state=result['state'];cast=state['world_characters']
    receipts=state.setdefault('world_character_action_receipts',[])
    controls=state.setdefault('world_character_controls',{})
    tick=(context or {}).get('tick',0)
    if definition not in receipts:
        if len(receipts)>=32:raise ValueError('character action receipt limit')
        for action in actions:
            identity=action['id'];character=cast[identity]
            if character['version']!=action['expected_version']:
                raise ValueError('character changed before action admission')
            character=copy.deepcopy(character)
            character.update(copy.deepcopy(action['changes']),version=character['version']+1,
                             evidence=action['evidence'],reason=action['reason'])
            if character.get('offer') is None:character.pop('offer',None)
            controls[identity]={'character':character,'object':copy.deepcopy(action['object'])}
            if 'walk' in action:
                controls[identity]['walk']={'id':definition[:24],'path':copy.deepcopy(action['walk']),'index':0,'last_tick':tick}
                controls[identity]['object']['x'],controls[identity]['object']['y']=action['walk'][0]
        receipts.append(definition)
    for identity,control in sorted(controls.items()):
        walk=control.get('walk')
        if walk and walk['index']<len(walk['path'])-1 and walk['last_tick']!=tick:
            point=walk['path'][walk['index']+1];obj=control['object']
            occupied=any(p.get('ready') and p.get('generated_place',{}).get('revision')==obj.get('region_revision')
                         and [p.get('x'),p.get('y')]==point for p in (context or {}).get('players',[]))
            if not occupied:
                walk['index']+=1;obj['x'],obj['y']=point
            walk['last_tick']=tick
        cast[identity]=copy.deepcopy(control['character'])
    result['objects']=[obj for obj in result.get('objects',[]) if obj['id'] not in controls]
    result['objects'] += [copy.deepcopy(control['object']) for control in controls.values() if control['object'] is not None]
    return result


def compile_actions(actions, context):
    actions=validate_actions(actions,context)
    data=context.get('data',context)
    previous=context.get('runtime',{}).get('previous_source')
    if type(previous) is not str or hashlib.sha256(previous.encode()).hexdigest()!=data.get('module_hash'):
        raise ValueError('verified active source required for character actions')
    definition=hashlib.sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest()
    suffix=definition[:16]
    helper=inspect.getsource(action_step).replace('def action_step(',f'def _action_step_{suffix}(',1)
    # Fresh sandbox staging must continue the inspected durable world, not
    # recreate the previous source's first chapter. Nonempty runtime state
    # remains authoritative, including admission/version checks below.
    checkpoint=copy.deepcopy(data.get('state',{}))
    return (previous+'\n'+f'_action_previous_{suffix}=update\n'+helper+'\n'+
            f'def update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy({checkpoint!r})\n    return _action_step_{suffix}({actions!r}, {definition!r}, _action_previous_{suffix}(context,state), context)\n')


def contract():
    return {'response':'{"character_actions": actions, "tests": "Python tests"}',
            'action_fields':['id','expected_version','evidence','reason','changes','object'],
            'optional_walk':'2..6 unique cardinal [x,y] points including current start and replacement object endpoint, same generated revision only; progresses one point per authority tick, yields to reported ready player occupancy, blocks interactions until complete',
            'changes':'goals, relationships to existing public NPCs, team, status, retained practice intentions for own identified companions, optional offer (null removes)',
            'effect':'explicitly take over selected existing NPCs from older scripts; native map object controls actual relocation/dialogue and team controls battle; all unrelated source effects preserved',
            'evidence':'nonempty inspected/recalled public history references; authored intent, never proof of battle or catch',
            'limits':'eight actions per request, 32 action publications before source consolidation; expected version rechecked on admission; native maps or region_revision-bound opened immutable generated regions or archived shared XL revisions',
            'execution':'source compiler only; normal tests, sandbox and atomic authority validation remain mandatory; no autonomous LLM call or live publication'}
