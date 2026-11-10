"""Model-authored plans over registered authority capabilities, not character arcs.

Local effects use transactions. Staged asynchronous tools supply an explicit
completion adapter; issuing a request is never completion.
"""
from dataclasses import dataclass
import copy,json,re,time

@dataclass(frozen=True)
class Capability:
    description: str
    arguments: dict
    outcome: str
    execute: object
    poll: object = None
    kinds: tuple = ('canonical',)

@dataclass
class Committed:
    seq: int
    result: dict

@dataclass
class Pending:
    data: dict
    dispatch: object


def _project(server,actor,row,args):
    from .canonical_world_actions import validate
    validate(args)
    if 'native:'+args['place'] not in row['places']:raise ValueError('Action is outside current actor interests')
    result=server.opportunities.actor_choose(actor,args)
    return dict(revision=result['revision'],changes=result['changes'],text=result['text'])


def _message(server,actor,row,args):
    from .canonical_cast import records,validate_letter,deliver_letter
    if set(args)!={'to','text'} or args['to']==actor or args['to'] not in records(server.module_state):raise ValueError('Message needs another existing actor')
    if type(args['text']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,200}",args['text']):raise ValueError('Message needs bounded public literal text')
    after=dict(row,letter=args)
    lookup=lambda n:json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(n,)).fetchone()[0])
    validate_letter(after,lookup)
    deliver_letter(server,dict(character_id=actor,before={},after=after))
    return dict(receipt=server.revision,recipient=args['to'],delivery='public_correspondence_delivered')

# Registration is host code, not arbitrary code or a tool supplied by a model.
CAPABILITIES={
    'world.act':Capability('Execute an available shared-state action assigned to this actor.',
        dict(pack='id',scene='id',choice='id',place='native map name',revision='integer or prior result reference'),
        'Actual shared state revision/changes; no native travel, inventory or XP.',_project),
    'actor.message':Capability('Deliver public speech to another existing actor without commanding its response.',
        dict(to='existing actor id',text='1..200 literal public characters'),
        'Delivered correspondence receipt, never agreement or physical meeting.',_message),
}

from .actor_navigation import start as navigate, poll as navigation_poll
CAPABILITIES['world.navigate']=Capability('Navigate this world-owned actor to a destination using actual immutable geometry.',dict(revision='exact generated-map revision',x='destination integer',y='destination integer'),'Actual authority arrival receipt; never client rendering or canonical/cross-map travel.',navigate,navigation_poll,('world',))

from .actor_observation import observe
CAPABILITIES['world.observe']=Capability('Inspect connected local geometry and public world objects at this actor current authoritative position.',dict(radius='integer 1..4 cardinal steps'),'Dated local snapshot only; no player/private data, inferred encounters or rendered eyesight.',observe,None,('world',))

from .actor_geometry import open_ground
CAPABILITIES['world.open_ground']=Capability('Open a bounded patch of observed local ground on an empty active plain shared XL map.',dict(observation='own successful observation receipt sequence',x='patch origin integer',y='patch origin integer',width='integer 1..5',height='integer 1..5'),'Actual immutable geometry revision and preserved character positions; abstract terrain change, not simulated labor or resources.',open_ground,None,('world',))

from .actor_population import spawn as spawn_population, poll as poll_population
CAPABILITIES['world.populate']=Capability('Stage a new original persistent character or typed prop on exact supported generated geometry.',dict(revision='exact plain opened-region or shared XL revision',definition='JSON <=700 chars: id,kind character/prop,x,y,gfx,text; character adds name,role,goals,team [{species,level}]; prop adds portable boolean. Character gfx7/8; prop gfx0/1. No canonical duplicates.'),'Actual validated durable population only; new fictional records are not proven autonomous model instances, catches or travel.',spawn_population,poll_population,('canonical','world'))

from .actor_places import create as create_place, create_habitat
CAPABILITIES['world.create_habitat']=Capability('Create a separate immutable cave populated through native Expansion wild encounter tables.',dict(label='literal menu label 1..20 ASCII characters',blueprint='Same bounded room/link JSON as world.create_place',population='JSON string: profile granite/meteor/ice/victory, rate 1..100, slots exactly 12 [enabled Expansion species name,level 1..100] pairs; normal step size bound applies'),'Archived selectable CAVE10+REGION1 destination with real native wildlife data. No catch, victory, NPC training, player bag or travel fabricated.',create_habitat,None,('canonical','world'))
CAPABILITIES['world.create_place']=Capability('Compile and open a new persistent selectable plain cave without replacing existing maps.',dict(label='literal menu label 1..20 ASCII characters',blueprint='JSON string <=700 chars: rooms [[x,y,width,height]], links [[room_index,room_index]], entrance_room, exit_room; optional style rooms/rounded/organic/maze, seed uint32, corridor_width 1..3; interior 1..29'),'Actual archived immutable 31x31 region and place ID. REGION1 clients select it then use existing entrance; no seamless portals, player visits or actor travel asserted.',create_place,None,('canonical','world'))

from .actor_space import extend as extend_space
CAPABILITIES['world.extend_space']=Capability('Add connected clearings and routes to this actor active plain XL place, preserving all existing ground.',dict(revision='exact active generated revision',blueprint='JSON string <=800 chars: seed uint32, loops 0..4, landmarks 2..12 {id,x,y,radius 2..10}, reservations 0..32 [x,y,width,height]; interior 1..125; no overlapping clearings or reserved existing floor'),'Committed connected geometry, same logical place and rebound actors. Empty-map publication only; no portals, new artwork, simulated labor or resource claims.',extend_space,None,('world',))

from .actor_social import approach,address,poll_approach
CAPABILITIES['world.approach']=Capability('Compute and execute a route beside another inspected world character.',dict(target='existing world actor id',expected_version='inspected recipient version'),'Actual authority arrival or already-adjacent state, not speech or a guarantee recipient remains.',approach,poll_approach,('world',))
CAPABILITIES['world.address']=Capability('Speak publicly to an adjacent world character; recipient decides independently what to do.',dict(target='existing world actor id',expected_version='inspected recipient version',text='1..28 literal public characters'),'Actual adjacency-validated encounter receipt; no automatic reply, relationship or rendered speech.',address,None,('world',))

from .actor_objects import use as use_object,poll as poll_object
CAPABILITIES['world.use_object']=Capability('Invoke an explicitly advertised local object handler through normal mechanic validation.',dict(object='observed non-character object id',action='advertised action id',object_revision='exact observed object/source revision'),'Committed own object state, text/appearance or one-cell position change. No native items, inventory or implied rewards.',use_object,poll_object,('world',))

from .prop_custody import take as take_prop,place as place_prop
CAPABILITIES['world.take_prop']=Capability('Take an existing explicitly portable adjacent world prop into authority custody.',dict(object='observed portable prop id',object_revision='observed portable_revision'),'Exclusive durable custody; prop disappears from map. No native inventory or resource minting.',take_prop,None,('world',))
CAPABILITIES['world.place_prop']=Capability('Place an owned prop beside this actor on the same exact generated map.',dict(object='owned prop id',version='current custody version',x='adjacent integer',y='adjacent integer'),'Same prop identity restored to actual map with collision validation; no carrying animation.',place_prop,None,('world',))

def actor_records(server):
    from .character_reactions import actors
    rows=actors(server.module_state)
    from .world_memory import native_place
    for actor,row in rows.items():
        if row.get('canonical'):continue
        obj=next((o for o in server.objects if o['id']==actor),None)
        row=dict(row,places=([native_place(obj['group'],obj['num'])] if obj else []));rows[actor]=row
    return rows

def install(db):
    from .actor_agreements import setup as agreement_setup
    agreement_setup(db)
    from .actor_attention import setup as attention_setup
    attention_setup(db)
    from .companion_barter import setup as barter_setup
    barter_setup(db)
    from .actor_cooperation import setup as cooperation_setup
    cooperation_setup(db)
    from .npc_guidance import setup as guidance_setup
    guidance_setup(db)
    from .npc_accompaniment import setup as accompaniment_setup
    accompaniment_setup(db)
    from .actor_battle_formats import setup as format_setup
    format_setup(db)
    from .actor_tutors import setup as tutor_setup
    tutor_setup(db)
    from .actor_weather import setup as weather_setup
    weather_setup(db)
    from .shared_outbreaks import setup as outbreak_setup
    outbreak_setup(db)
    from .shared_fishing import setup as fishing_setup
    fishing_setup(db)
    from .rental_pools import setup as rental_setup
    rental_setup(db)
    from .contest_guests import setup as contest_setup
    contest_setup(db)
    from .actor_shops import setup as shop_setup
    shop_setup(db)
    from .actor_capture import setup as capture_setup
    capture_setup(db)
    from .npc_conversations import install as install_speech
    install_speech(db)
    from .actor_knowledge import setup as knowledge_setup
    knowledge_setup(db)
    db.execute('CREATE TABLE IF NOT EXISTS actor_plans(actor TEXT,plan TEXT,definition TEXT NOT NULL,PRIMARY KEY(actor,plan))')
    db.execute('CREATE TABLE IF NOT EXISTS actor_tool_receipts(actor TEXT,plan TEXT,step TEXT,status TEXT,result TEXT,seq INTEGER,PRIMARY KEY(actor,plan,step))')


def validate(plan):
    if plan is None:return
    if type(plan) is not dict or set(plan)!={'id','purpose','steps'}:raise ValueError('Plan requires id, purpose and steps')
    def identifier(v):return type(v) is str and bool(re.fullmatch('[a-z][a-z0-9_]{0,23}',v))
    if not identifier(plan['id']) or type(plan['purpose']) is not str or not 1<=len(plan['purpose'])<=240 or any(not 32<=ord(c)<=126 for c in plan['purpose']):raise ValueError('Invalid plan identity or purpose')
    if type(plan['steps']) is not list or not 1<=len(plan['steps'])<=6:raise ValueError('Plan requires 1..6 bounded tool steps')
    seen=set()
    for step in plan['steps']:
        if type(step) is not dict or not {'id','tool','args','after'}<=set(step) or set(step)-{'id','tool','args','after','when'}:raise ValueError('Step needs id, tool, args and after')
        if not identifier(step['id']) or step['id'] in seen or type(step['tool']) is not str or step['tool'] not in CAPABILITIES:raise ValueError('Unknown tool or repeated step')
        if type(step['after']) is not list or any(type(s) is not str for s in step['after']) or len(set(step['after']))!=len(step['after']) or not set(step['after'])<=seen:raise ValueError('Dependencies must be earlier step IDs')
        if 'when' in step:
            from .actor_conditions import validate as validate_condition
            validate_condition(step['when'],step['after'])
        if type(step['args']) is not dict or set(step['args'])!=set(CAPABILITIES[step['tool']].arguments):raise ValueError('Tool arguments do not match advertised capability')
        for value in step['args'].values():
            if type(value) is dict:
                if set(value)!={'result','key'} or value['result'] not in step['after'] or not identifier(value['key']):raise ValueError('Result reference needs a declared prior dependency and scalar key')
            elif type(value) not in (str,int) or isinstance(value,bool):raise ValueError('Tool arguments must be scalar or result references')
        if len(json.dumps(step))>1024:raise ValueError('Tool step exceeds bounded size')
        seen.add(step['id'])


def definition(plan):return json.dumps(plan,sort_keys=True,separators=(',',':'))


def inspect_runtime(server):
    from .actor_agreements import discover as agreement_discover
    from .canonical_cast import records
    install(server.db)
    from .prop_custody import inventory
    from .companion_barter import offers as barter_offers
    from .actor_cooperation import discover as cooperation_discover
    from .npc_guidance import discover as guidance_discover
    from .npc_accompaniment import inbox as accompaniment_inbox
    from .companion_exchange import offers as companion_offers
    from .actor_attention import discover as attention_discover
    from .actor_navigation import discover as discover_navigation
    from .actor_linked_navigation import graph as linked_graph
    from .character_companions import roster
    from .actor_knowledge import inbox as knowledge_inbox
    from .npc_conversations import inbox as speech_inbox
    from .actor_capture import available as capture_available
    from .actor_shops import catalog as shop_catalog
    from .actor_tutors import catalog as tutor_catalog
    from .shared_outbreaks import catalog as outbreak_catalog
    from .contest_guests import available as contest_available
    from .region_networks import catalog as region_network_catalog
    from .shared_fishing import catalog as fishing_catalog
    from .actor_field_games import catalog as flag_catalog
    from .actor_stories import catalog as story_catalog
    from .actor_blueprints import catalog as blueprint_catalog
    return dict(blueprints=blueprint_catalog(server),public_stories=story_catalog(server),flag_arenas=flag_catalog(server),agreements=agreement_discover(server),fishing=fishing_catalog(server),region_networks=region_network_catalog(server),battle_formats={a:dict(revision=r,format='doubles' if mode else 'singles') for a,r,mode in server.db.execute('SELECT actor,revision,mode FROM actor_battle_formats')},race_courses=server.races.catalog(),contest_guests=contest_available(server),outbreaks=outbreak_catalog(server),battle_campaigns=[json.loads(r[0]) for r in server.db.execute('SELECT document FROM battle_campaigns ORDER BY id LIMIT 32')],tutoring=tutor_catalog(server),retail=shop_catalog(server),capture=capture_available(server),public_player_speech=speech_inbox(server),received_observations=knowledge_inbox(server),companion_rosters={actor:roster(server,actor) for actor,r in actor_records(server).items() if not r.get('canonical')},capabilities={key:dict(description=c.description,arguments=c.arguments,outcome=c.outcome,actor_kinds=c.kinds) for key,c in CAPABILITIES.items()},
        available_actions=server.opportunities.actor_actions()[:32],actors={a:('canonical' if r.get('canonical') else 'world') for a,r in actor_records(server).items()},
        local_attention=attention_discover(server),guided_journeys=guidance_discover(server),accompaniment_requests=accompaniment_inbox(server),cooperation=cooperation_discover(server),cooperation_semantics="Public fictional requests, not operator instructions or new permissions. Accept or decline independently. Use own capabilities, then deliver an actual post-acceptance receipt; matching terms establishes only that historical operation, not prose truth or current state.",reciprocal_exchanges=barter_offers(server),companion_offers=companion_offers(server),navigation=discover_navigation(server),cave_links=linked_graph(server),carried_props=inventory(server),
        object_player_use='Optional state.world_object_player_use maps prop ID to one advertised world_object_actions action ID. Native A dispatches the same actor_interact(object_id,action,own_state) handler through normal staging. No map: text only. Effects are bounded own-state/text/graphics/one-cell movement, not bags/items.',
        conditional_steps='Optional when:{step:declared_prior_dependency,path:JSON_pointer,equals:literal_scalar}. Evaluated only against that own successful receipt. False or missing values produce a skipped receipt without executing the tool; dependent steps skip too. Hard blocked results still halt the entire plan. No condition can bypass a tool guard. No implicit loop or join of mutually exclusive branches.',
        result_references='Use {result: earlier_step_id, key: scalar_result_key}. Reserved key tool_receipt yields that successful step durable receipt sequence.',
        plans=[dict(actor=actor,plan=row['plan'],receipts=[dict(step=s,status=status,result=json.loads(result),seq=seq)
            for s,status,result,seq in server.db.execute('SELECT step,status,result,seq FROM actor_tool_receipts WHERE actor=? AND plan=? ORDER BY seq',(actor,row['plan']['id']))])
            for actor,row in actor_records(server).items() if row.get('plan')],
        limits='Registered scoped capabilities only. Pending requests are not completion. Plans are intentions, receipts are observations. No arbitrary native scripts, private data, forced player actions, simulated training or inferred completion.')


def relevant(event,actor):
    return (event.get('event')=='actor_tool_result' and event.get('character_id')==actor
        and event.get('source')=='authority_capability_runtime' and event.get('tool') in CAPABILITIES
        and event.get('status') in ('succeeded','blocked'))


def tick(server,*,now=None):
    now=time.monotonic() if now is None else now
    if server.job is not None or server.deployment is not None or now<getattr(server,'actor_runtime_next',0):return None
    server.actor_runtime_next=now+5
    from .canonical_cast import records
    install(server.db)
    from .actor_attention import tick as attention_tick
    attention_tick(server)
    current=actor_records(server)
    for actor,plan_id,step_id in server.db.execute("SELECT actor,plan,step FROM actor_tool_receipts WHERE status='pending'").fetchall():
        row=current.get(actor)
        if row and (row.get('plan') or {}).get('id')==plan_id:continue
        saved=server.db.execute('SELECT definition FROM actor_plans WHERE actor=? AND plan=?',(actor,plan_id)).fetchone()
        if saved:
            plan=json.loads(saved[0]);step=next(s for s in plan['steps'] if s['id']==step_id)
            record=row or dict(version=0,evidence=[],places=[])
            with server.db:seq=_receipt(server,actor,record,plan,step,'blocked',dict(reason='Plan withdrawn or actor unavailable; completion not asserted.'))
            return dict(actor=actor,plan=plan_id,step=step_id,status='blocked',seq=seq)
    for actor,row in sorted(current.items()):
        plan=row.get('plan')
        if not plan:continue
        validate(plan)
        encoded=definition(plan)
        with server.db:
            prior=server.db.execute('SELECT definition FROM actor_plans WHERE actor=? AND plan=?',(actor,plan['id'])).fetchone()
            if prior and prior[0]!=encoded:continue # Admission normally rejects this; never execute a changed identity.
            server.db.execute('INSERT OR IGNORE INTO actor_plans VALUES(?,?,?)',(actor,plan['id'],encoded))
        receipts={s:(status,json.loads(result)) for s,status,result in server.db.execute('SELECT step,status,result FROM actor_tool_receipts WHERE actor=? AND plan=?',(actor,plan['id']))}
        if any(status=='blocked' for status,_ in receipts.values()):continue # Replan explicitly, never blind retry.
        pending_steps={s for s,(status,_) in receipts.items() if status=='pending'}
        for step in plan['steps']:
            if pending_steps and step['id'] not in pending_steps:continue
            if step['id'] in receipts and receipts[step['id']][0]!='pending':continue
            if not all(s in receipts and receipts[s][0] in ('succeeded','skipped') for s in step['after']):continue
            from .actor_conditions import matches as condition_matches
            if (any(receipts[s][0]=='skipped' for s in step['after'])
                or ('when' in step and not condition_matches(step['when'],receipts))):
                with server.db:seq=_receipt(server,actor,row,plan,step,'skipped',dict(executed=False,reason='dependency_skipped' if any(receipts[s][0]=='skipped' for s in step['after']) else 'condition_not_matched'))
                return dict(actor=actor,plan=plan['id'],step=step['id'],status='skipped',seq=seq)
            old_revision=server.revision
            try:
                with server.db:
                    capability=CAPABILITIES[step['tool']]
                    if ('canonical' if row.get('canonical') else 'world') not in capability.kinds:raise ValueError('Capability is unavailable for this actor kind')
                    if step['id'] in receipts:
                        result=capability.poll(server,actor,row,receipts[step['id']][1])
                        if result is None:continue
                        seq=_receipt(server,actor,row,plan,step,'succeeded',result)
                        return dict(actor=actor,plan=plan['id'],step=step['id'],status='succeeded',seq=seq)
                    args=copy.deepcopy(step['args'])
                    for key,value in args.items():
                        if type(value) is dict:
                            result=receipts[value['result']][1]
                            if value['key']=='tool_receipt':
                                args[key]=server.db.execute('SELECT seq FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',(actor,plan['id'],value['result'])).fetchone()[0]
                                continue
                            if value['key'] not in result or type(result[value['key']]) not in (str,int):raise ValueError('Unavailable scalar result reference')
                            args[key]=result[value['key']]
                    server.actor_tool_execution=(actor,row,plan,step)
                    try:result=CAPABILITIES[step['tool']].execute(server,actor,row,args)
                    finally:server.actor_tool_execution=None
                    if isinstance(result,Committed):
                        return dict(actor=actor,plan=plan['id'],step=step['id'],status='succeeded',seq=result.seq)
                    if isinstance(result,Pending):
                        server.db.execute('INSERT INTO actor_tool_receipts VALUES(?,?,?,?,?,NULL)',(actor,plan['id'],step['id'],'pending',json.dumps(result.data,sort_keys=True)))
                    else:seq=_receipt(server,actor,row,plan,step,'succeeded',result)
                if isinstance(result,Pending):
                    result.dispatch()
                    return dict(actor=actor,plan=plan['id'],step=step['id'],status='pending')
                return dict(actor=actor,plan=plan['id'],step=step['id'],status='succeeded',seq=seq)
            except ValueError as exc:
                server.revision=old_revision
                with server.db:seq=_receipt(server,actor,row,plan,step,'blocked',dict(reason=str(exc)[:240]))
                return dict(actor=actor,plan=plan['id'],step=step['id'],status='blocked',seq=seq)
    return None


def _receipt(server,actor,row,plan,step,status,result):
    seq=server.memory.append('actor_tool_result',dict(character_id=actor,plan=plan['id'],step=step['id'],tool=step['tool'],status=status,result=result,
        character_version=row['version'],based_on=row['evidence'],places=row['places'],source='authority_capability_runtime',
        limits=CAPABILITIES[step['tool']].outcome))
    server.db.execute('INSERT OR REPLACE INTO actor_tool_receipts VALUES(?,?,?,?,?,?)',(actor,plan['id'],step['id'],status,json.dumps(result,sort_keys=True),seq))
    server.revision=seq
    return seq

from .actor_landscapes import create as create_landscape
CAPABILITIES['world.create_landscape']=Capability('Compile and activate a new outdoor XL layout in the shared destination, archiving prior geometry.',dict(label='literal label 1..20 ASCII characters',layout='clearings or connected_shapes',blueprint='JSON <=800 chars. clearings: seed, loops, landmarks [{id,x,y,radius}], reservations [[x,y,w,h]]. connected_shapes: rooms [[x,y,w,h]], links [[a,b]], entrance_room, exit_room; optional style rooms/rounded/organic/maze, seed, corridor_width 1..3. Interior 1..125.'),'Actual 127x127 CAVE16 outdoor destination and stable place ID. Refuses occupied or populated active maps. Existing native grass/obstacle palette only, not new biome art, seamless travel or actor labor.',create_landscape,None,('canonical','world'))

from .actor_watch import start as watch, poll as watch_poll
CAPABILITIES['world.await_entity']=Capability('Wait for a real nearby entity to appear or visibly change, without repeated model calls.',dict(observation='own successful world.observe receipt sequence',target='existing world object identity',condition='present or changed'),'Durable pending watch; completes only on actual local observation. Observer relocation or geometry revision blocks; unseen targets reveal nothing.',watch,watch_poll,('world',))

from .actor_challenges import prepare as prepare_challenge, poll as challenge_poll
CAPABILITIES['world.prepare_challenge']=Capability('Prepare this trainer optional native challenge with an ordered lineup of owned individual Pokemon.',dict(lineup='JSON list of 1..6 distinct individual IDs from companion_rosters for this actor',text='literal invitation up to 28 ASCII characters'),'Actual admitted lineup and invitation; no forced battle, catch, growth or win. Existing native player consent and CHARPK1/CHARPK2 compatibility remain required.',prepare_challenge,challenge_poll,('world',))

from .actor_practice import request as practice_request,poll as practice_poll
CAPABILITIES['world.practice']=Capability('Request isolated host practice for an actual on-team individual companion.',dict(individual='owned on-team individual ID from companion_rosters'),'Pending until separately enabled exact-binary QA-validated host runner reconciles full state. Host controls exercise limits; no battle, victory, evolution or player-save effect asserted.',practice_request,practice_poll,('world',))

from .actor_events import start as event_wait,poll as event_poll
CAPABILITIES['world.await_event']=Capability('Wait for a future committed public world event without repeated model calls.',dict(event='public world history event type',where='JSON object <=600 chars with up to four exact top-level scalar filters; empty object matches any event of this type'),'First actual matching record after subscription, with event_seq, payload and scalar event_FIELD results for composition. Durable bounded paging; not private information, direct perception or an invented outcome. One-shot; agent chooses whether to subscribe again.',event_wait,event_poll,('canonical','world'))

from .actor_object_programs import install as program_object,poll as program_poll
CAPABILITIES['world.program_object']=Capability('Install a reusable interactive state machine on an observed unprogrammed anchored prop.',dict(object='observed prop ID',revision='observed program_revision',program='JSON <=700 chars: initial state name, states {name:{text <=28 ASCII,gfx 0/1,on:{action:next_state},use:action or empty, optional choices:[player_action]}}; 1..4 states, up to4 transitions each. Native A invokes use; /guild object choices exposes only explicitly listed player choices; agents choose advertised actions.'),'Admitted persistent prop program through normal mechanic staging. Appearance, text and available actions change through real player/agent use; no bag, rewards, movement or claimed interactions.',program_object,program_poll,('world',))

from .cave_links import install as install_cave_link
CAPABILITIES['world.link_caves']=Capability('Bind an observed unused anchored prop to another already-opened plain cave.',dict(object='observed anchored prop ID',revision='observed program_revision',place='exact opened destination place ID',destination='exact format-1 destination revision'),'Durable one-way physical link. Capable player A opens confirmation; separate destination transfer preserves original Hoenn return. No actor/player travel claimed by installation; no outdoor formats.',install_cave_link,None,('world',))

from .actor_cave_travel import traverse, poll as cave_travel_poll
CAPABILITIES['world.traverse_link']=Capability('Traverse an adjacent observed physical cave link as this world-owned actor.',dict(object='observed anchored link prop ID',revision='observed program_revision'),'Committed authority departure/arrival under one identity; no canonical relocation, player warp or animated portal claim.',traverse,cave_travel_poll,('world',))

from .actor_linked_navigation import start as navigate_places, poll as linked_navigation_poll
CAPABILITIES['world.navigate_places']=Capability('Route this actor to a tile across actual installed cave links.',dict(place='opened destination place ID',revision='exact destination cave revision',x='destination integer',y='destination integer'),'Durable per-leg authority movement/traversal receipts and final arrival; changed or blocked routes require replan, no canonical/outdoor travel.',navigate_places,linked_navigation_poll,('world',))

from .companion_exchange import offer as offer_companion, respond as respond_companion
CAPABILITIES['world.offer_companion']=Capability('Offer an actually owned benched companion to an adjacent world character.',dict(target='recipient actor ID',individual='owned benched individual ID',recipient_individual='unused recipient-local identity'),'Pending independent recipient choice; no capture or immediate transfer.',offer_companion,None,('world',))
CAPABILITIES['world.respond_companion']=Capability('Accept/decline a companion offered to this actor, or withdraw own offer.',dict(offer='actual offer ID',decision='accept, decline or withdraw'),'Atomic real companion custody transfer preserving native identity/state. Teams and player saves unchanged; recipient can later prepare its own lineup.',respond_companion,None,('world',))

from .actor_knowledge import share as share_observation,recall as recall_observation
CAPABILITIES['world.share_observation']=Capability('Pass a real own observation to an adjacent independent world character.',dict(target='existing recipient',expected_version='current recipient version',observation='own successful world.observe receipt sequence'),'Durable dated facts and provenance delivered; not current sight or agreement. Recipient can react independently.',share_observation,None,('world',))
CAPABILITIES['world.recall_report']=Capability('Read a factual report actually received from another character.',dict(delivery='received_observations delivery sequence'),'Dated snapshot and report_revision/report_x/report_y for planning; inspect again after travel, not current first-hand knowledge.',recall_observation,None,('world',))

from .object_networks import install as install_network,poll as poll_network
CAPABILITIES['world.program_network']=Capability('Build shared interactive or spatial prop mechanisms.',dict(definition='JSON <=2600: id, objects[2..4], program {initial,states:{phase:{objects:{id:{x,y,gfx,text}},on:{id:{action:phase}},use:{id:action},when?:[{to,mode:all|any,occupied:bool,hold:1..30,zones:[{x,y,radius:0..2,players:0..4,characters:0..8}]}]}}}. Max6 phases,2 rules,4 zones. gfx0/1,text28,one-tile moves.'),'Actual shared objects; fresh scoped positions, connected geometry and occupancy enforced. No rewards or fictional labor.',install_network,poll_network,('world',))

from .npc_conversations import reply as reply_player
CAPABILITIES['world.reply_player']=Capability('Reply publicly to an actual nearby player speech addressed to this recurring NPC.',dict(speech='own public_player_speech receipt integer',text='1..80 printable characters of public fictional reply'),'Durable public reply; native chat if original speaker remains nearby. No obedience, action completion or private relationship invented.',reply_player,None,('world',))

from .actor_capture import request as capture_request,poll as capture_poll
CAPABILITIES['world.attempt_capture']=Capability('Request a real isolated first throw with an owned companion and finite host-provisioned ball.',dict(individual='owned on-team full-state individual',ball='basic ball integer 1..3 from host stock'),'Disabled without an exact QA-validated host runner. Actual caught individual imported to bench or unresolved failure receipt; no battle victory, player save or automatic team rewrite.',capture_request,capture_poll,('world',))

from .actor_shops import configure as configure_shop
CAPABILITIES['world.configure_shop']=Capability('Open, revise or close this recurring NPC ordinary native retail service.',dict(items='JSON list of up to 8 distinct reviewed item IDs from retail.items; [] closes'),'Real catalog offered in native Shop menu at engine prices, with native purchase/bag checks. Unlimited retail, no finite inventory, profit or sale inferred. Existing canonical shops unchanged.',configure_shop,None,('world',))

from .actor_weather import configure as configure_weather
CAPABILITIES['world.set_weather']=Capability('Author persistent native weather on the exact generated outdoor destination this actor occupies.',dict(revision='exact current active archived outdoor revision',mode='clear, clouds, rain, snow, fog, overcast or default'),'Actual authority environmental setting; compatible clients apply only at safe field boundaries. Native weather/battle/form effects remain native; not a character power, forecast or proven client application. Original Hoenn unchanged.',configure_weather,None,('world',))

from .actor_tutors import configure as configure_tutor
CAPABILITIES['world.offer_tutoring']=Capability('Offer or close optional move tutoring through the native party/learn-move menus.',dict(move='reviewed move ID from tutoring.moves, or 0 to close'),'Actual opportunity, not learned move. Player chooses Pokemon and replacement; native eligibility enforced. Repeatable free tutoring, no server party/save edits and no canonical tutor flags changed.',configure_tutor,None,('world',))

from .actor_environment import inspect_patch, reshape
CAPABILITIES['world.inspect_environment']=Capability('Inspect a bounded patch of the active shared event-outdoor terrain from public authority data.',dict(x='patch origin',y='patch origin',width='1..8',height='1..8'),'Dated authority map data, not actor eyesight or a player observation. Only archived 63x63 CAVE9 event outdoors; no private player data.',inspect_patch,None,('canonical','world'))
CAPABILITIES['world.reshape_environment']=Capability('Change inspected outdoor surfaces through the existing native grass, tall-grass and water mechanics.',dict(observation='own successful world.inspect_environment receipt',tiles='JSON <=700 chars list of {x,y,terrain:grass/tall_grass/water/original}'),'Durable connected terrain patch with atomic receipt. All trainers must leave first. Native surface/encounter/Surf semantics, not simulated labor, migration, catches or proof of client rendering. Original Hoenn unchanged.',reshape,None,('canonical','world'))

from .companion_barter import propose as barter_propose, respond as barter_respond
CAPABILITIES['world.propose_exchange']=Capability('Propose a reciprocal trade of two actually owned benched Pokemon with an adjacent world character.',dict(target='recipient actor ID',give='own benched individual ID',receive='recipient benched individual ID',sender_alias='unused or matching prior own local ID for received Pokemon',recipient_alias='unused or matching prior recipient local ID for offered Pokemon'),'Durable frozen proposal only. Recipient receives a real event and independently accepts/declines. No forced transfer, player trade or evolution.',barter_propose,None,('world',))
CAPABILITIES['world.resolve_exchange']=Capability('Independently accept/decline a reciprocal companion exchange, or withdraw your own proposal.',dict(offer='actual reciprocal exchange ID',decision='accept, decline or withdraw'),'Both existing native identities and full training state transfer atomically, or neither does. Actual adjacency and unchanged bench required; teams and player saves untouched. Prepare a challenge separately to use received companions.',barter_respond,None,('world',))

from .actor_cooperation import request as cooperation_request, respond as cooperation_respond, deliver as cooperation_deliver
CAPABILITIES['world.request_cooperation']=Capability('Ask an adjacent independent world character to pursue a public goal using an existing capability.',dict(target='recipient actor ID',purpose='public fictional request up to 120 ASCII chars',tool='existing world capability name',where='JSON <=350 chars: outcome plus up to three exact scalar successful-result fields'),'Durable voluntary request, not a forced plan, permission grant or completed work. Recipient independently decides and acts. Predicate describes actual operation evidence, not prose truth.',cooperation_request,None,('world',))
CAPABILITIES['world.respond_cooperation']=Capability('Accept or decline a request, abandon accepted work, or withdraw your own request.',dict(request='actual cooperation request ID',decision='accept, decline, abandon or withdraw'),'Records a choice only. No action or reversal is invented; actual executor preconditions and permissions still apply.',cooperation_respond,None,('canonical','world'))
CAPABILITIES['world.deliver_cooperation']=Capability('Deliver a real successful action receipt satisfying an accepted cooperation request.',dict(request='accepted request ID',receipt='own successful authority action receipt after acceptance'),'Matches exact tool and typed result fields. Durable evidence reaches requester for independent next decision; no fabricated goal achievement, rewards, animation or persistent current-state claim.',cooperation_deliver,None,('canonical','world'))

from .npc_accompaniment import start as accompany_start, poll as accompany_poll
CAPABILITIES['world.accompany_player']=Capability('Choose to walk with a nearby player who explicitly invited this NPC.',dict(request='actual accompaniment_requests invitation sequence'),'Real collision-checked generated-map steps toward the same authenticated session. Pauses for field menus/battles/obstacles, stops on cancellation, disconnect or map revision change. No warp, player control, canonical follower flag or partner battle. Existing scheduler pace, not a tight native follower formation.',accompany_start,accompany_poll,('world',))

from .actor_habitat_revision import inspect as inspect_habitat, revise as revise_habitat
CAPABILITIES['world.inspect_habitat']=Capability('Inspect the real configured native encounters of the active shared cave.',{},'Public authority encounter configuration, not sightings. Durable non-opened 31/63 cave only; no outdoor or original Hoenn tables.',inspect_habitat,None,('canonical','world'))
CAPABILITIES['world.revise_habitat']=Capability('Populate or revise the existing shared cave wildlife while retaining its place identity and exact geometry.',dict(observation='own world.inspect_habitat receipt',profile='existing profile or granite/meteor/ice/victory for previously plain cave',rate='native encounter rate 1..100',slots='JSON <=650 chars: exactly 12 [enabled Expansion species name,level 1..100] pairs'),'Actual CAVE10/11 native encounter data with atomic revision/history receipt. Players must leave the shared destination. Opened immutable regions, outdoors, Hoenn encounters and player saves unchanged. No simulated migration, catch or NPC training.',revise_habitat,None,('canonical','world'))

from .battle_campaigns import publish as publish_campaign
CAPABILITIES["world.publish_battle_campaign"]=Capability("Publish a branching optional adventure of existing NPC battles and ordinary-map visit stages.",dict(campaign="JSON id/title/entry/nodes; each node either opponent/win/loss routes (optional preparation {choice:{actor,items,move}}), or visit:{label,point:[group,num,x,y]}/next routes. Stable normal maps only; bounds checked, walkability needs playtest"),"Immutable playable graph, not completed battles or travel. Existing native campaign board offers voluntary fresh-presence check-in; shared party waits for all check-ins, not simultaneous presence. Player chooses routes; exact native reports retain private save-scoped progress. No rewards, forced fights or invented growth.",publish_campaign,None,("world","canonical"))

from .shared_outbreaks import configure as configure_outbreak
CAPABILITIES['world.configure_outbreak']=Capability('Author or end a temporary public land encounter population on a reviewed Hoenn route.',dict(map='route name from outbreaks.maps',species='enabled Expansion species name',level='1..100',chance='1..50 percent of native outbreak tests',minutes='1..60, or 0 to end own population'),'Actual temporary encounter configuration, not simulated migration/catches. Native terrain, encounter rate, Repel, capture and party rules remain intact. Saved personal outbreaks take priority. Never modifies a player saved outbreak or forces a battle.',configure_outbreak,None,('canonical','world'))

from .contest_guests import configure as configure_contest
CAPABILITIES['world.enter_contest']=Capability('Offer an owned on-team companion as an optional normal-rank Lilycove contest guest.',dict(category='cool, beauty, cute, smart or tough',individual='owned on-team individual, or empty to withdraw own category entry'),'Actual guest entry, not completed contest or travel. Actor must already occupy the real lobby. Player can invite guest through ordinary receptionist; native appeal mechanics, personal eligibility and rewards remain normal. No ribbons/condition/training invented.',configure_contest,None,('world',))

from .rental_pools import tool as rental_tool
CAPABILITIES['world.rentals']=Capability('Inspect or curate optional Slateport rentals.',dict(operation='inspect or configure',value='inspect: page 0..6; configure: JSON six set IDs or []'),'Native rental pool only, not recruitment or earned growth.',rental_tool,None,('canonical','world'))

from .place_connections import connect as connect_places, poll as poll_connection
CAPABILITIES['world.connect_places']=Capability('Connect two existing opened caves with paired safe native passage props, without manually placing objects or moving an author.',dict(source='opened source place ID',source_revision='exact source revision',target='opened target place ID',target_revision='exact target revision'),'Two admitted anchored props and durable directed cave links. Existing CAVELINK1/CAVELINKW1 confirmation, transfer and return warp; plain/wildlife caves only. No travel, labor or seamless transition inferred.',connect_places,poll_connection,('canonical','world'))

from .habitat_composer import inspect_species, create as compose_habitat
CAPABILITIES['world.inspect_species']=Capability('Inspect bounded pages of native species traits matching a type/stat/generation query.',dict(criteria='JSON <=500: types 1..4 native type names, generations distinct 1..9, bst [min,max] 150..720, levels [min,max] 1..100, seed uint32',page='nonnegative page, 12 rows'),'Sourced supported base-species metadata, not observed habitat or catches; special legendary/mythical/Ultra Beast/Paradox species excluded.',inspect_species,None,('canonical','world'))
CAPABILITIES['world.compose_habitat']=Capability('Create a persistent selectable wildlife cave with twelve diverse encounter species composed from native traits.',dict(label='menu label 1..20',blueprint='world.create_place room/link JSON <=700',profile='granite/meteor/ice/victory',rate='integer 1..100',criteria='Same bounded criteria JSON as world.inspect_species; must match at least 12 species'),'Actual immutable CAVE10/REGION1 cave with native encounter table. Seeded species selection; higher selected BST/levels occupy later, rarer native slots. Authoring only, no ecosystem simulation, catches or NPC training claimed.',compose_habitat,None,('canonical','world'))

from .shared_pushing import install as enable_pushing, poll_install as poll_pushing
CAPABILITIES['world.enable_pushing']=Capability('Give an observed unused anchored prop directional one-tile pushing through existing player A and agent object use.',dict(object='observed prop id',revision='exact program_revision from observation'),'Admitted shared movable body; each real push preserves geometry, occupants and routes. Existing sign/pot visuals and snapshot movement, not native HM Strength, inventory or animation.',enable_pushing,poll_pushing,('world',))

from .actor_moves import request as move_request,poll as move_poll
CAPABILITIES['world.learn_move']=Capability('Teach one native-legal reminder move to an owned companion.',dict(individual='owned on-team individual with full native state',move='native move ID from inspection',slot='replacement slot 0..3'),'Requires QA-validated host worker; returns actual native choices or reconciled full individual state. No XP, evolution, TM items or player save changes.',move_request,move_poll,('world',))

CAPABILITIES['world.inspect_moves']=Capability('Request native reminder choices for an owned companion.',dict(individual='owned on-team individual with full native state'),'Returns current move slots and legal level-up reminder IDs from exact engine. Requires QA-validated host worker; does not change the companion.',move_request,move_poll,('world',))

from .actor_cooperation import request_work
CAPABILITIES['actor.request_work']=Capability('Ask another existing independent actor for supported work by public correspondence.',dict(target='existing canonical or world actor ID',purpose='public fictional purpose <=120 ASCII chars',tool='capability actually available to recipient kind',where='JSON <=350 chars: outcome plus up to three exact scalar successful result fields'),'Voluntary request only, not a forced plan or physical meeting. Recipient can accept/decline/abandon using world.respond_cooperation, act independently, and deliver its actual successful receipt with world.deliver_cooperation. No permissions, labor, travel or rewards invented.',request_work,None,('canonical','world'))
from .actor_bulletins import publish as publish_bulletin,withdraw as withdraw_bulletin
CAPABILITIES['world.publish_bulletin']=Capability('Publish an attributed public-history report for optional viewing at normal TVs.',dict(pages='JSON two pages, each 1..2 literal 28-character lines',evidence='JSON 1..4 committed public event sequence IDs',hours='integer 1..24'),'Actual shared bulletin publication, not proof report assertions are true or players watched; existing story news remains intact.',publish_bulletin,None,('world','canonical'))
CAPABILITIES['world.withdraw_bulletin']=Capability('Withdraw this character own current TV report.',{},'Removes only own bulletin; historical publication evidence remains.',withdraw_bulletin,None,('world','canonical'))
from .shared_races import publish as publish_race
CAPABILITIES['world.publish_race']=Capability('Create an immutable simultaneous field race using actual native walking or mounts.',dict(course='JSON id/title/starts/checkpoints/laps/limit/mounted'),'Playable opt-in course registration, not a race result. Stable normal-map bounds validated, route walkability and fairness require playtesting.',publish_race,None,('world','canonical'))
from .actor_battle_formats import configure as configure_battle_format
CAPABILITIES['world.set_battle_format']=Capability('Choose Singles or Doubles for this recurring trainer optional native challenge.',dict(format='singles or doubles; doubles requires at least two individually owned team members'),'Actual frozen native battle format offered to the player; doubles requires two usable player Pokemon at launch. No forced battle, invented results, scripted campaign changes or server party edits.',configure_battle_format,None,('world',))

from .region_networks import start as create_region_network,poll as network_poll
CAPABILITIES['world.create_region_network']=Capability('Create two to four distinct persistent cave places with a connected physical passage graph.',dict(network='JSON <=850 chars: places [{label,blueprint}], links [[place_index,place_index]]; normal 31x31 cave blueprints; 2..4 places, connected unique links max4'),'Stages actual immutable plain caves and passage props. Success only after admission and all links installed. Pending/failed admission may leave opened places; same request resumes without duplication. No outdoor REGION1, visits, construction or seamless travel claimed.',create_region_network,network_poll,('canonical','world'))

from .shared_fishing import configure as configure_fishing
CAPABILITIES['world.configure_fishing']=Capability('Author rod-specific encounter populations on existing Hoenn waters.',dict(map='Reviewed fishing route from fishing catalog',rods='JSON old/good/super lists of 2/3/5 [species,min_level,max_level] slots; native rod weights',minutes='0..1440; zero closes own fishery'),'Actual transient native fishing table, not catches or stock simulation. Existing rods, timing, battles, special Feebas and shuffle remain native.',configure_fishing,None,('world','canonical'))

from .npc_guidance import start as guidance_start, poll as guidance_poll
CAPABILITIES['world.guide_players']=Capability('Offer to lead up to four voluntary nearby players to a chosen reachable tile, then actually walk while waiting for the group.',dict(revision='this actor exact generated map revision',x='destination integer',y='destination integer',text='public invitation, 1..60 ASCII characters'),'Pending invitation visible through /guild npc nearby and guide ID. Players join-guide ID and retain all input. Real one-step authority movement; pauses for readiness, obstacles or stragglers, ends on group departure/disconnect or after 15 minutes. Success requires actual NPC arrival and nearby current player presence. No player teleport, reward, canonical relocation or cross-map travel.',guidance_start,guidance_poll,('world',))

from .actor_history import search as history_search, read as history_read
CAPABILITIES['world.search_history']=Capability('Search and page original committed public world history beyond the recent context window.',dict(query='JSON object: optional terms (up to six literal changed-content terms), actor (sender/recipient/character ID), event (type), place (stable ID). Filters combine; {} browses all public history.',after='integer cursor; 0 starts at oldest retained event',through='integer fixed boundary; 0 captures current head, reuse returned through for later pages'),'Up to eight original records or explicit large-record references, cursor/through/has_more and first_sequence (0 if empty) for composition. No private data, inferred knowledge or fabricated summaries; historical reports retain their provenance.',history_search,None,('canonical','world'))
CAPABILITIES['world.read_history']=Capability('Read an exact public source event or nested value by its sequence and JSON pointer.',dict(sequence='original public event sequence from history search',path='empty string for root, or JSON pointer such as /after/goals or /result; large containers return fields/index count to read individually'),'Exact source value with sequence/path and completeness. Not current state or proof of assertions. Retrieval receipts cannot be recursively read.',history_read,None,('canonical','world'))

from .actor_attention import configure as configure_attention
CAPABILITIES['world.attend_local']=Capability('Keep noticing changing nearby public entities and weather while pursuing independent plans.',dict(mode='local or off',radius='connected cardinal radius integer 1..4',cooldown='minimum seconds between notices, integer 30..3600'),'Durable local sampling registration, not immediate activity or a model call. Actual sampled changes can trigger the existing enrolled author under host budgets. No player data, global tracking or canonical relocation. Moves/revisions rebase without fabricated arrivals.',configure_attention,None,('world',))

from .actor_population import populate_group
CAPABILITIES['world.populate_group']=Capability('Populate a supported place with a jointly validated group of independently defined original NPCs and props in one admission.',dict(revision='exact supported generated revision',definitions='JSON list <=700 chars, two to four definitions using world.populate fields; independent identities and distinct valid placements'),'Actual atomic population receipt with all member identities, or no admitted members. Existing NPC author enrollment and native per-map/entity limits remain; no births, catches or simulated activity.',populate_group,poll_population,('canonical','world'))

from .procedural_regions import start as generate_region_network
CAPABILITIES['world.generate_region_network']=Capability('Generate and publish connected places from topology and layout constraints, without manually specifying rectangles or edges.',dict(label='literal 1..12 character prefix',constraints='JSON <=400 chars: places 2..4, rooms per place 2..4, loops 0..1, branching max degree 1..3, style rooms/rounded/organic/maze, seed uint32, corridor_width 1..3. Existing network size budget applies.'),'Actual deterministic plain 31x31 cave network through existing REGION1/CAVELINK1 admission, or explicit failure. Not outdoor regions, story, resources, travel or encounters.',generate_region_network,network_poll,('canonical','world'))

from .adaptive_navigation import start as navigate_adaptively,poll as adaptive_navigation_poll
CAPABILITIES['world.navigate_adaptively']=Capability('Walk toward a same-map destination while recomputing routes around changing occupancy between real admitted steps.',dict(revision='exact supported generated revision',x='destination integer',y='destination integer',max_steps='actual cardinal-step allowance 1..256'),'Actual arrival or step-budget exhaustion at the current tile. Blocked owned steps are explicitly halted before rerouting; no teleport, player control or canonical/cross-map travel.',navigate_adaptively,adaptive_navigation_poll,('world',))

from .actor_agreements import propose as propose_agreement,decide as decide_agreement,commit as commit_agreement
CAPABILITIES['world.propose_agreement']=Capability('Invite independent characters to agree on one exact supported shared-world change.',dict(participants='JSON list of 1..3 other active actor IDs',purpose='public fictional purpose <=120 ASCII',tool='agreement-safe tool from agreements.supported',args='JSON <=500 chars, exact literal arguments for that tool',hours='expiry integer 1..24'),'Public immutable proposal only, not action, authority or agreement by others. No physical meeting inferred.',propose_agreement,None,('world','canonical'))
CAPABILITIES['world.decide_agreement']=Capability('Independently accept or decline an invited shared-world proposal, or withdraw your own.',dict(agreement='actual agreement ID',decision='accept, decline or withdraw'),'Durable choice only. Declining cancels; all invited actors must accept before proposer can execute. No work or effect claimed.',decide_agreement,None,('world','canonical'))
CAPABILITIES['world.commit_agreement']=Capability('Execute your own unanimously accepted exact shared-world operation using its original authority guards.',dict(agreement='actual agreement ID'),'Atomic real operation result, or a blocked plan with no committed effect. Acceptances grant no new permissions and do not bypass ownership, location, species or geometry validation.',commit_agreement,None,('world','canonical'))

from .actor_field_games import publish as publish_flag_arena
CAPABILITIES['world.publish_flag_arena']=Capability('Create a real opt-in two- or four-player field capture-the-flag arena on normal maps.',dict(arena='JSON <=1500: id,title,bases [two map-group/map-number/x/y points],limit seconds 30..600,captures 1..5; optional starts [four distinct points alternating Red/Blue, each on or adjacent to its base]'),'Immutable playable activity-board registration. Two teams, one flag each, proximity tagging and independent player movement; existing private results, voluntary joining, no rewards or story changes. Coordinates validate map bounds, not walkability; playtest paths.',publish_flag_arena,None,('canonical','world'))

from .actor_stories import publish as publish_story, wait as wait_story, poll as poll_story
CAPABILITIES['world.publish_story']=Capability('Create optional public player choices on existing normal maps, using the real story UI and persistent shared qualities.',dict(pack='JSON <=800 chars within normal step budget: id,title,qualities {key:{scope:place,initial,max}},scenes {id:{place,text,requires,once:world,choices:{id:{text,requires,effects,result}}}}'),'Immutable public story, not a fulfilled narrative assertion or native world effect. Players explicitly select a displayed public choice; no trainer identity or private story data enters history.',publish_story,None,('canonical','world'))
CAPABILITIES['world.await_story_choice']=Capability('Receive an actual committed choice in your own public story, including choices made before this wait began.',dict(pack='own published public story ID',after_cursor='last returned cursor, or 0 for first choice'),'Durable actual scene/choice/place/revision/changes and receipt cursor. Compose supported follow-up actions or replan; narrative text is not proof that a world action occurred.',wait_story,poll_story,('canonical','world'))

from .actor_blueprints import edit as edit_blueprint, inspect as inspect_blueprint, close as close_blueprint
CAPABILITIES['world.edit_blueprint']=Capability('Build larger public fictional JSON content across bounded edits and plans, without executing it.',dict(id='own stable lowercase draft ID',revision='exact current revision; 0 creates an empty object',patch='JSON <=700 chars: 1..4 {op:set,path:JSON-pointer,value:literal} or {op:remove,path:JSON-pointer}. Set /array/- appends; parent must exist.'),'Durable CAS revision and digest only, not a published map, program, campaign or completed action. Root object <=8192 bytes; all downstream validators/permissions unchanged. Public fictional data only, no personal or secret data.',edit_blueprint,None,('canonical','world'))
CAPABILITIES['world.inspect_blueprint']=Capability('Freeze your own assembled JSON draft as a scalar result for an existing content executor.',dict(id='own blueprint ID'),'Exact document string, revision and digest. Reference document from a later dependent tool argument; that tool validates and executes normally. Snapshot remains unchanged by later edits.',inspect_blueprint,None,('canonical','world'))
CAPABILITIES['world.close_blueprint']=Capability('Archive your own finished draft and free an active authoring slot without deleting its history.',dict(id='own blueprint ID',revision='exact revision'),'Closed read-only draft; existing publications and receipts remain unchanged. Up to16 active drafts per actor/128 world, not lifetime creation limits.',close_blueprint,None,('canonical','world'))
