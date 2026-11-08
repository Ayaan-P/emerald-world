"""Compile optional agent-authored character chapters into normal sandbox mechanics.

This creates source only. It never executes a model's source or bypasses staging.
Arbitrary source/tests responses remain supported for behavior beyond chapters.
"""
import hashlib
import inspect
import json
import re

EVENT_FIELDS = {
    'landmark_discovery_shared': {'place_id', 'revision', 'landmark'},
    'area_activated': {'place_id', 'label'},
    'area_named': {'place_id', 'before', 'after'},
    'region_opened': {'place_id', 'label'},
    'guild_goal_completed': {'place_id', 'goal_kind', 'guild_name', 'character_id', 'character_offer_id', 'character_offer_revision', 'region_revision'},
    'character_changed': {'character_id', 'character_status', 'relationship_target', 'relationship'},
}


def validate_plan(plan):
    from .characters import records
    from .mechanics import validate_objects
    from .build_catalog import catalog_maps
    if (type(plan) is not dict or set(plan) != {'id','name','role','origin_evidence','chapters'}
            or type(plan['id']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}',plan['id'])):
        raise ValueError('invalid character chapter plan')
    if len(json.dumps(plan,allow_nan=False).encode()) > 16384:
        raise ValueError('character plan exceeds 16 KiB')
    chapters=plan['chapters']
    if type(chapters) is not list or not 1 <= len(chapters) <= 16:
        raise ValueError('one to sixteen character chapters required')
    identities=set()
    for index,chapter in enumerate(chapters):
        if (type(chapter) is not dict or not {'id','when','goals','team','status','object','reason'} <= set(chapter)
                or set(chapter)-{'id','when','goals','team','status','object','reason','offer','next','services'}):
            raise ValueError('invalid chapter fields')
        identity=chapter['id']
        if type(identity) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}',identity) or identity in identities:
            raise ValueError('invalid or repeated chapter id')
        identities.add(identity)
        condition=chapter['when']
        if index == 0:
            if condition is not None:raise ValueError('first chapter starts on approved publication')
        elif (type(condition) is not dict or type(condition.get('event')) is not str or condition.get('event') not in EVENT_FIELDS
              or not set(condition) <= EVENT_FIELDS[condition['event']] | {'event'}
              or len(condition)<2 or any((type(v) is not int or not 1<=v<=2**31-1) if k=='character_offer_revision'
                  else (type(v) is not str or not 1<=len(v)<=160) for k,v in condition.items())):
            raise ValueError('chapter needs a specific public-event condition')
        if index and ('relationship_target' in condition or 'relationship' in condition):
            if (condition['event']!='character_changed' or not {'character_id','relationship_target','relationship'}<=set(condition)
                    or not re.fullmatch('[A-Za-z0-9_-]{1,24}',condition['relationship_target'])
                    or condition['character_id']==condition['relationship_target'] or len(condition['relationship'])>120):
                raise ValueError('relationship chapter requires actor, other NPC target and exact authored relationship')
        if index and condition['event']=='landmark_discovery_shared':
            if set(condition)!={'event','place_id','revision','landmark'} or not re.fullmatch('[0-9a-f]{64}',condition['revision']) or not re.fullmatch(r'area:[0-9a-f-]{36}',condition['place_id']) or not re.fullmatch('[a-z][a-z0-9_]{0,23}',condition['landmark']):
                raise ValueError('landmark chapters require exact place, revision and landmark')
        character=dict(version=1,name=plan['name'],role=plan['role'],goals=chapter['goals'],relationships={},
                       team=chapter['team'],status=chapter['status'],object_id=plan['id'],
                       evidence=plan['origin_evidence'],reason=chapter['reason'])
        if chapter.get('offer') is not None:character['offer']=chapter['offer']
        if 'services' in chapter:character['services']=chapter['services']
        records({'world_characters':{plan['id']:character}})
        obj=chapter['object']
        if chapter['status']=='active':
            if type(obj) is not dict or obj.get('id') != plan['id']:
                raise ValueError('active chapter must render its character')
            validate_objects([obj])
            entry=catalog_maps()[(obj['group'],obj['num'])]

        elif obj is not None:
            raise ValueError('away and retired chapters must not render')
        if chapter['status']=='retired' and index != len(chapters)-1:
            raise ValueError('retirement must be the last chapter')
    positions={chapter['id']:i for i,chapter in enumerate(chapters)}
    reached={0}
    for index,chapter in enumerate(chapters):
        targets=chapter.get('next',[chapters[index+1]['id']] if index+1<len(chapters) else [])
        if (type(targets) is not list or len(targets)>8 or
                any(type(target) is not str or target not in positions or positions[target]<=index for target in targets)
                or len(set(targets))!=len(targets)):
            raise ValueError('chapter next must name up to eight distinct later chapters')
        if chapter['status']=='retired' and targets:
            raise ValueError('retired chapters cannot continue')
        if index not in reached:
            raise ValueError('all chapters must be reachable from arrival')
        for target in targets:
            reached.add(positions[target])
            condition=chapters[positions[target]]['when']
            offer=chapter.get('offer')
            if offer and condition['event']=='guild_goal_completed':
                expected={'character_id':plan['id'],'character_offer_id':offer['id'],
                          'character_offer_revision':offer['revision']}
                if any(condition.get(key)!=value for key,value in expected.items()):
                    raise ValueError('offered expedition completion requires exact character and offer identity')
    return json.loads(json.dumps(plan))


def chapter_step(plan, definition, published_after, context, result):
    """Trusted reducer embedded verbatim into the sandbox-generated wrapper."""
    import copy
    result=copy.deepcopy(result)
    state=result['state']
    if type(state) is not dict:
        raise ValueError('character chapters require object-shaped mechanic state')
    programs=state.setdefault('world_character_chapters',{})
    cast=state.setdefault('world_characters',{})
    identity=plan['id']
    progress=programs.get(identity)
    if progress is None:
        if identity in cast or any(o['id']==identity for o in result.get('objects',[])):
            raise ValueError('character identity already belongs to existing content')
        progress={'definition':definition,'chapter':0,'event_seq':published_after}
        programs[identity]=progress
        chapter=plan['chapters'][0]
        cast[identity]=dict(version=1,name=plan['name'],role=plan['role'],goals=chapter['goals'],
            relationships={},team=chapter['team'],status=chapter['status'],object_id=identity,
            evidence=plan['origin_evidence'],reason=chapter['reason'])
        if chapter.get('offer') is not None:cast[identity]['offer']=chapter['offer']
        if 'services' in chapter:cast[identity]['services']=chapter['services']
        original=None
    else:
        if progress['definition'] != definition:
            raise ValueError('existing character chapter definition cannot be replaced silently')
        original=copy.deepcopy(cast[identity])
    feed=context.get('character_history',{'events':[],'through':state.get('character_history_cursor',0)})
    for event in feed['events']:
        if event['seq'] <= progress['event_seq']:
            continue
        progress['event_seq']=event['seq']
        current=plan['chapters'][progress['chapter']]
        targets=current.get('next',[plan['chapters'][progress['chapter']+1]['id']]
                            if progress['chapter']+1<len(plan['chapters']) else [])
        next_index=None
        for target in targets:
            candidate=next(i for i,c in enumerate(plan['chapters']) if c['id']==target)
            condition=plan['chapters'][candidate]['when']
            matched=all(event.get(k)==v for k,v in condition.items() if k not in ('relationship_target','relationship'))
            if 'relationship_target' in condition:
                matched=matched and event.get('relationship_changes',{}).get(condition['relationship_target'])==condition['relationship']
            if matched:
                next_index=candidate
                break
        if next_index is None:continue
        chapter=plan['chapters'][next_index]
        progress['chapter']=next_index
        cast[identity].update(goals=chapter['goals'],team=chapter['team'],status=chapter['status'],
                              evidence=[event['seq']],reason=chapter['reason'])
        cast[identity].pop('services',None)
        cast[identity].pop('offer',None)
        if chapter.get('offer') is not None:cast[identity]['offer']=chapter['offer']
        if 'services' in chapter:cast[identity]['services']=chapter['services']
    character=cast[identity]
    if original is not None and character != original:
        character['version']=original['version']+1
    state['character_history_cursor']=feed['through']
    # Replace only this program's visible object. Every unrelated effect survives.
    objects=[obj for obj in result.get('objects',[]) if obj['id'] != identity]
    chapter=plan['chapters'][progress['chapter']]
    if character['status']=='active':objects.append(copy.deepcopy(chapter['object']))
    result['objects']=objects
    return result


def compile_plan(plan, context):
    plan=validate_plan(plan)
    data=context.get('data',context)
    state=data.get('state',{})
    if type(state) is not dict or plan['id'] in state.get('world_characters',{}):
        raise ValueError('use the existing source route to revise an established character')
    known=set()
    for event in context.get('recalled_history',{}).get('events',[])+data.get('world_memory',{}).get('recent',[]):
        if type(event.get('seq')) is int:known.add(event['seq'])
    if any(seq not in known for seq in plan['origin_evidence']):
        raise ValueError('origin evidence must come from inspected or recalled public history')
    active=data.get('module_hash')
    previous=context.get('runtime',{}).get('previous_source')
    if active:
        if type(previous) is not str or hashlib.sha256(previous.encode()).hexdigest()!=active:
            raise ValueError('verified active source required to preserve existing world behavior')
    else:
        previous="def update(context, state):\n    return {'state':state,'tiles':[],'objects':[]}\n"
    through=data.get('world_memory',{}).get('through',0)
    if type(through) is not int or through<0:raise ValueError('invalid world history boundary')
    definition=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    suffix=definition[:16]
    helper=inspect.getsource(chapter_step).replace('def chapter_step(',f'def _chapter_step_{suffix}(',1)
    # Reuse the exact hash-verified source as text. Only the normal isolated
    # runtime will execute it, together with the wrapper and author tests.
    return (previous+'\n'+f'_chapter_previous_{suffix}=update\n'+helper+'\n'+
            f'def update(context,state):\n    return _chapter_step_{suffix}({plan!r}, {definition!r}, {through}, context, _chapter_previous_{suffix}(context,state))\n')


def contract():
    return {'response': '{"character_plan": plan, "tests": "Python tests for update"}',
            'plan_fields':['id','name','role','origin_evidence','chapters'],
            'chapter_fields':['id','when','goals','team','status','object','reason'],
            'branching':'optional next lists up to eight later chapter ids; default is the next chapter; [] ends the story; earliest recorded matching event chooses one route, declaration order breaks simultaneous matches; skipped routes never run; all chapters must be reachable',
            'optional_services':['guide'],
            'optional_chapter_field':'offer: validated expedition offer; requires explicit native acceptance and pre-existing guild chronicle ON',
            'relationships':'character_changed may match character_id + relationship_target + exact relationship label; only an actual newly committed NPC relationship delta qualifies, not unrelated later team changes; authored fictional relationship, not a human/player judgment',
            'landmark_privacy':'only explicitly shared landmark_discovery_shared events may trigger a chapter; require exact place_id, revision and landmark; private visits and unconfirmed share prompts never enter this feed',
            'scope':'shared-world characters respond to public events from any opted-in guild; guild_name is a literal name, not stable identity; an offered expedition completion must match its exact character_id, character_offer_id and character_offer_revision',
            'first_when':None,'later_when':'exact public event plus at least one listed field, all comparisons must match',
            'events':{name:sorted(fields) for name,fields in EVENT_FIELDS.items()},
            'limits':'one new stable character, up to sixteen authored chapters; native maps or explicitly scoped opened immutable generated regions or archived shared XL revisions; 16 KiB plan',
            'behavior':'initial chapter appears on approved publication; later chapters use only events newer than the author inspection; no battle-result triggers or mandatory player goals',
            'preservation':'wraps hash-verified previous_source; preserves other characters, tiles and objects; existing identities require normal source/tests route for deliberate revision',
            'execution':'compiled source still uses normal sandbox tests, authority validation and publication; this is not a sandbox bypass'}
