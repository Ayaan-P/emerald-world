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
        if type(step) is not dict or set(step)!={'id','tool','args','after'}:raise ValueError('Step needs id, tool, args and after')
        if not identifier(step['id']) or step['id'] in seen or type(step['tool']) is not str or step['tool'] not in CAPABILITIES:raise ValueError('Unknown tool or repeated step')
        if type(step['after']) is not list or any(type(s) is not str for s in step['after']) or len(set(step['after']))!=len(step['after']) or not set(step['after'])<=seen:raise ValueError('Dependencies must be earlier step IDs')
        if type(step['args']) is not dict or set(step['args'])!=set(CAPABILITIES[step['tool']].arguments):raise ValueError('Tool arguments do not match advertised capability')
        for value in step['args'].values():
            if type(value) is dict:
                if set(value)!={'result','key'} or value['result'] not in step['after'] or not identifier(value['key']):raise ValueError('Result reference needs a declared prior dependency and scalar key')
            elif type(value) not in (str,int) or isinstance(value,bool):raise ValueError('Tool arguments must be scalar or result references')
        if len(json.dumps(step))>1024:raise ValueError('Tool step exceeds bounded size')
        seen.add(step['id'])


def definition(plan):return json.dumps(plan,sort_keys=True,separators=(',',':'))


def inspect_runtime(server):
    from .canonical_cast import records
    install(server.db)
    from .prop_custody import inventory
    from .companion_exchange import offers as companion_offers
    from .actor_navigation import discover as discover_navigation
    from .actor_linked_navigation import graph as linked_graph
    from .character_companions import roster
    from .actor_knowledge import inbox as knowledge_inbox
    from .npc_conversations import inbox as speech_inbox
    from .actor_capture import available as capture_available
    from .actor_shops import catalog as shop_catalog
    return dict(retail=shop_catalog(server),capture=capture_available(server),public_player_speech=speech_inbox(server),received_observations=knowledge_inbox(server),companion_rosters={actor:roster(server,actor) for actor,r in actor_records(server).items() if not r.get('canonical')},capabilities={key:dict(description=c.description,arguments=c.arguments,outcome=c.outcome,actor_kinds=c.kinds) for key,c in CAPABILITIES.items()},
        available_actions=server.opportunities.actor_actions()[:32],actors={a:('canonical' if r.get('canonical') else 'world') for a,r in actor_records(server).items()},
        companion_offers=companion_offers(server),navigation=discover_navigation(server),cave_links=linked_graph(server),carried_props=inventory(server),
        object_player_use='Optional state.world_object_player_use maps prop ID to one advertised world_object_actions action ID. Native A dispatches the same actor_interact(object_id,action,own_state) handler through normal staging. No map: text only. Effects are bounded own-state/text/graphics/one-cell movement, not bags/items.',
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
            if not all(s in receipts and receipts[s][0]=='succeeded' for s in step['after']):continue
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
CAPABILITIES['world.program_object']=Capability('Install a reusable interactive state machine on an observed unprogrammed anchored prop.',dict(object='observed prop ID',revision='observed program_revision',program='JSON <=700 chars: initial state name, states {name:{text <=28 ASCII,gfx 0/1,on:{action:next_state},use:action or empty}}; 1..4 states, up to4 transitions each. Native A invokes current use; agents choose advertised actions.'),'Admitted persistent prop program through normal mechanic staging. Appearance, text and available actions change through real player/agent use; no bag, rewards, movement or claimed interactions.',program_object,program_poll,('world',))

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
CAPABILITIES['world.program_network']=Capability('Link observed unused props into a shared player-and-agent interactive state machine.',dict(definition='JSON <=2600 chars: id, objects[2..4 ids], program {initial, states {phase:{objects:{id:{x,y,gfx,text}},on:{id:{action:next_phase}},use:{id:default_action}}}}. 1..6 states; gfx0/1; text28; each prop moves at most one tile; all geometry/occupancy validated.'),'Actual linked object states admitted. Native A or agent use changes all members in one validated transaction; no item, reward or story fabricated.',install_network,poll_network,('world',))

from .npc_conversations import reply as reply_player
CAPABILITIES['world.reply_player']=Capability('Reply publicly to an actual nearby player speech addressed to this recurring NPC.',dict(speech='own public_player_speech receipt integer',text='1..80 printable characters of public fictional reply'),'Durable public reply; native chat if original speaker remains nearby. No obedience, action completion or private relationship invented.',reply_player,None,('world',))

from .actor_capture import request as capture_request,poll as capture_poll
CAPABILITIES['world.attempt_capture']=Capability('Request a real isolated first throw with an owned companion and finite host-provisioned ball.',dict(individual='owned on-team full-state individual',ball='basic ball integer 1..3 from host stock'),'Disabled without an exact QA-validated host runner. Actual caught individual imported to bench or unresolved failure receipt; no battle victory, player save or automatic team rewrite.',capture_request,capture_poll,('world',))

from .actor_shops import configure as configure_shop
CAPABILITIES['world.configure_shop']=Capability('Open, revise or close this recurring NPC ordinary native retail service.',dict(items='JSON list of up to 8 distinct reviewed item IDs from retail.items; [] closes'),'Real catalog offered in native Shop menu at engine prices, with native purchase/bag checks. Unlimited retail, no finite inventory, profit or sale inferred. Existing canonical shops unchanged.',configure_shop,None,('world',))
