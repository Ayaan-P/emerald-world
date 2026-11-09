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
        if type(row) is not dict or set(row)-{'offer','relationships','conversation','letter'}!={'version','goal','dialogue','places','evidence','reason'}:
            raise ValueError('invalid canonical actor fields')
        if type(row['version']) is not int or not 1<=row['version']<=2**31-1:raise ValueError('invalid canonical actor version')
        for field,limit in [('goal',160),('reason',240)]:
            if type(row[field]) is not str or not 1<=len(row[field])<=limit or any(ord(c)<32 for c in row[field]):raise ValueError('invalid canonical actor text')
        if type(row['dialogue']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",row['dialogue']):raise ValueError('canonical dialogue requires bounded literal native text')
        if type(row['places']) is not list or not 1<=len(row['places'])<=4 or len(set(row['places']))!=len(row['places']) or any(p not in places for p in row['places']):raise ValueError('canonical interests require known native places')
        if type(row['evidence']) is not list or not 1<=len(row['evidence'])<=8 or any(type(n) is not int or n<1 for n in row['evidence']) or len(set(row['evidence']))!=len(row['evidence']):raise ValueError('canonical actor needs public evidence')
        letter=row.get('letter')
        if letter is not None:
            if type(letter) is not dict or set(letter)!={'to','text'}:raise ValueError('letter requires recipient and text')
            if type(letter['to']) is not str or letter['to'] not in value or letter['to']==identity:raise ValueError('letter needs another existing canonical recipient')
            if type(letter['text']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",letter['text']):raise ValueError('bounded literal public letter required')
        conversation=row.get('conversation',{})
        if type(conversation) is not dict or len(conversation)>3:raise ValueError('at most three conversational choices')
        for choice,option in conversation.items():
            if type(choice) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,15}',choice):raise ValueError('invalid conversational choice')
            if type(option) is not dict or set(option)!={'label','reply'}:raise ValueError('conversation choices require label and reply')
            for field,limit in [('label',48),('reply',200)]:
                if type(option[field]) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,"+str(limit)+"}",option[field]):raise ValueError('bounded literal conversation text required')
        relationships=row.get('relationships',{})
        if type(relationships) is not dict or len(relationships)>2:raise ValueError('at most two directional cast relationships')
        for target,relation in relationships.items():
            if target not in BINDINGS or target==identity or target not in value:raise ValueError('relationship requires another existing original actor')
            if type(relation) is not dict or set(relation)!={'stance','motivation','evidence'}:raise ValueError('invalid relationship fields')
            if relation['stance'] not in ('curious','encouraged','concerned','respectful','competitive'):raise ValueError('invalid directional stance')
            if type(relation['motivation']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,160}",relation['motivation']):raise ValueError('bounded relationship motivation required')
            if type(relation['evidence']) is not list or not 1<=len(relation['evidence'])<=4 or any(type(n) is not int or n not in row['evidence'] for n in relation['evidence']):raise ValueError('relationship must cite this decision evidence')
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
            if event is None or not decision_evidence(json.loads(event[0]),identity,row):raise ValueError('canonical actor evidence must be an actual opted-in public activity in its interests')
        validate_letter(row,lambda n: json.loads(db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]))
        validate_relationship_evidence(row,lambda n: json.loads(db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]))
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
    if type(action['changes']) is not dict or set(action['changes'])-{'offer','relationships','conversation','letter'}!={'goal','dialogue','places','evidence','reason'}:raise ValueError('invalid canonical changes')
    old=cast.get(action['id']);version=old['version'] if old else 0
    if type(action['expected_version']) is not int or action['expected_version']!=version:raise ValueError('stale canonical action')
    row=copy.deepcopy(action['changes']);row['version']=version+1
    state.setdefault(KEY,{})[action['id']]=row;records(state)
    known={e['seq']:e for e in context.get('recalled_history',{}).get('events',[])+data.get('world_memory',{}).get('recent',[])}
    if any(n not in known or not decision_evidence(known[n],action['id'],row) for n in row['evidence']):raise ValueError('canonical action requires inspected public activity evidence')
    validate_letter(row,lambda n: known[n])
    validate_relationship_evidence(row,lambda n: known[n])
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
    private=server.db.execute('SELECT version,choice FROM canonical_conversations WHERE trainer=? AND actor=?',(conn['id'],identity)).fetchone()
    option=row.get('conversation',{}).get(private[1]) if private and private[0]==row['version'] else None
    result=dict(schema=1,world_id=server.memory.world_id,run=run,actor=identity,
                version=row['version'],briefing=option['reply'] if option else row['dialogue'],objective=('Guild chat has conversation choices.' if row.get('conversation') and not option else 'Ask guild chat about my plan.' if row.get('offer') else ''),evidence=row['evidence'])
    result['digest']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result


def contract():
    return dict(response='canonical_actions/tests',bindings=BINDINGS,
                action_fields=['id','expected_version','changes'],
                change_fields=['goal','dialogue','places','evidence','reason','offer (optional native map/count)','relationships (optional directional assessments)','conversation (optional private player choices)','letter (optional public cast correspondence)'],
                letter=dict(fields=['to (existing canonical identity)','text (200 literal characters)'],effect='authority delivers a public in-world letter and records exact evidence; no physical meeting',basis='public activity or received letter; at most two deliveries per reply chain; recipient may reconsider goals or respond'),
                conversation=dict(choice='1..3 lowercase IDs',fields=['label (48 literal characters)','reply (200 literal characters)'],privacy='only player explicitly selects their own option; selection never enters world history or author context',scope='per authenticated trainer and actor; actor version changes require choosing again; no auto affinity, gifts or story changes'),
                relationships=dict(target='another existing bound canonical actor, not a player',fields=['stance','motivation','evidence'],stances=['curious','encouraged','concerned','respectful','competitive'],basis='actual public completion attributed to target actor; directional interpretation, not mutual relationship or invented meeting',reaction='new public target-offer results in actor interests trigger reconsideration; never authored decisions alone'),
                optional_offer=dict(map='canonical native map in places',count='1..50 distinct guild trainers',acceptance='/guild cast ACTOR previews; leader accepts exact version; chronicle must already be on',outcome='actual authenticated guild presence, not actor personal achievements'),
                effects='supplement original bound actor dialogue only; no spawned duplicate, save flag, team, reward, bike exchange or main script change',
                evidence='actual inspected opted-in public guild_goal_completed in selected places or authority-delivered letter addressed to this actor; no invented personal achievement',
                native='requires paired CAST safe-point adapter; original story continues offline or on refusal')


def guild_command(server, conn, args):
    """Explicit preview/accept, only at the original actor's location.

    Existing guild authority owns consent, frozen receipts, visits and rewards.
    Actor version binds ALL displayed terms; accepting never publishes old history.
    """
    from .guilds import GuildError
    if len(args) not in (1,2,4):
        return ['Use /guild cast ACTOR to preview a public field proposal. Actors: rydel, wally, briney.']
    identity=next((i for i,b in BINDINGS.items() if b['wire']==args[0]),None)
    if identity is None:raise GuildError('Unknown canonical actor.')
    if server.peers.get(conn.get('id')) is not conn:raise GuildError('Authenticated trainer connection required.')
    if args[1:]==['forget']:return conversation_command(server,conn,identity,None,['forget'])
    if not (conn.get('state') or [0]*7)[6]:
        raise GuildError('Stand ready near the original actor before accepting a proposal.')
    try:server.core_story._place(conn,BINDINGS[identity]['map'])
    except ValueError:raise GuildError('Visit the original actor before reviewing or accepting a proposal.')
    row=records(server.module_state).get(identity);offer=(row or {}).get('offer')
    if len(args)>=2 and args[1] in ('talk','forget'):
        return conversation_command(server,conn,identity,row,args[1:])
    if len(args)==4:raise GuildError('Use /guild cast ACTOR talk VERSION CHOICE.')
    if len(args)==2 and args[1]=='letters':
        entries=[]
        for (data,) in server.db.execute("SELECT data FROM events WHERE kind='world_memory' AND json_extract(data,'$.event')='canonical_letter_delivered' AND (json_extract(data,'$.sender')=? OR json_extract(data,'$.recipient')=?) ORDER BY seq DESC LIMIT 3",(identity,identity)):
            event=json.loads(data)
            entries.append(f"{BINDINGS[event['sender']]['name']} to {BINDINGS[event['recipient']]['name']}:")
            entries.extend(event['text'][i:i+110] for i in range(0,len(event['text']),110))
        return ['Public cast correspondence. No physical meeting is implied.']+(entries or ['No delivered letters yet.'])
    if len(args)==2 and args[1]=='thoughts':
        if row is None:raise GuildError('This actor has no authored intent yet.')
        lines=[f"{BINDINGS[identity]['name']}'s current goal:"]
        lines.extend(row['goal'][i:i+110] for i in range(0,len(row['goal']),110))
        for target,relation in row.get('relationships',{}).items():
            lines.append(f"{relation['stance'].capitalize()} about {BINDINGS[target]['name']} - authored interpretation.")
            lines.extend(relation['motivation'][i:i+110] for i in range(0,len(relation['motivation']),110))
            lines.append('Public evidence: '+', '.join(str(n) for n in relation['evidence']))
        return lines
    if not offer:raise GuildError('This actor has no current field proposal. Use /guild cast ACTOR thoughts for current intent.')
    if len(args)==1:
        return [f"{BINDINGS[identity]['name']}: {offer['count']} trainers visit {offer['map']}.",
                'Public guild expedition. Chronicle must already be on. Completion can inform the actor.',
                f"Leader accepts these terms: /guild cast {args[0]} {row['version']}"]
    if args[1]!=str(row['version']):raise GuildError('Proposal changed. Preview again before accepting.')
    return server.guilds.expedition(conn['id'],['start',offer['map'],str(offer['count'])],
                                   character_offer=(identity,'field_plan',row['version']))


def reaction_activity(event, identity, row):
    if received_letter(event,identity):return True
    if not public_activity(event,row.get('places',[])):return False
    if event.get('character_id') in row.get('relationships',{}) and event.get('character_offer_id')=='field_plan':return True
    if not row.get('offer'):return True
    return (event.get('character_id')==identity and event.get('character_offer_id')=='field_plan'
            and event.get('character_offer_revision')==row['version'])


def validate_relationship_evidence(row, lookup):
    for target,relation in row.get('relationships',{}).items():
        for seq in relation['evidence']:
            event=lookup(seq)
            if (not public_activity(event,row['places']) or event.get('character_id')!=target
                    or event.get('character_offer_id')!='field_plan'
                    or type(event.get('character_offer_revision')) is not int):
                raise ValueError('relationship needs real public completion of the target actor proposal')


def conversation_command(server, conn, identity, row, args):
    """Own authenticated conversation only. No broadcast, history or GM input."""
    from .guilds import GuildError
    if args==['forget']:
        with server.db:
            server.db.execute('DELETE FROM canonical_conversations WHERE trainer=? AND actor=?',(conn['id'],identity))
        return ['Your conversation choice was forgotten. Other trainers are unchanged.']
    if not row or not row.get('conversation'):raise GuildError('No authored conversation choices are available.')
    options=row['conversation'];wire=BINDINGS[identity]['wire']
    if args==['talk']:
        return ['Private conversation. This choice affects only your response, not the shared story.',
                'A new actor version requires a new choice. Use forget to clear yours.']+[
                f"{key}: {option['label']}" for key,option in options.items()]+[
                f"Choose: /guild cast {wire} talk {row['version']} CHOICE"]
    if len(args)!=3 or args[0]!='talk' or args[1]!=str(row['version']) or args[2] not in options:
        raise GuildError('Conversation changed or choice unavailable. Preview with /guild cast ACTOR talk.')
    with server.db:
        server.db.execute('INSERT OR REPLACE INTO canonical_conversations VALUES(?,?,?,?)',
                          (conn['id'],identity,row['version'],args[2]))
    text=options[args[2]]['reply']
    return [f"{BINDINGS[identity]['name']} answers you privately:"]+[text[i:i+110] for i in range(0,len(text),110)]+[
            'Your next original NPC conversation uses this reply. Other trainers are unchanged.']


def received_letter(event, identity):
    return (event.get('event')=='canonical_letter_delivered' and event.get('publication')=='public_cast_correspondence'
            and event.get('recipient')==identity and event.get('sender') in BINDINGS
            and type(event.get('depth')) is int and 1<=event['depth']<=2)


def decision_evidence(event, identity, row):
    return public_activity(event,row['places']) or received_letter(event,identity)


def validate_letter(row, lookup):
    if row.get('letter'):
        depth=max((lookup(n).get('depth',0) if lookup(n).get('event')=='canonical_letter_delivered' else 0 for n in row['evidence']),default=0)+1
        if depth>2:raise ValueError('letter reply chain is complete; reconsider a goal or wait instead')


def deliver_letter(server, change):
    """Called inside the same admission transaction; replayed unchanged state sends nothing."""
    row=change['after'];old=change.get('before') or {};letter=row.get('letter')
    if not letter or letter==old.get('letter'):return
    events=[json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]) for n in row['evidence']]
    depth=max((e.get('depth',0) if e.get('event')=='canonical_letter_delivered' else 0 for e in events),default=0)+1
    server.revision=server.memory.append('canonical_letter_delivered',dict(
        sender=change['character_id'],recipient=letter['to'],text=letter['text'],
        sender_version=row['version'],based_on=row['evidence'],depth=depth,
        publication='public_cast_correspondence',
        places=['native:'+BINDINGS[i]['map'] for i in (change['character_id'],letter['to'])]))
