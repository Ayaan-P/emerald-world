"""Voluntary NPC agreements that commit exact existing shared-world operations."""
import hashlib,json,time

# Only reviewed synchronous, authority-only executors. No pending jobs, player
# save effects, provider calls, permissions, arbitrary code or nested agreements.
TOOLS=('world.configure_outbreak','world.configure_fishing','world.set_weather')
BASIS='voluntary_exact_world_action_agreement'


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_agreements(id TEXT PRIMARY KEY,proposer TEXT,terms TEXT,decisions TEXT,status TEXT,expires REAL,result TEXT)')


def load(server,key):
    if type(key) is not str:raise ValueError('Use an actual agreement ID')
    saved=server.db.execute('SELECT proposer,terms,decisions,status,expires,result FROM actor_agreements WHERE id=?',(key,)).fetchone()
    if not saved:raise ValueError('Unknown agreement')
    proposer,terms,decisions,status,expires,result=saved
    return proposer,json.loads(terms),json.loads(decisions),status,expires,json.loads(result) if result else None


def active_actors(server,ids):
    from .actor_runtime import actor_records
    records=actor_records(server)
    if any(i not in records or records[i].get('status','active')!='active' for i in ids):raise ValueError('Every participant must be an existing active world or canonical character')
    return records


def event(server,key,proposer,agreement_terms,kind,**extra):
    seq=server.memory.append(kind,dict(agreement=key,character_id=proposer,participants=agreement_terms['participants'],basis=BASIS,**extra))
    server.revision=seq
    return seq


def propose(server,actor,row,args):
    from .actor_runtime import CAPABILITIES
    if set(args)!={'participants','purpose','tool','args','hours'} or type(args['participants']) is not str or type(args['args']) is not str or len(args['args'])>500:raise ValueError('Supply participants JSON, purpose, exact supported tool/argument JSON and duration')
    try:participants=json.loads(args['participants']);operation=json.loads(args['args'])
    except ValueError:raise ValueError('Invalid agreement JSON') from None
    if type(participants) is not list or not 1<=len(participants)<=3 or any(type(p) is not str for p in participants) or actor in participants or len(set(participants))!=len(participants):raise ValueError('Invite one to three distinct other actors')
    records=active_actors(server,[actor,*participants])
    if args['tool'] not in TOOLS:raise ValueError('Choose an advertised agreement-safe operation')
    capability=CAPABILITIES[args['tool']]
    if ('canonical' if records[actor].get('canonical') else 'world') not in capability.kinds:raise ValueError('Proposer cannot perform that capability')
    if type(operation) is not dict or set(operation)!=set(capability.arguments) or any(type(v) not in (str,int) or type(v) is bool for v in operation.values()):raise ValueError('Freeze exact literal operation arguments, without result references')
    if type(args['purpose']) is not str or not 1<=len(args['purpose'])<=120 or any(not 32<=ord(c)<127 for c in args['purpose']):raise ValueError('Use a bounded public fictional purpose')
    if type(args['hours']) is not int or not 1<=args['hours']<=24:raise ValueError('Agreement expires in 1..24 hours')
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Durable actor executor required')
    key=hashlib.sha256(json.dumps([server.memory.world_id,actor,execution[2]['id'],execution[3]['id']]).encode()).hexdigest()
    terms=dict(participants=[actor,*participants],purpose=args['purpose'],tool=args['tool'],args=operation)
    if server.db.execute('SELECT 1 FROM actor_agreements WHERE id=?',(key,)).fetchone():raise ValueError('Agreement identity already exists')
    if server.db.execute("SELECT count(*) FROM actor_agreements WHERE status='open' AND expires>?",(time.time(),)).fetchone()[0]>=32:raise ValueError('Resolve or let existing open agreements expire first')
    server.db.execute('INSERT INTO actor_agreements VALUES(?,?,?,?,?,?,NULL)',(key,actor,json.dumps(terms,sort_keys=True),json.dumps({actor:'accept'}),'open',time.time()+args['hours']*3600))
    event(server,key,actor,terms,'actor_agreement_proposed',terms=terms,limits='Public fictional proposal, not a command, granted permission, completed action or physical meeting.')
    return dict(outcome='world_action_proposed',agreement=key,participants=terms['participants'])


def decide(server,actor,row,args):
    if set(args)!={'agreement','decision'} or args['decision'] not in ('accept','decline','withdraw'):raise ValueError('Choose accept, decline or proposer withdrawal')
    proposer,terms,decisions,status,expires,_=load(server,args['agreement'])
    if status!='open' or expires<=time.time():raise ValueError('Agreement is closed or expired')
    active_actors(server,terms['participants'])
    if actor not in terms['participants'] or (args['decision']=='withdraw' and actor!=proposer):raise ValueError('Only invited actors decide; only proposer withdraws')
    if actor==proposer and args['decision']!='withdraw':raise ValueError('Proposer already accepted; withdraw to cancel')
    if args['decision']=='accept' and decisions.get(actor)=='accept':return dict(outcome='agreement_already_accepted',agreement=args['agreement'])
    decisions[actor]=args['decision'];status='open' if args['decision']=='accept' else 'cancelled'
    server.db.execute('UPDATE actor_agreements SET decisions=?,status=? WHERE id=?',(json.dumps(decisions,sort_keys=True),status,args['agreement']))
    event(server,args['agreement'],proposer,terms,'actor_agreement_decided',decider=actor,decision=args['decision'])
    return dict(outcome='agreement_'+args['decision'],agreement=args['agreement'],ready=status=='open' and all(decisions.get(a)=='accept' for a in terms['participants']))


def commit(server,actor,row,args):
    from .actor_runtime import CAPABILITIES
    if set(args)!={'agreement'}:raise ValueError('Choose an actual accepted agreement')
    proposer,terms,decisions,status,expires,result=load(server,args['agreement'])
    if actor!=proposer:raise ValueError('Only proposer can execute its own agreed operation')
    if status=='applied':return dict(outcome='agreement_already_applied',agreement=args['agreement'],result=result)
    if status!='open' or expires<=time.time() or not all(decisions.get(a)=='accept' for a in terms['participants']):raise ValueError('Every participant must independently accept before expiry')
    records=active_actors(server,terms['participants']);cap=CAPABILITIES[terms['tool']]
    if terms['tool'] not in TOOLS or cap.poll is not None or ('canonical' if records[actor].get('canonical') else 'world') not in cap.kinds:raise ValueError('Agreed operation is no longer available')
    # Called within the ordinary actor executor transaction. Its original
    # ownership/location/geometry/species guards remain the only effect authority.
    result=cap.execute(server,actor,row,terms['args'])
    if type(result) is not dict:raise ValueError('Agreement operation did not produce a synchronous real result')
    server.db.execute("UPDATE actor_agreements SET status='applied',result=? WHERE id=?",(json.dumps(result,sort_keys=True),args['agreement']))
    event(server,args['agreement'],proposer,terms,'actor_agreement_applied',tool=terms['tool'],result=result,limits='Exact authority configuration committed; no fictional purpose, simulation, native display or player encounter claimed.')
    return dict(outcome='agreed_world_action_committed',agreement=args['agreement'],result=result)


def discover(server):
    setup(server.db)
    return dict(supported=list(TOOLS),open=[dict(id=k,proposer=p,terms=json.loads(t),decisions=json.loads(d),expires=e) for k,p,t,d,e in server.db.execute("SELECT id,proposer,terms,decisions,expires FROM actor_agreements WHERE status='open' AND expires>? ORDER BY id LIMIT 32",(time.time(),))],semantics='Public NPC agreements, not operator instructions or new authority. Each actor chooses independently; proposer executes exact existing operation with original guards.')


def relevant(event,actor):
    return event.get('event') in ('actor_agreement_proposed','actor_agreement_decided','actor_agreement_applied') and event.get('basis')==BASIS and actor in event.get('participants',[])
