"""Bounded public character intent attached to original native script identities.

No spawned objects, teams, rewards, save flags or replacement story scripts.
"""
import copy
import hashlib
import inspect
import json
import re
import time

KEY='canonical_cast'
BINDINGS={'canon_rydel':dict(name='Rydel',map='MauvilleCity_BikeShop',
    hook='MauvilleCity_BikeShop_EventScript_Rydel',offset=2,
    wire='rydel',effect='supplemental_dialogue_before_original_bike_service'),
    'canon_wally':dict(name='Wally',map='VerdanturfTown_WandasHouse',hook='VerdanturfTown_WandasHouse_EventScript_Wally',offset=2,wire='wally',effect='supplemental_dialogue_before_original_speech'),
    'canon_steven':dict(name='Steven',map='MossdeepCity_StevensHouse',hook='MossdeepCity_StevensHouse_EventScript_Steven',offset=2,wire='steven',effect='supplemental_dialogue_after_original_dive_scene'),
    'canon_briney':dict(name='Mr. Briney',map='Route104_MrBrineysHouse',hook='Route104_MrBrineysHouse_EventScript_Briney',offset=2,wire='briney',effect='supplemental_dialogue_before_original_sailing')}

# Same canonical actor at reviewed later-story conversation continuations.
LOCATION_ALIASES={'wally_vr':('canon_wally','VictoryRoad_1F')}

def location(key):
    if key in LOCATION_ALIASES:return LOCATION_ALIASES[key]
    return next(((identity,row['map']) for identity,row in BINDINGS.items() if row['wire']==key),(None,None))

def check_actor_location(server,conn,identity):
    if identity!='canon_steven':
        try:server.core_story._place(conn,BINDINGS[identity]['map']);return
        except ValueError:pass
    reached=conn.get('canonical_location')
    if reached and reached['actor']==identity and reached['run']==conn.get('core_active_run'):
        server.core_story._place(conn,reached['map']);return
    raise ValueError('Talk to this original actor at the current location first.')


def records(state):
    value=state.get(KEY,{})
    if type(value) is not dict or set(value)-set(BINDINGS):raise ValueError('unknown canonical actor binding')
    from .build_catalog import catalog_maps
    places={'native:'+m['name'] for m in catalog_maps().values()}
    for identity,row in value.items():
        if type(row) is not dict or set(row)-{'activity_projects','scene','initiative','call','companion','world_action','council','journey_interests','routine','cooperate','worksite','study','offer','relationships','conversation','letter','project','contribution','resolve_contribution','intentions','fulfill'}!={'version','goal','dialogue','places','evidence','reason'}:
            raise ValueError('invalid canonical actor fields')
        if type(row['version']) is not int or not 1<=row['version']<=2**31-1:raise ValueError('invalid canonical actor version')
        for field,limit in [('goal',160),('reason',240)]:
            if type(row[field]) is not str or not 1<=len(row[field])<=limit or any(ord(c)<32 for c in row[field]):raise ValueError('invalid canonical actor text')
        if type(row['dialogue']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",row['dialogue']):raise ValueError('canonical dialogue requires bounded literal native text')
        if type(row['places']) is not list or not 1<=len(row['places'])<=4 or len(set(row['places']))!=len(row['places']) or any(p not in places for p in row['places']):raise ValueError('canonical interests require known native places')
        if type(row['evidence']) is not list or not 1<=len(row['evidence'])<=8 or any(type(n) is not int or n<1 for n in row['evidence']) or len(set(row['evidence']))!=len(row['evidence']):raise ValueError('canonical actor needs public evidence')
        if row.get('scene') is not None and (identity!='canon_rydel' or row['scene']!='rydel_step'):raise ValueError('Only reviewed Rydel step scene is supported')
        from .canonical_initiatives import validate as validate_initiative
        validate_initiative(row.get('initiative'),identity,row,value)
        from .canonical_activity_projects import validate as validate_activity_projects
        validate_activity_projects(row.get('activity_projects'),row)
        from .canonical_calls import validate as validate_call
        validate_call(identity,row.get('call'))
        if row.get('companion') is not None and (identity!='canon_steven' or row['companion']!='steven_wild_once'):raise ValueError('Only Steven has a supported existing partner preset')
        from .canonical_world_actions import validate as validate_world_action
        validate_world_action(row.get('world_action'))
        if row.get('world_action') and 'native:'+row['world_action']['place'] not in row['places']:raise ValueError('World action must belong to actor interests')
        from .canonical_councils import validate as validate_council
        validate_council(row.get('council'))
        from .canonical_intentions import validate as validate_intentions
        validate_intentions(row,value,identity)
        from .canonical_collaboration import validate_fields
        validate_fields(row)
        interests=row.get('journey_interests',[])
        if type(interests) is not list or len(interests)>4 or any(type(r) is not str or not re.fullmatch('[0-9a-f]{64}',r) for r in interests) or len(set(interests))!=len(interests):raise ValueError('journey interests need up to four exact archived revisions')
        from .canonical_routines import validate as validate_routine
        validate_routine(row.get('routine'))
        from .canonical_cooperation import validate as validate_cooperation
        validate_cooperation(row,value,identity)
        from .canonical_construction import validate as validate_worksite
        validate_worksite(row.get('worksite'))
        from .canonical_studies import validate as validate_study
        validate_study(row.get('study'))
        from .canonical_projects import validate_project
        validate_project(row.get('project'))
        if row.get('project') and 'native:PetalburgCity' not in row['places']:raise ValueError('practice project needs PetalburgCity in actor interests')
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
        call=row.get('call')
        previous_call=(old.get(identity) or {}).get('call')
        if type(call) is dict and previous_call and call.get('id')==previous_call['id'] and call!=previous_call:raise ValueError('New call content requires a new request id')
        for revision in row.get('journey_interests',[]):
            if db.execute('SELECT 1 FROM generated_area_archive WHERE identity=?',(revision,)).fetchone() is None:raise ValueError('journey interest must name an existing archived map')
        from .canonical_intentions import selected
        selected(old.get(identity) or {},row)
        if any(db.execute('SELECT 1 FROM canonical_intent_receipts WHERE actor=? AND intention=?',(identity,t['id'])).fetchone() for t in row.get('intentions',[])):
            raise ValueError('completed intention cannot be returned to pending work')
        for seq in row['evidence']:
            event=db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()
            if event is None or not decision_evidence(json.loads(event[0]),identity,row):raise ValueError('canonical actor evidence must be an actual opted-in public activity in its interests')
        from .canonical_collaboration import validate_evidence
        validate_evidence(row,lambda n: json.loads(db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]))
        validate_letter(row,lambda n: json.loads(db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]))
        validate_relationship_evidence(row,lambda n: json.loads(db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]),identity)
        from .canonical_cooperation import check as check_cooperation
        check_cooperation(old.get(identity) or {},row,identity,new,lambda n: json.loads(db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0]))
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
    if type(action['changes']) is not dict or set(action['changes'])-{'activity_projects','scene','initiative','call','companion','world_action','council','journey_interests','routine','cooperate','worksite','study','offer','relationships','conversation','letter','project','contribution','resolve_contribution','intentions','fulfill'}!={'goal','dialogue','places','evidence','reason'}:raise ValueError('invalid canonical changes')
    old=cast.get(action['id']);version=old['version'] if old else 0
    call=action['changes'].get('call');previous_call=(old or {}).get('call')
    if type(call) is dict and previous_call and call.get('id')==previous_call['id'] and call!=previous_call:raise ValueError('New call content requires a new request id')
    if type(action['expected_version']) is not int or action['expected_version']!=version:raise ValueError('stale canonical action')
    row=copy.deepcopy(action['changes']);row['version']=version+1
    state.setdefault(KEY,{})[action['id']]=row;records(state)
    from .canonical_intentions import selected
    selected(old or {},row)
    known={e['seq']:e for e in context.get('recalled_history',{}).get('events',[])+data.get('world_memory',{}).get('recent',[])}
    if any(n not in known or not decision_evidence(known[n],action['id'],row) for n in row['evidence']):raise ValueError('canonical action requires inspected public activity evidence')
    from .canonical_collaboration import validate_evidence
    validate_evidence(row,lambda n: known[n])
    validate_letter(row,lambda n: known[n])
    validate_relationship_evidence(row,lambda n: known[n],action['id'])
    from .canonical_cooperation import check as check_cooperation
    check_cooperation(old or {},row,action['id'],state[KEY],lambda n:known[n])
    previous=context.get('runtime',{}).get('previous_source')
    if type(previous) is not str or hashlib.sha256(previous.encode()).hexdigest()!=data.get('module_hash'):raise ValueError('verified active source required')
    suffix=hashlib.sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest()[:16]
    helper=inspect.getsource(action_step).replace('def action_step(',f'def _cast_step_{suffix}(',1)
    return previous+'\n'+f'_cast_previous_{suffix}=update\n'+helper+f'\ndef update(context,state):\n    if not state:\n        import copy\n        state=copy.deepcopy({data.get("state",{})!r})\n    return _cast_step_{suffix}({actions!r}, {suffix!r}, _cast_previous_{suffix}(context,state))\n'


def response(server, conn, run, key):
    identity,map_name=location(key)
    if identity is None:raise ValueError('unknown canonical actor')
    server.core_story._place(conn,map_name)
    row=records(server.module_state).get(identity)
    if row is None:raise ValueError('no authored canonical response')
    from .canonical_activity_projects import visible
    row=visible(server,identity,row)
    private=server.db.execute('SELECT version,choice FROM canonical_conversations WHERE trainer=? AND actor=?',(conn['id'],identity)).fetchone()
    option=row.get('conversation',{}).get(private[1]) if private and private[0]==row['version'] else None
    from .canonical_reflection import private_reply
    personal=private_reply(server,conn['id'],identity,run,row['version'])
    result=dict(schema=1,world_id=server.memory.world_id,run=run,actor=identity,
                version=row['version'],briefing=personal or (option['reply'] if option else row['dialogue']),objective=('Guild chat has a shared question.' if row.get('council') else 'Guild chat has conversation choices.' if row.get('conversation') and not option else 'Ask guild chat about my plan.' if row.get('offer') else 'Guild chat has my field studies.' if row.get('study') else 'Guild chat has my practice courses.' if row.get('project') else ''),evidence=row['evidence'])
    if row.get('scene') and not result.get('objective'):result['objective']='Optional group demonstration. Use history scene.'
    if row.get('companion') and not result.get('objective'):result['objective']='Companion battle. Ask guild cast Steven.'
    if row.get('initiative') and not result.get('objective'):result['objective']='Guild cast initiatives lists my shared projects.'
    result['digest']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    conn['core_active_run']=run
    conn['canonical_location']=dict(actor=identity,map=map_name,run=run,version=row['version'],expires=time.monotonic()+120)
    from .canonical_memory import prepare
    return prepare(server,conn,run,identity,row,result,map_name=map_name)


def contract():
    return dict(response='canonical_actions/tests',bindings=BINDINGS,location_aliases=LOCATION_ALIASES,
                action_fields=['id','expected_version','changes'],
                change_fields=['activity_projects (optional owned-project outcome binding for existing companion/scene activities)', 'scene (optional Rydel only: rydel_step)', 'initiative (optional immutable public story pack with owner/actor turns and player-facing scenes)', 'call (optional Wally/Steven incoming request: stable id, literal text)', 'companion (Steven only: steven_wild_once)', 'world_action (exact available actor-owned shared story action)', 'council (optional question/options, mode unanimous or speaker; speaker-led conversation has up to four opted-in participants and advisory listeners)','goal','dialogue','places','evidence','reason','journey_interests (optional up to four exact archived revision digests)','routine (optional quiet-world decision interval)','cooperate (optional independent exact project join/decline)','worksite (optional authority construction plan)','study (optional archived-map exploration project)','offer (optional native map/count)','relationships (optional directional assessments)','conversation (optional private player choices)','letter (optional public cast correspondence)','project (optional playable practice course)','contribution (optional project guidance)','resolve_contribution (optional owner decision)','intentions (up to three retained tasks)','fulfill (one prior task ID)'],
                intentions=dict(fields=['id','kind (letter, project, study, construction, world_action, contribution or practice)','target','reason'],completion='set fulfill to a prior retained ID, remove it from agenda, execute the matching new action; authority requires a real action receipt',practice='target is an already host-registered fictional companion ID; isolated dispatcher only, no live fulfillment or story-party changes',initiative='followed actors may attempt retained work without a new player event; eight attempts per actor/world, once per task ID, no automatic retry or hidden model startup'),
                collaboration=dict(contribution=['course','digest','text (200 literal characters)'],resolve_contribution=['seq (proposal evidence)','decision (accept or decline)'],effect='another existing actor contributes to exact published project; owner decides; accepted text becomes actual activity briefing',limits='one contribution per actor/project; only public evidence, no inferred participation or private results'),
                routine=dict(fields=['interval_seconds (60..86400)'],effect='already followed actors may reconsider their own goals during quiet-world periods through the configured author runtime',limits='eight scheduled attempts per actor/world/UTC day; durable no-catch-up scheduling; no hidden worker startup, fake outcome or automatic XP',evidence='scheduled turns still cite inspected prior public evidence; clock passage is never outcome evidence'),
                cooperation=dict(fields=['owner','intention','signature','decision: join or decline'],invitation='worksite optional partners names up to two existing other actors; authority publishes exact signature',effect='each invited actor decides independently from its invitation; construction waits for all exact joins',limits='changed owner version/plan requires fresh agreement; no agreement inferred from silence or relationship; actual result lists participants and may inform their directional relationships'),
                scene=dict(kind='rydel_step',effect='original Rydel takes one native step and returns, synchronized across an opted-in room cohort',limits='every connected trainer ready in Bike Shop and independently joins; no bike service, save or reward changes; native geometry may refuse; no public completion inferred',access='/history scene ask, then each trainer uses /history scene join; cancel returns the actor home'),
                activity_projects=dict(format='activity name -> scene and requires ranges in own immutable initiative',effect='existing optional native activity becomes available only after that actor scene actually commits and shared qualities match',limits='companion or scene only, no automatic joining or native story/service changes; later project changes can close future admission'),
                initiative=dict(format='existing story pack: id, title, public place qualities and scenes',effect='atomic publication of an owned executable shared project; independent world_action intentions drive actor turns, players see current /story choices',limits='eight immutable projects per actor; existing actors only; no private qualities or mysteries; no physical work or rewards implied',access='/guild cast ACTOR initiatives; inspect.cast_initiatives contains real retained shared state'),
                incoming_calls=dict(fields=['id (stable lowercase, max 24)','text (literal max 160)'],actors=['canon_wally','canon_steven'],effect='request an optional real Match Call for already registered players; no named player targeting',limits='one automatic delivery per request and save; ten-minute cadence; quiet/decline/check; private dispositions never enter author evidence, so do not claim a recipient answered'),
                companion=dict(kind='steven_wild_once',actor='canon_steven',effect='explicit one-shot invitation for original Steven partner team in one ordinary wild battle; no follower or campaign battle change',command='/history companion steven then /history companion confirm after talking to original Steven',limits='requires paired native adapter, own post-Dive story state, full-team configuration and no active co-op; normal wild battle effects, no earned NPC growth'),
                world_action=dict(fields=['pack','scene','choice','place','revision'],intention='kind world_action, target pack; authority executes once, never author fulfill',source='inspect.cast_world_actions lists existing explicitly actor-owned public choices',effect='changes shared story qualities and available player scenes; no physical travel, native progression or player turn'),
                construction=dict(fields=['worksite: revision, label, plan {x,y,width,height,gate,reservations}'],intention='kind construction; target exact source revision; normal authority loop executes once when map empty, not author fulfill',effect='existing compiler adds bounded courtyard and access trail while preserving prior walkable terrain, map continuity and scoped NPCs',limits='plain XL only, eight per actor, no animated labor, travel, resources or player work; no story/save edits',access='/guild cast ACTOR construction'),
                study=dict(fields=['revision (exact archived plain XL digest)','title (55 literal characters)','sites (2..8 unique id/x/y walkable sites)'],effect='installs an immutable optional private survey on existing map geometry; no terrain edits or character travel',initiative='study intention target is the exact revision; fulfill only after actual survey installation',feedback='only explicit anonymous player shares become public evidence for the owning actor; unshared visits never enter author context',access='/guild cast ACTOR studies then /explore start inside the exact active map',limits='eight per actor; existing surveys cannot be overwritten; no activation, warp, reward or autojoin'),
                project=dict(kind='petalburg_relay',fields=['title (55 characters)','limit (30..900 seconds)','mounted (boolean)'],effect='installs an immutable playable two-runner relay on existing Petalburg layout; no player autojoin, terrain or save change',limits='eight per actor; actual publication evidence, no inferred participation or results'),
                letter=dict(fields=['to (existing canonical identity)','text (200 literal characters)'],effect='authority delivers a public in-world letter and records exact evidence; no physical meeting',basis='public activity or received letter; at most two deliveries per reply chain; recipient may reconsider goals or respond'),
                conversation=dict(choice='1..3 lowercase IDs',fields=['label (48 literal characters)','reply (200 literal characters)'],privacy='only player explicitly selects their own option; selection never enters world history or author context',scope='per authenticated trainer and actor; actor version changes require choosing again; no auto affinity, gifts or story changes'),
                relationships=dict(target='another existing bound canonical actor, not a player',fields=['stance','motivation','evidence'],stances=['curious','encouraged','concerned','respectful','competitive'],basis='actual public completion or committed shared-world choice attributed to target actor; directional interpretation, not mutual relationship or invented meeting',reaction='actual public target-offer results and committed shared-world actions in actor interests trigger reconsideration; never a proposed action alone'),
                optional_offer=dict(map='canonical native map in places',count='1..50 distinct guild trainers',acceptance='/guild cast ACTOR previews; leader accepts exact version; chronicle must already be on',outcome='actual authenticated guild presence, not actor personal achievements'),
                effects='supplement original bound actor dialogue only; no spawned duplicate, save flag, team, reward, bike exchange or main script change',
                evidence='actual explicitly shared canonical_story_outcome for existing Woods ambush/Peeko rescue beats in selected native places, opted-in public guild_goal_completed, or other supported public actor activity; private REPORT/SYNC never qualifies; native story is client attestation, not simulated proof or this actor personal achievement',
                native='requires paired CAST safe-point adapter; original story continues offline or on refusal')


def guild_command(server, conn, args):
    """Explicit preview/accept, only at the original actor's location.

    Existing guild authority owns consent, frozen receipts, visits and rewards.
    Actor version binds ALL displayed terms; accepting never publishes old history.
    """
    from .guilds import GuildError
    if len(args) not in (1,2,3,4):
        return ['Use /guild cast ACTOR to preview a public field proposal. Actors: rydel, wally, briney, steven.']
    identity=next((i for i,b in BINDINGS.items() if b['wire']==args[0]),None)
    if identity is None:raise GuildError('Unknown canonical actor.')
    if server.peers.get(conn.get('id')) is not conn:raise GuildError('Authenticated trainer connection required.')
    if len(args)>1 and args[1] in ('converse','listen','conversation','advise','choose','leave'):
        from .canonical_dialogues import command
        return command(server,conn,identity,records(server.module_state).get(identity),args[1:])
    if len(args)>1 and args[1] in ('reflect','reflection'):
        from .canonical_reflection import command
        return command(server,conn,identity,args[1:])
    if len(args)>1 and args[1] in ('remember','memory'):
        from .canonical_memory import command
        return command(server,conn,identity,args[1:])
    if len(args)==3 and args[1]!='decide':raise GuildError('Use /guild cast ACTOR remember on|off.')
    if args[1:]==['forget']:return conversation_command(server,conn,identity,None,['forget'])
    if not (conn.get('state') or [0]*7)[6]:
        raise GuildError('Stand ready near the original actor before accepting a proposal.')
    try:check_actor_location(server,conn,identity)
    except ValueError:raise GuildError('Visit the original actor before reviewing or accepting a proposal.')
    row=records(server.module_state).get(identity)
    from .canonical_activity_projects import visible
    row=visible(server,identity,row);offer=(row or {}).get('offer')
    if (len(args)==1 or args[1:]==['companion']) and (row or {}).get('companion'):
        return ['Steven offers his original partner team for one ordinary wild battle.', 'No follower or campaign battle changes. Normal battle HP, EXP, items and catching apply.', '/history companion steven previews; /history companion confirm requests it.']
    if len(args)==1 and (row or {}).get('council'):
        shared=row['council'];mode='converse' if shared.get('mode','unanimous')=='speaker' else 'council'
        return [shared['question'],'Use /guild cast '+BINDINGS[identity]['wire']+' '+mode+' to review the shared conversation.']
    if len(args)>=2 and args[1] in ('council','decide'):
        from .canonical_councils import command
        return command(server,conn,identity,row,args[1:])
    if len(args)>=2 and args[1] in ('talk','forget'):
        return conversation_command(server,conn,identity,row,args[1:])
    if len(args)==4:raise GuildError('Use /guild cast ACTOR talk VERSION CHOICE.')
    if len(args)==2 and args[1]=='initiatives':
        from .canonical_initiatives import lines
        return lines(server,identity)
    if len(args)==2 and args[1]=='construction':
        from .canonical_construction import lines
        return lines(server,identity)
    if len(args)==2 and args[1]=='studies':
        from .canonical_studies import lines
        return lines(server,identity)
    if len(args)==2 and args[1]=='projects':
        from .canonical_projects import lines
        return lines(server,identity)
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
        if row.get('routine'):lines.append('Quiet-world decision interval: '+str(row['routine']['interval_seconds'])+' seconds, when the author service is running.')
        for task in row.get('intentions',[]):
            lines.append('Pending '+task['kind']+': '+task['target'])
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
    from .canonical_initiatives import relevant as initiative_relevant
    if initiative_relevant(event,identity,row):return True
    from .canonical_dialogues import relevant as dialogue_relevant
    if dialogue_relevant(event,identity):return True
    from .canonical_councils import relevant as council_relevant
    if council_relevant(event,identity):return True
    from .campaign_milestones import relevant as milestone_relevant
    if milestone_relevant(event,row.get('places',[])):return True
    from .core_story import shared_outcome
    if shared_outcome(event,row.get('places',[])):return True
    from .character_reconnaissance import observed as survey_observed
    if survey_observed(event,row.get('journey_interests',[])):return True
    from .character_encounters import observed as encounter_observed
    if encounter_observed(event,row.get('journey_interests',[])):return True
    from .character_journeys import relevant as journey_relevant
    if journey_relevant(event,row.get('journey_interests',[])):return True
    from .canonical_cooperation import relevant as cooperation_relevant
    if cooperation_relevant(event,identity):return True
    from .canonical_world_actions import relevant as world_action_relevant
    if world_action_relevant(event,identity,row):return True
    from .canonical_construction import relevant as construction_relevant
    if construction_relevant(event,identity):return True
    from .canonical_studies import relevant as study_relevant
    if study_relevant(event,identity):return True
    from .canonical_intentions import fulfilled
    if fulfilled(event,identity):return True
    from .canonical_collaboration import relevant
    if relevant(event,identity):return True
    if received_letter(event,identity):return True
    if not public_activity(event,row.get('places',[])):return False
    if event.get('character_id') in row.get('relationships',{}) and event.get('character_offer_id')=='field_plan':return True
    if not row.get('offer'):return True
    return (event.get('character_id')==identity and event.get('character_offer_id')=='field_plan'
            and event.get('character_offer_revision')==row['version'])


def validate_relationship_evidence(row, lookup, identity):
    for target,relation in row.get('relationships',{}).items():
        for seq in relation['evidence']:
            event=lookup(seq)
            from .canonical_initiatives import assessment
            if assessment(event,identity,target,row):continue
            from .canonical_cooperation import shared_result
            if shared_result(event,identity,target):continue
            if (not public_activity(event,row['places']) or event.get('character_id')!=target
                    or event.get('character_offer_id')!='field_plan'
                    or type(event.get('character_offer_revision')) is not int):
                raise ValueError('relationship needs real public completion of the target actor proposal')


def conversation_command(server, conn, identity, row, args):
    """Own authenticated conversation only. No broadcast, history or GM input."""
    from .guilds import GuildError
    if args==['forget']:
        with server.db:
            from .canonical_memory import forget
            forget(server,conn,identity)
            server.db.execute('DELETE FROM canonical_conversations WHERE trainer=? AND actor=?',(conn['id'],identity))
        return ['Your choice and encounter memories were erased. Remembering is off; other trainers are unchanged.']
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
    from .canonical_initiatives import relevant as initiative_relevant
    if initiative_relevant(event,identity,row):return True
    from .canonical_dialogues import relevant as dialogue_relevant
    if dialogue_relevant(event,identity):return True
    from .canonical_councils import relevant as council_relevant
    if council_relevant(event,identity):return True
    from .campaign_milestones import relevant as milestone_relevant
    if milestone_relevant(event,row.get('places',[])):return True
    from .core_story import shared_outcome
    if shared_outcome(event,row.get('places',[])):return True
    from .canonical_projects import public_project
    from .canonical_collaboration import relevant
    from .canonical_intentions import fulfilled
    from .character_reconnaissance import observed as survey_observed
    if survey_observed(event,row.get('journey_interests',[])):return True
    from .character_encounters import observed as encounter_observed
    if encounter_observed(event,row.get('journey_interests',[])):return True
    from .character_journeys import relevant as journey_relevant
    if journey_relevant(event,row.get('journey_interests',[])):return True
    from .canonical_cooperation import relevant as cooperation_relevant
    if cooperation_relevant(event,identity):return True
    from .canonical_world_actions import relevant as world_action_relevant
    if world_action_relevant(event,identity,row):return True
    from .canonical_construction import relevant as construction_relevant
    if construction_relevant(event,identity):return True
    from .canonical_studies import relevant as study_relevant
    return study_relevant(event,identity) or fulfilled(event,identity) or relevant(event,identity) or public_activity(event,row['places']) or received_letter(event,identity) or public_project(event,row['places'])


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


def remote_response(server,conn,run,key):
    """Supplement an existing registered native Match Call, never impersonate a visit."""
    if key not in ('wally','steven') or conn.get('core_active_run')!=run:
        raise ValueError('Match Call requires a supported original contact and current save context')
    identity='canon_'+key;row=records(server.module_state).get(identity)
    if row is None:raise ValueError('No authored response for this contact')
    selected=server.db.execute('SELECT version,choice FROM canonical_conversations WHERE trainer=? AND actor=?',(conn['id'],identity)).fetchone()
    option=row.get('conversation',{}).get(selected[1]) if selected and selected[0]==row['version'] else None
    result=dict(world_id=server.memory.world_id,run=run,actor=identity,version=row['version'],
                briefing=option['reply'] if option else row['dialogue'],objective='')
    result['digest']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result
