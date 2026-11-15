"""Model-authored plans over registered authority capabilities, not character arcs.

Local effects use transactions. Staged asynchronous tools supply an explicit
completion adapter; issuing a request is never completion.
"""
from dataclasses import dataclass,replace
import copy,json,re,time

@dataclass(frozen=True)
class Capability:
    description: str
    arguments: dict
    outcome: str
    execute: object
    poll: object = None
    kinds: tuple = ('canonical',)
    during_activity: bool = False

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
    from .campaign_cast import setup as campaign_cast_setup
    campaign_cas…13027 tokens truncated…ine; {} browses all public history.',after='integer cursor; 0 starts at oldest retained event',through='integer fixed boundary; 0 captures current head, reuse returned through for later pages'),'Up to eight original records or explicit large-record references, cursor/through/has_more and first_sequence (0 if empty) for composition. No private data, inferred knowledge or fabricated summaries; historical reports retain their provenance.',history_search,None,('canonical','world'))
CAPABILITIES['world.read_history']=Capability('Read an exact public source event or nested value by its sequence and JSON pointer.',dict(sequence='original public event sequence from history search',path='empty string for root, or JSON pointer such as /after/goals or /result; large containers return fields/index count to read individually'),'Exact source value with sequence/path and completeness. Not current state or proof of assertions. Retrieval receipts cannot be recursively read.',history_read,None,('canonical','world'))

from .actor_attention import configure as configure_attention
CAPABILITIES['world.attend_local']=Capability('Keep noticing changing nearby public entities and weather while pursuing independent plans.',dict(mode='local or off',radius='connected cardinal radius integer 1..4',cooldown='minimum seconds between notices, integer 30..3600'),'Durable local sampling registration, not immediate activity or a model call. Actual sampled changes can trigger the existing enrolled author under host budgets. No player data, global tracking or canonical relocation. Moves/revisions rebase without fabricated arrivals.',configure_attention,None,('world',))

from .actor_population import populate_group
CAPABILITIES['world.populate_group']=Capability('Populate a supported place with a jointly validated group of independently defined original NPCs and props in one admission.',dict(revision='exact supported generated revision',definitions='JSON list <=700 chars, two to four definitions using world.populate fields; independent identities and distinct valid placements'),'Actual atomic population receipt with all member identities, or no admitted members. Existing NPC author enrollment and native per-map/entity limits remain; no births, catches or simulated activity.',populate_group,poll_population,('canonical','world'))

from .procedural_regions import start as generate_region_network
CAPABILITIES['world.generate_region_network']=Capability('Generate and publish connected places from topology and layout constraints, without manually specifying rectangles or edges.',dict(label='literal 1..12 character prefix',constraints='JSON <=400 chars: places 2..4, rooms per place 2..4, loops 0..1, branching max degree 1..3, style rooms/rounded/organic/maze, seed uint32, corridor_width 1..3; optional room_loops 0..1 (one cycle requires at least 3 rooms; default 0), place_styles list with one rooms/rounded/organic/maze style per place. Existing network size budget applies.'),'Actual deterministic plain 31x31 cave network through existing REGION1/CAVELINK1 admission, or explicit failure. Not outdoor regions, story, resources, travel or encounters.',generate_region_network,network_poll,('canonical','world'))

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

from .safari_outings import publish as publish_safari
CAPABILITIES['world.publish_safari_outing']=Capability('Invite players to an optional shared outing using stock Hoenn Safari gameplay.',dict(id='stable lowercase id <=24 characters',title='public fictional title <=60 ASCII',target='group reported-catch target 1..120',hours='duration 1..24 hours'),'Players explicitly opt in to anonymous aggregate reporting, then enter and play normally. Real client reports feed public history; no verified catches, rewards, invented attendance or rule/save changes.',publish_safari,None,('canonical','world'))

from .safari_outings import wait as wait_safari, poll as poll_safari
CAPABILITIES['world.await_safari_outing']=Capability('Wait for your outing reported group target or actual expiry.',dict(id='own published outing ID'),'Returns opted-in anonymous aggregate client reports, not verified captures or NPC growth. Existing validated follow-up capabilities remain separate decisions.',wait_safari,poll_safari,('canonical','world'))


# Reviewed non-physical operations only. Default remains exclusive, including
# unknown future capabilities. Passive waits may coexist; all original
# dependencies, audience checks, exact receipts and transactions still apply.
for _tool in ('world.await_event','world.reply_player','actor.message',
              'world.search_history','world.read_history','world.recall_report',
              'world.inspect_species','world.inspect_blueprint'):
    CAPABILITIES[_tool]=replace(CAPABILITIES[_tool],during_activity=True)

from .native_resident_population import spawn as populate_native, poll as native_population_poll
CAPABILITIES['world.populate_native']=Capability('Create a new original recurring NPC at a source-verified ordinary Hoenn residence site.',dict(map='eligible map name from native_resident_sites',definition='JSON <=700: id,name,role,goals,team [{species,level}],x,y,gfx 7/8,text; choose an advertised site'),'Actual persistent NPC using existing normal-map rendering and optional interactions. One resident per eligible room, players must leave during admission. No canonical duplicates, travel, captures or native save changes. Exact native asset pin required.',populate_native,native_population_poll,('canonical','world'))

from .spatial_speech import speak as spatial_speak
CAPABILITIES['world.speak']=Capability('Speak publicly to actually nearby recurring NPCs and eligible nearby players, without selecting their response.',dict(text='1..80 printable fictional public characters',radius='1..4 generated connected-ground steps; native maps clamp to same-map proximity radius2'),'Durable public speech and exact NPC recipient IDs; independent recipient turns. Existing chat attempts one-shot delivery to frozen nearby player sessions. Stationary non-battle world actors only; 30-second per-actor cooldown. No claim of rendered hearing, truth, agreement, or physical action.',spatial_speak,None,('world',))

from .history_world_rules import publish as publish_history_rule, pause as pause_history_rule
CAPABILITIES['world.publish_reaction']=Capability('Install an ongoing bounded response to future committed public events.',dict(id='immutable own rule ID',rule='JSON <=650: event/where/tool/args/cooldown/per_hour. Discover history_world_rules for reviewed events and operations. Fixed scalar args; cooldown60..86400, attempts1..12 per hour.'),'Durable registration only. Current validated native-world operation runs later on matching real public records, with causal receipt and recurring attempt budget. No model call or inferred truth.',publish_history_rule,None,('world','canonical'))
CAPABILITIES['world.pause_reaction']=Capability('Stop your own persistent world reaction.',dict(id='own existing rule ID'),'No future effects from this rule; existing committed world state and receipts retained.',pause_history_rule,None,('world','canonical'))

from .campaign_cast import decide as campaign_decide, finish as campaign_finish, poll as campaign_poll
CAPABILITIES['world.decide_campaign_role']=Capability('Independently accept, decline or withdraw an addressed public generated-map visit invitation.',dict(invitation='advertised invitation ID',decision='accept, decline or withdraw'),'Choice only, never movement. Human party history remains private. Accepted roles need a subsequent real navigation arrival.',campaign_decide,None,('world',))
CAPABILITIES['world.complete_campaign_role']=Capability('Submit your own actual post-acceptance journey arrival for an accepted generated visit role.',dict(invitation='accepted invitation ID',arrival_receipt='arrival_receipt returned by world.navigate'),'Waits until party deployment is ready; requires matching authority journey and current exact-revision position. No human results/history or fabricated battles.',campaign_finish,campaign_poll,('world',))

from .character_archive import recall as recall_archived_character
CAPABILITIES['world.recall_character']=Capability('Recall permanent public retired-character identities and relationships outside live capacity.',dict(after='ID cursor, empty starts first page',identity='exact archived ID for full final record, or empty to list eight'), 'Dated final authored record and archive event; never a present actor or verified achievement. Original history remains searchable.',recall_archived_character,None,('canonical','world'),True)

from .knowledge_relays import relay as relay_received_report
CAPABILITIES['world.relay_report']=Capability('Pass a genuinely received public observation to another actually adjacent generated NPC.',dict(target='existing inspected character ID',expected_version='current recipient version',delivery='own received report delivery ID'),'Immutable dated observation with original observer and prior-delivery provenance, never new sight or automatic trust. Already-informed recipients do not create new deliveries or reaction loops. Nearby players see a post-commit notice.',relay_received_report,None,('world',))

from .npc_tactics import configure as configure_tactics
CAPABILITIES["world.set_tactics"]=Capability("Choose composable native battle AI preferences for this generated trainer optional challenges.",dict(flags="JSON list: setup_first, risky, seek_two_hit_ko, baton_pass, hp_aware, field_status, prefer_status, reserve_ace; [] restores normal"),"Frozen at battle preparation; no guaranteed moves, new stats, training or victories. Existing moves/party only; canonical and co-op encounters unchanged. No omniscience.",configure_tactics,None,("world",))

from .route_rematch_events import configure as configure_rematch_event
CAPABILITIES['world.organize_rematches']=Capability('Organize temporary optional rematch availability on an existing Hoenn route.',dict(route='route from route_rematch_events catalog',minutes='0..1440; zero closes own event'),'Original registered previously defeated trainers, personal native badge and team progression. No forced fights, attendance, consent, outcome, shared credit or growth inferred. Other organizer active events cannot be replaced.',configure_rematch_event,None,('canonical','world'))

from .player_tournaments import publish as publish_tournament
CAPABILITIES['world.publish_tournament']=Capability('Invite 2/4/8 consenting players to a persistent native singles tournament.',dict(id='stable public ID <=24',title='public title <=60 ASCII',size='2,4 or8'),'Public entrant names and matching session-bound native client reports, not verified victories. Each match requires normal proximity and opponent acceptance; disagreement/disconnect needs both entrants to retry. No party normalization or save/reward changes.',publish_tournament,None,('canonical','world'))
from .player_tournaments import cancel as cancel_tournament
CAPABILITIES['world.cancel_tournament']=Capability('Cancel your own open tournament without inventing winners or stopping native battles.',dict(id='own tournament ID'),'Durable cancellation, releasing active capacity. Previously reported results remain historical; in-flight battles are separate and do not advance this bracket.',cancel_tournament,None,('canonical','world'))

from .pyramid_courses import publish as publish_pyramid, close as close_pyramid
CAPABILITIES["world.publish_pyramid_course"]=Capability("Publish a reproducible seven-floor course using native Battle Pyramid geometry.",dict(id="immutable lowercase course ID",seed="uint32 generation seed"),"Native seed/template forecast and optional player admission. Existing facility rules and private save progression apply; no visits, identical enemy teams or victories inferred.",publish_pyramid,None,("world","canonical"))
CAPABILITIES["world.close_pyramid_course"]=Capability("Close own Pyramid course to new downloads.",dict(id="own course ID"),"Already downloaded/admitted personal courses remain valid.",close_pyramid,None,("world","canonical"))

from .spatial_signals import signal as spatial_signal
CAPABILITIES["world.signal"]=Capability("Place a short-lived visible intent marker at this stationary native-map resident position.",dict(kind="look, meet, help or danger"),"Nearby opted-in players may see a stock field arrow. Actual public town/route position, not verified danger, assistance or rendered acknowledgement. No collision objects or save edits.",spatial_signal,None,("world",))

from .starter_offers import tool as starter_offer_tool
CAPABILITIES['world.starters']=Capability('Inspect, publish or close optional fresh-save starter offers using native Birch selection.',dict(operation='inspect, publish or close',value='inspect: empty string; publish: JSON {id,species:[three distinct catalog names]}; close: own offer ID'),'Player explicitly loads and chooses. Native level-5 grant, story and rival slot teams remain native. No Pokemon adoption or victory inferred.',starter_offer_tool,None,('world','canonical'))

from .maze_courses import tool as maze_course_tool
CAPABILITIES['world.maze_courses']=Capability('Preview and publish newly generated collision-checked maze layouts in native Trainer Hill.',dict(operation='inspect, preview, publish or close',value='inspect: empty string; preview: seed 0..4095; publish: JSON {id,seed}; close: own ID'),'Four real generated layouts with native selected-mode trainers. Explicit next-run player opt-in; no vanilla prizes or best-time writes, no completed exploration/battle inferred.',maze_course_tool,None,('world','canonical'))

from .overworld_moves import use as use_world_move
CAPABILITIES['world.use_move']=Capability('Use an actually learned companion move on an observed authored prop action.',dict(object='observed prop ID',action='advertised move action',object_revision='observed object_revision',individual='owned on-team individual with matching current native move inspection',move='learned native move ID'),'Existing shared-object executor admits actual state/appearance change. Requires current reconciled native move slots; no battle, PP consumption, growth or canonical-world destruction.',use_world_move,poll_object,('world',))

from .move_selectors import inspect_rules
CAPABILITIES['world.inspect_move_rules']=Capability('Inspect native move selectors before authoring reusable world responses.',dict(selector='JSON exact ID list or {types:[water],categories:[special],exclude:[ID]}; types/categories intersect, values within each list are alternatives',after='last move ID for paging, initially 0'),'Up to24 static catalog entries; never evidence of ownership or learned moves. Configuration-dependent traits omitted.',inspect_rules,None,('canonical','world'))

from .reconstruction import queue as queue_reconstruction,poll as poll_reconstruction,cancel as cancel_reconstruction
CAPABILITIES['world.reconstruct_environment']=Capability('Plan inspected terrain reconstruction after the area becomes vacant.',dict(observation='own world.inspect_environment receipt',tiles='JSON <=700 chars of inspected {x,y,terrain} cells'),'Pending durable plan, not live construction. Unchanged native geometry transaction commits only while empty; stale revision conflicts, no automatic rebase.',queue_reconstruction,poll_reconstruction,('canonical','world'))
CAPABILITIES['world.cancel_reconstruction']=Capability('Cancel own pending reconstruction without terrain changes.',dict(id='own reconstruction ID'),'No rollback of completed work.',cancel_reconstruction,None,('canonical','world'),during_activity=True)

from .actor_methods import remember as remember_method,unavailable as perform_method,inspect_object
CAPABILITIES['world.remember_method']=Capability('Retain your own actually completed public action sequence as an immutable reusable method.',dict(name='new lowercase method name',plan='own completed plan ID',parameters='JSON object up to8 name:{step,argument} literal slots. Reviewed observe/navigate/inspect_object/use_object/set_weather only; every prior step must be a dependency, revisions and use_object identity must reference fresh observations.'),'Stored public method with exact successful outcome evidence; no new effect or skill mastery invented.',remember_method,None,('world',))
CAPABILITIES['world.perform_method']=Capability('As the sole step of a new plan, compile an own retained method into ordinary fresh capability steps.',dict(method='own retained method name',digest='exact retained digest',bindings='JSON object supplying every parameter with the original scalar type'),'Fresh observations and guarded real actions, independently receipted. Reuses no past state, receipt or success. Restart resumes exact expanded plan; no nested executor or canonical/player-save effects.',perform_method,None,('world',))
CAPABILITIES['world.inspect_object']=Capability('Inspect a specific adjacent public object through a fresh bounded local observation.',dict(object='nearby public object ID'),'Fresh scalar object identity/revision and advertised actions for result-reference composition; no remote/private knowledge.',inspect_object,None,('world',))

from .encounter_profiles import configure as configure_encounter_profile
CAPABILITIES['world.configure_encounter_profile']=Capability('Author a voluntary move-driven ordinary walking encounter filter for a reviewed Hoenn route.',dict(map='route from encounter_profiles.maps',selector='JSON move selector, same as world.inspect_move_rules',accept='25..99 percent acceptance of ordinary generated encounters',prefer_move_type='0 or 1: matching final species types retain 100 percent acceptance',steps='10..200 eligible walking step countdown',pp='1..4 PP cost shown before player confirmation'),'Configuration only. Native actual learned move, PP and explicit consent are required. Filters actual post-shuffle table species; never creates species, guarantees catches, alters personal roamers/outbreaks or changes item counters.',configure_encounter_profile,None,('canonical','world'))

from .move_sensing import configure as configure_move_sensing
CAPABILITIES['world.configure_move_sensing']=Capability('Author optional move-based hidden-item reconnaissance on a reviewed ordinary route.',dict(map='route from move_sensing.maps',selector='existing bounded move selector JSON',radius='1..5 current-map tile radius',pp='1..4 native PP cost per scan'),'Configuration only. Player needs Itemfinder and actual learned move, separately consents to lookup, scan/PP and any nearby clue sharing. Personal collection flags remain private unless a clue is explicitly volunteered. No item granted, NPC knowledge, verified discovery or collection implied.',configure_move_sensing,None,('canonical','world'))

from .move_weather import configure as configure_move_weather
CAPABILITIES['world.configure_move_weather']=Capability('Author optional learned-move temporary local weather on a reviewed route.',dict(map='route from move_weather.maps',selector='bounded existing move selector JSON',weather='rain, sandstorm or sun',frames='600..3600 weather-task ticks; paused during battle',pp='1..4 native PP cost'),'Configuration only. Player explicitly requests a profile and confirms native PP cost. No shared climate or verified activation. Native clear stable weather required; story/map weather takes priority. Stock weather forms and initial battle weather apply.',configure_move_weather,None,('canonical','world'))

from .passage_lifecycle import configure as configure_passage
CAPABILITIES['world.set_passage']=Capability('Close or reopen both directions of an owned existing physical cave passage.',dict(connection='exact ID from passage_lifecycle discovery',revision='current passage lifecycle revision',operation='close or open'),'Atomic durable route availability and native closed caption. Refuses affected in-flight player transfers or current NPC journeys. No redirect, deletion, forced travel or loss of private return warp; regional menus remain available.',configure_passage,None,('canonical','world'))

from .move_witnesses import configure as configure_move_attention
CAPABILITIES['world.attend_moves']=Capability('Notice locally committed shared move actions, including unchanged-object contributions, and independently choose how to react.',dict(mode='local or off',radius='connected cardinal radius integer 1..4',cooldown='minimum notice interval seconds integer 30..3600'),'Opt-in durable observation at actual admission; bounded batches retain exact receipts and client/native provenance. Existing enrolled author and host budgets, no automatic model launch or scripted response. Reobserve before acting.',configure_move_attention,None,('world',))

from .player_npc_memory import appraise as appraise_player
CAPABILITIES['world.appraise_player']=Capability('Form a subjective fictional appraisal of a visitor who explicitly consented to this NPC remembering future public interactions.',dict(visitor='own active consented pseudonymous visitor handle',evidence='exact subsequent linked speech or reported challenge event sequence',text='subjective appraisal, 1..160 ASCII characters',battle='open, invite or decline this optional dynamic challenge',greeting='personalized native dialogue, 1..28 ASCII characters'),'Public interpretation, never verified victory, friendship score or forced battle. No retroactive identity linkage or private party access. Current consent and policy checked before native opponent freeze; revocation does not rewrite accepted battles.',appraise_player,None,('world',))
from .actor_rendezvous import start as rendezvous_start, poll as rendezvous_poll
CAPABILITIES['world.rendezvous']=Capability('Seek another active world character using actual paths and installed cave links; re-evaluate their position between legs.',dict(target='persistent generated-world character ID'),'Actual adjacent idle authority objects and current recipient version; no forced recipient response or fictional meeting. At most sixteen completed legs per plan; unchanged existing occupancy and staging guards.',rendezvous_start,rendezvous_poll,('world',))

from .move_assistance import respond as respond_move_help,poll as poll_move_help
CAPABILITIES['world.respond_move_help']=Capability('Independently decline or help a nearby player with an explicitly requested shared object move action.',dict(request='current public move assistance request ID',decision='help or decline',individual='own on-team individual; empty for decline',move='currently inspected learned move ID; 0 for decline'),'Normal object revision, proximity, ownership and learned-move validation. Actual admitted shared effect and receipt only, no commanded NPC, reward, PP or guaranteed result. Player can withdraw; submitted actions settle honestly.',respond_move_help,poll_move_help,('world',))

from .npc_absence import start as start_absence,poll as poll_absence
CAPABILITIES['world.take_leave']=Capability('Choose temporary absence and safe return at this generated-place character retained position.',dict(seconds='60..86400 seconds after actual departure admission'),'Actual object removal and reintroduction, preserving individual state/history. Waits for safe original geometry/tile. No off-screen activity, healing, travel or canonical movement. Keep this pending plan until it settles; replacing it leaves an honest away state requiring explicit action.',start_absence,poll_absence,('world',))

from .method_exchange import offer as offer_method,respond as respond_method
CAPABILITIES['world.offer_method']=Capability('Offer a first-hand experienced public action method to an adjacent generated NPC. Recipient chooses independently.',dict(lesson='new immutable lesson name',recipient='adjacent NPC identity',method='own experienced method',digest='exact method digest'),'Ten-minute public offer; no execution or transfer of Pokémon.',offer_method,None,('world',))
CAPABILITIES['world.respond_method']=Capability('Voluntarily accept or decline a teaching offer, or withdraw your own pending offer.',dict(lesson='exact lesson ID',decision='accept, decline or withdraw',name='new own method name when accepting'),'Accepted recipe retains teacher evidence, not recipient success. Use world.perform_method later with fresh observations and ordinary guards.',respond_method,None,('world',))

from .native_trade_offers import configure as configure_native_trade
CAPABILITIES['world.configure_native_trade']=Capability('Offer a repeatable newly generated native Pokemon exchange, not an owned companion.',dict(requested='reviewed species name, or empty to close',offered='distinct reviewed species name, or empty to close'),'Configuration only. Nearby ordinary-Hoenn players explicitly request the frozen template, select their own Pokemon and confirm native trade. No world inventory, limited stock, server trade result or NPC growth.',configure_native_trade,None,('world',))

from .floorplans import configure as configure_floorplan
CAPABILITIES['world.publish_floorplan']=Capability('Publish an immutable optional Secret Base furniture layout, never a player inventory edit.',dict(id='unique lowercase id',design='JSON {title,layout,placements:[[decoration_id,x,y],...]}; 1..16 native bottom-left anchors, or empty to close'),'Public design metadata only. Player requests guidance privately, chooses their own unused furniture in stock PC UI, and explicitly confirms native placement. No automatic build, save, completion or sharing.',configure_floorplan,None,('canonical','world'))

from .regional_campaigns import inspect as inspect_campaign_destinations
CAPABILITIES['world.inspect_campaign_destinations']=Capability(
    'Inspect a bounded page of existing Hoenn or combined Kanto maps for optional campaign visit stages.',
    dict(region='hoenn or kanto',offset='nonnegative page offset, default 0'),
    'Exact map bounds and required registry; not a route, unlock, visit or completion.',
    inspect_campaign_destinations,None,('canonical','world'))


from .npc_organizations import found as found_organization, invite as invite_organization, decide as decide_organization, propose as propose_organization
CAPABILITIES['world.found_organization']=Capability('Found a persistent fictional NPC group without enrolling anyone else.',dict(id='new stable lowercase ID',name='public name <=40 ASCII',goal='public fictional shared purpose <=120 ASCII'),'Own voluntary membership only; no powers, resources, work or player affiliation granted.',found_organization,None,('world','canonical'))
CAPABILITIES['world.invite_organization']=Capability('Invite another active character to your organization. They decide independently.',dict(organization='current group ID',target='existing active actor ID'),'Public invitation bound to current membership revision, not membership or agreement.',invite_organization,None,('world','canonical'))
CAPABILITIES['world.decide_organization']=Capability('Accept or decline your invitation, or freely leave your current organization.',dict(organization='group ID',decision='join, decline or leave'),'Membership change invalidates old joint project consent and invites. History remains; no forced participation.',decide_organization,None,('world','canonical'))
CAPABILITIES['world.propose_organization_project']=Capability('Propose an exact normal world action to every current group member, optionally offering your existing adventure after commitment.',dict(organization='group ID',purpose='public fictional purpose <=120 ASCII',tool='existing agreements.supported tool',args='exact operation JSON <=500 chars',hours='expiry 1..24',campaign='own published campaign ID or empty string'),'Existing agreement executor requires each member to decide independently and proposer to commit. Membership grants no authority. Optional campaign becomes discoverable only after real commitment, not automatic player enrolment.',propose_organization,None,('world','canonical'))

from .procedural_adventures import start as build_adventure,poll as adventure_poll
CAPABILITIES['world.build_adventure']=Capability('Create connected explorable places with optional residents, playful mechanisms and campaign objectives.',dict(document='JSON <=6000 chars: label, constraints (generate_region_network schema), optional place_names (one distinct name per place, <=20 chars), trainers (0..4 originals; optional anchor anywhere/entrance/exit), optional habitats ([{place,profile,rate,criteria}] using world.compose_habitat criteria OR {place,profile,rate,slots} with 12 explicit [species,level] pairs), optional mechanisms (0..2: id,place,props [{id,gfx,text}],program with relative dx/dy appearances), optional campaign (opponent/win/loss, mechanism/next or expedition resolutions). Refer to new network IDs; definition digests bound by compiler. Quiet places and residents/objects without objectives are valid. Use a blueprint for larger documents.'),'Existing geometry/population/campaign validation and normal staging. Exact request resumes retained places without duplicating or rewinding characters. Only final admission publishes campaign; players choose entry and independent participation. Plain caves, no story flags, copied assets or claimed wins.',build_adventure,adventure_poll,('world','canonical'))
from .hoenn_markets import configure as configure_hoenn_market
CAPABILITIES['world.arrange_market_shelf']=Capability('Offer optional community stock in a reviewed original Hoenn mart; actual consenting checkout reports can inform later choices.',dict(site='site from hoenn_markets catalog',items='JSON list of up to eight reviewed item IDs; empty closes',minutes='1..1440, or zero to close'), 'Native unlimited retail at stock prices. Catalog authorship is not delivery, merchant agreement or profit. Disclosed Community stock checkouts can yield anonymous client-reported item/count history, not attested spending. Usual stock unchanged; open visits retain frozen catalog.',configure_hoenn_market,None,('canonical','world'))


from .rematch_strategies import configure as configure_rematch_strategy
CAPABILITIES['world.rematch_strategy']=Capability('Publish persistent optional tactics for reviewed original Hoenn trainers.',dict(trainer='key from rematch_strategies catalog',expected_revision='exact inspected current revision; zero if absent',types='1..3 ordered type preferences',status_moves='0..2 preferred status slots',active='optional boolean; false withdraws future offers, retaining history'),'Native level-legal moves only; original species/levels/items and rewards. Consenting solo challenges report real client outcomes without player names. No autonomous training or shared story progress inferred.',configure_rematch_strategy,None,('canonical','world'))
from .route_trainers import configure as configure_route_trainers
CAPABILITIES['world.arrange_route_trainers']=Capability('Author an optional normal trainer sight disposition on a reviewed original Hoenn route.',dict(route='route from route_trainers catalog',mode='usual, resting or watchful',minutes='1..1440, zero withdraws your policy',reason='printable public explanation, 1..28 characters'),'Personal opt-in only. Real native battles/defeats unchanged; no actual character mood or agreement inferred. Direct conversation still battles. Other actors active policies are preserved.',configure_route_trainers,None,('canonical','world'))

from .trick_questions import configure as configure_trick_questions
CAPABILITIES["world.trick_questions"]=Capability("Author an optional five-gate question pack for the original Trick House fifth room.",dict(expected_revision="current revision, zero if absent",title="1..24 plain characters",questions="exactly five question/choices/answer objects; question <=96 chars, three distinct choices <=18 chars, answer index 0..2",active="boolean; withdraw future downloads"),"Player explicitly chooses; original native gates and reward progression. Frozen for the visit, private answers, no reports or fabricated history.",configure_trick_questions,None,("canonical","world"))
