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

from .actor_places import create as create_place
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
    from .actor_navigation import discover as discover_navigation
    return dict(capabilities={key:dict(description=c.description,arguments=c.arguments,outcome=c.outcome,actor_kinds=c.kinds) for key,c in CAPABILITIES.items()},
        available_actions=server.opportunities.actor_actions()[:32],actors={a:('canonical' if r.get('canonical') else 'world') for a,r in actor_records(server).items()},
        navigation=discover_navigation(server),carried_props=inventory(server),
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
