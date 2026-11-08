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
        if type(action) is not dict or set(action)!={'id','expected_version','evidence','reason','changes','object'}:
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
        if type(changes) is not dict or set(changes)-{'goals','relationships','team','status','offer'}:
            raise ValueError('unsupported character action changes')
        character.update(copy.deepcopy(changes),version=character['version']+1,evidence=evidence,reason=action['reason'])
        if character.get('offer') is None:character.pop('offer',None)
        obj=action['object']
        if character['status']=='active':
            if type(obj) is not dict or obj.get('id')!=identity:raise ValueError('active action needs matching rendered object')
            validate_objects([obj])

        elif obj is not None:raise ValueError('absent character action must remove object')
    records({'world_characters':cast})
    return copy.deepcopy(actions)


def action_step(actions, definition, result):
    """Trusted reducer embedded in source; controlled actors supersede old scripts."""
    import copy
    result=copy.deepcopy(result)
    state=result['state'];cast=state['world_characters']
    receipts=state.setdefault('world_character_action_receipts',[])
    controls=state.setdefault('world_character_controls',{})
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
        receipts.append(definition)
    for identity,control in controls.items():
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
    return (previous+'\n'+f'_action_previous_{suffix}=update\n'+helper+'\n'+
            f'def update(context,state):\n    return _action_step_{suffix}({actions!r}, {definition!r}, _action_previous_{suffix}(context,state))\n')


def contract():
    return {'response':'{"character_actions": actions, "tests": "Python tests"}',
            'action_fields':['id','expected_version','evidence','reason','changes','object'],
            'changes':'goals, relationships to existing public NPCs, team, status, optional offer (null removes)',
            'effect':'explicitly take over selected existing NPCs from older scripts; native map object controls actual relocation/dialogue and team controls battle; all unrelated source effects preserved',
            'evidence':'nonempty inspected/recalled public history references; authored intent, never proof of battle or catch',
            'limits':'eight actions per request, 32 action publications before source consolidation; expected version rechecked on admission; native maps or region_revision-bound opened immutable generated regions or archived shared XL revisions',
            'execution':'source compiler only; normal tests, sandbox and atomic authority validation remain mandatory; no autonomous LLM call or live publication'}
