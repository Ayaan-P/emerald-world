"""Bounded public character intent attached to original native script identities.

No spawned objects, teams, rewards, save flags or replacement story scripts.
"""
import copy
import hashlib
import inspect
import json
import re

KEY='canonical_cast'
BINDINGS={'canon_rydel':dict(name='Rydel',map='MauvilleCity_BikeShop',
    hook='MauvilleCity_BikeShop_EventScript_Rydel',offset=2,
    wire='rydel',effect='supplemental_dialogue_before_original_bike_service'),
    'canon_wally':dict(name='Wally',map='VerdanturfTown_WandasHouse',hook='VerdanturfTown_WandasHouse_EventScript_Wally',offset=2,wire='wally',effect='supplemental_dialogue_before_original_speech'),
    'canon_briney':dict(name='Mr. Briney',map='Route104_MrBrineysHouse',hook='Route104_MrBrineysHouse_EventScript_Briney',offset=2,wire='briney',effect='supplemental_dialogue_before_original_sailing')}


def records(state):
    value=state.get(KEY,{})
    if type(value) is not dict or set(value)-set(BINDINGS):raise ValueError('unknown canonical actor binding')
    from .build_catalog import catalog_maps
    places={'native:'+m['name'] for m in catalog_maps().values()}
    for identity,row in value.items():
        if type(row) is not dict or set(row)-{'offer'}!={'version','goal','dialogue','places','evidence','reason'}:
            raise ValueError('invalid canonical actor fields')
        if type(row['version']) is not int or not 1<=row['version']<=2**31-1:raise ValueError('invalid canonical actor version')
        for field,limit in [('goal',160),('reason',240)]:
            if type(row[field]) is not str or not 1<=len(row[field])<=limit or any(ord(c)<32 for c in row[field]):raise ValueError('invalid canonical actor text')
        if type(row['dialogue']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",row['dialogue']):raise ValueError('canonical dialogue requires bounded literal native text')
        if type(row['places']) is not list or not 1<=len(row['places'])<=4 or len(set(row['places']))!=len(row['places']) or any(p not in places for p in row['places']):raise ValueError('canonical interests require known native places')
        if type(row['evidence']) is not list or not 1<=len(row['evidence'])<=8 or any(type(n) is not int or n<1 for n in row['evidence']) or len(set(row['evidence']))!=len(row['evidence']):raise ValueError('canonical actor needs public evidence')
        offer=row.get('offer')
        if offer is not None:
            if (type(offer) is not dict or set(offer)!={'map','count'} or 'native:'+str(offer.get('map')) not in places
                    or 'native:'+str(offer.get('map')) not in row['places']
                    or str(offer.get('map')).startswith('GeneratedWorld_')
                    or type(offer.get('count')) is not int or not 1<=offer['count']<=50):
                raise ValueError('canonical offer requires a native destination and bounded trainer count')
        if identity in state.get('world_characters',{}):raise ValueError('canonical identity cannot also be a spawned actor')
    return value


def public_activity(event, places):
    return (event.get('event')=='guild_goal_completed'
            and event.get('publication')=='guild_leader_opt_in'
            and event.get('place_id') in places)


def validate_transition(before, after, objects, db):
    old,new=records(before),records(after)
    changes=[]
    if set(old)-set(new):raise ValueError('canonical identity cannot be deleted')
    for identity,row in new.items():
        if any(o['id']==identity for o in objects):raise ValueError('canonical actor must not be duplicated as a world object')
        if row==old.get(identity):continue
        if row['version']!=(old[identity]['version']+1 if identity in old else 1):raise ValueError('canonical actor version must advance once')
        for seq in row['evidence']:
            event=db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()
            if event is None or not public_activity(json.loads(event[0]),row['places']):raise ValueError('canonical actor evidence must be an actual opted-in public activity in its interests')
        changes.append(dict(character_id=identity,character_name=BINDINGS[identity]['name'],before=old.get(identity),after=row,places=sorted(set(row['places']+['native:'+BINDINGS[identity]['map']])),source='authored_public_activity_interpretation'))
    return changes


def action_step(actions, definition, result):
    import copy
    result=copy.deepcopy(result);cast=result['state'].setdefault('canonical_cast',{})
    receipts=result['state'].setdefault('canonical_action_receipts',[])
    if definition in receipts:return result
    if len(receipts)>=32:raise ValueError('canonical source consolidation required')
    for action in actions:
        identity=action['id'];old=cast.get(identity);version=old['version'] if old else 0
        row=copy.deepcopy(action['changes']);row['version']=action['expected_version']+1
        if old==row:continue
        if version!=action['expected_version']:raise ValueError('canonical actor changed before admission')
        cast[identity]=row
    receipts.append(definition)
    return result


def compile_actions(actions, context):
    data=context.get('data',context);state=copy.deepcopy(data.get('state',{}));cast=records(state)
    if type(actions) is not list or len(actions)!=1:raise ValueError('one bounded canonical action required')
    action=actions[0]
    if type(action) is not dict or set(action)!={'id','expected_version','changes'} or action['id'] not in BINDINGS:raise ValueError('invalid canonical action')
    if type(action['changes']) is not dict or set(action['changes'])-{'offer'}!={'goal','dialogue','places','evidence','reason'}:raise ValueError('invalid canonical changes')
    old=cast.get(action['id']);version=old['version'] if old else 0
    if type(action['expected_version']) is not int or action['expected_version']!=version:raise ValueError('stale canonical action')
    row=copy.deepcopy(action['changes']);row['version']=version+1
    state.setdefault(KEY,{})[action['id']]=row;records(state)
    known={e['seq']:e for e in context.get('recalled_history',{}).get('events',[])+data.get('world_memory',{}).get('recent',[])}
    if any(n not in known or not public_activity(known[n],row['places']) for n in row['evidence']):raise ValueError('canonical action requires inspected public activity evidence')
    previous=context.get('runtime',{}).get('previous_source')
    if type(previous) is not str or hashlib.sha256(previous.encode()).hexdigest()!=data.get('module_hash'):raise ValueError('verified active source required')
    suffix=hashlib.sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest()[:16]
    helper=inspect.getsource(action_step).replace('def action_step(',f'def _cast_step_{suffix}(',1)
    return previous+'\n'+f'_cast_previous_{suffix}=update\n'+helper+f'\ndef update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy({data.get("state",{})!r})\n    return _cast_step_{suffix}({actions!r}, {suffix!r}, _cast_previous_{suffix}(context,state))\n'


def response(server, conn, run, key):
    identity=next((i for i,b in BINDINGS.items() if b['wire']==key),None)
    if identity is None:raise ValueError('unknown canonical actor')
    server.core_story._place(conn,BINDINGS[identity]['map'])
    row=records(server.module_state).get(identity)
    if row is None:raise ValueError('no authored canonical response')
    result=dict(schema=1,world_id=server.memory.world_id,run=run,actor=identity,
                version=row['version'],briefing=row['dialogue'],objective=('Ask guild chat about my plan.' if row.get('offer') else ''),evidence=row['evidence'])
    result['digest']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result


def contract():
    return dict(response='canonical_actions/tests',bindings=BINDINGS,
                action_fields=['id','expected_version','changes'],
                change_fields=['goal','dialogue','places','evidence','reason','offer (optional native map/count)'],
                optional_offer=dict(map='canonical native map in places',count='1..50 distinct guild trainers',acceptance='/guild cast ACTOR previews; leader accepts exact version; chronicle must already be on',outcome='actual authenticated guild presence, not actor personal achievements'),
                effects='supplement original bound actor dialogue only; no spawned duplicate, save flag, team, reward, bike exchange or main script change',
                evidence='actual inspected opted-in public guild_goal_completed event in selected native places; no invented personal achievement',
                native='requires paired CAST safe-point adapter; original story continues offline or on refusal')


def guild_command(server, conn, args):
    """Explicit preview/accept, only at the original actor's location.

    Existing guild authority owns consent, frozen receipts, visits and rewards.
    Actor version binds ALL displayed terms; accepting never publishes old history.
    """
    from .guilds import GuildError
    if len(args) not in (1,2):
        return ['Use /guild cast ACTOR to preview a public field proposal. Actors: rydel, wally, briney.']
    identity=next((i for i,b in BINDINGS.items() if b['wire']==args[0]),None)
    if identity is None:raise GuildError('Unknown canonical actor.')
    if server.peers.get(conn.get('id')) is not conn or not (conn.get('state') or [0]*7)[6]:
        raise GuildError('Stand ready near the original actor before accepting a proposal.')
    try:server.core_story._place(conn,BINDINGS[identity]['map'])
    except ValueError:raise GuildError('Visit the original actor before reviewing or accepting a proposal.')
    row=records(server.module_state).get(identity);offer=(row or {}).get('offer')
    if not offer:raise GuildError('This actor has no current field proposal.')
    if len(args)==1:
        return [f"{BINDINGS[identity]['name']}: {offer['count']} trainers visit {offer['map']}.",
                'Public guild expedition. Chronicle must already be on. Completion can inform the actor.',
                f"Leader accepts these terms: /guild cast {args[0]} {row['version']}"]
    if args[1]!=str(row['version']):raise GuildError('Proposal changed. Preview again before accepting.')
    return server.guilds.expedition(conn['id'],['start',offer['map'],str(offer['count'])],
                                   character_offer=(identity,'field_plan',row['version']))


def reaction_activity(event, identity, row):
    if not public_activity(event,row.get('places',[])):return False
    if not row.get('offer'):return True
    return (event.get('character_id')==identity and event.get('character_offer_id')=='field_plan'
            and event.get('character_offer_revision')==row['version'])
