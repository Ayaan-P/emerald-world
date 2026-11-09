"""Voluntary inter-actor work with explicit, authority-receipt completion terms.

A request is fictional speech, never new permission or a forced plan. Completion
means the exact requested operation/result occurred, not that prose became true.
"""
import hashlib,json
from .companion_exchange import colocated


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_cooperation(id TEXT PRIMARY KEY,sender TEXT,recipient TEXT,terms TEXT,status TEXT,accepted INTEGER,result INTEGER)')


def discover(server):
    return [dict(id=k,sender=s,recipient=r,terms=json.loads(t),status=st,accepted=a,result=p)
            for k,s,r,t,st,a,p in server.db.execute("SELECT * FROM actor_cooperation WHERE status IN ('offered','accepted') ORDER BY id")]


def request(server,actor,row,args):
    from .actor_runtime import CAPABILITIES
    if set(args)!={'target','purpose','tool','where'}:
        raise ValueError('Supply recipient, public purpose, existing tool and exact result predicate')
    purpose=args['purpose'];tool=args['tool']
    if type(purpose) is not str or not 1<=len(purpose)<=120 or any(not 32<=ord(c)<=126 for c in purpose):
        raise ValueError('Use up to 120 printable public fictional characters')
    if type(tool) is not str or tool not in CAPABILITIES or 'world' not in CAPABILITIES[tool].kinds or tool in TOOLS:
        raise ValueError('Choose an existing world-character capability, not another cooperation operation')
    if type(args['where']) is not str or len(args['where'])>350:raise ValueError('Use bounded result predicate JSON')
    try:where=json.loads(args['where'])
    except ValueError:raise ValueError('Invalid result predicate') from None
    if (type(where) is not dict or not 1<=len(where)<=4 or 'outcome' not in where
            or any(type(k) is not str or not 1<=len(k)<=40 or type(v) not in (str,int,bool) or (type(v) is str and len(v)>100) for k,v in where.items())):
        raise ValueError('Use outcome and up to three other exact scalar result fields')
    target=args['target']
    if type(target) is not str:raise ValueError('Use an existing recipient actor ID')
    colocated(server,actor,target)
    if server.db.execute("SELECT 1 FROM actor_cooperation WHERE status IN ('offered','accepted') AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))",(actor,target,target,actor)).fetchone():
        raise ValueError('Resolve the existing cooperation between these characters first')
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Durable capability executor required')
    key=hashlib.sha256(json.dumps([actor,execution[2]['id'],execution[3]['id']]).encode()).hexdigest()
    terms=dict(purpose=purpose,tool=tool,where=where)
    server.db.execute('INSERT INTO actor_cooperation VALUES(?,?,?,?,?,NULL,NULL)',(key,actor,target,json.dumps(terms,sort_keys=True),'offered'))
    server.memory.append('character_cooperation_requested',dict(request=key,sender=actor,recipient=target,terms=terms,basis=BASIS))
    return dict(outcome='cooperation_requested',request=key,recipient=target)


def load(server,key):
    if type(key) is not str:raise ValueError('Use an actual request identity')
    saved=server.db.execute('SELECT sender,recipient,terms,status,accepted FROM actor_cooperation WHERE id=?',(key,)).fetchone()
    if not saved:raise ValueError('Unknown cooperation request')
    return saved


def respond(server,actor,row,args):
    if set(args)!={'request','decision'} or args['decision'] not in ('accept','decline','withdraw','abandon'):
        raise ValueError('Choose accept/decline as recipient, withdraw as sender, or abandon accepted work as recipient')
    sender,recipient,raw,status,accepted=load(server,args['request']);decision=args['decision']
    if actor!=(sender if decision=='withdraw' else recipient):raise ValueError('Only the appropriate participant may decide')
    if status not in ('offered','accepted') or (decision in ('accept','decline') and status!='offered') or (decision=='abandon' and status!='accepted'):
        raise ValueError('Request is no longer in the required state')
    seq=server.memory.append('character_cooperation_decided',dict(request=args['request'],sender=sender,recipient=recipient,decision=decision,basis=BASIS))
    next_status='accepted' if decision=='accept' else decision
    server.db.execute('UPDATE actor_cooperation SET status=?,accepted=? WHERE id=?',(next_status,seq if decision=='accept' else accepted,args['request']))
    return dict(outcome='cooperation_'+next_status,request=args['request'],decision_seq=seq,
        limits='No work performed by this decision. Recipient chooses its own existing capabilities and can abandon. Cancellation does not undo already committed actions.')


def deliver(server,actor,row,args):
    if set(args)!={'request','receipt'} or type(args['receipt']) is not int:raise ValueError('Supply request and own successful action receipt')
    sender,recipient,raw,status,accepted=load(server,args['request'])
    if actor!=recipient or status!='accepted' or args['receipt']<=accepted:raise ValueError('Only accepted recipient work performed after acceptance qualifies')
    saved=server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(args['receipt'],)).fetchone()
    if not saved:raise ValueError('Actual committed action evidence required')
    event=json.loads(saved[0]);terms=json.loads(raw);result=event.get('result')
    if (event.get('event')!='actor_tool_result' or event.get('source')!='authority_capability_runtime'
            or event.get('character_id')!=actor or event.get('tool')!=terms['tool'] or event.get('status')!='succeeded'
            or type(result) is not dict or any(type(result.get(k)) is not type(v) or result.get(k)!=v for k,v in terms['where'].items())):
        raise ValueError('Receipt does not demonstrate the requested exact operation and result')
    server.db.execute("UPDATE actor_cooperation SET status='delivered',result=? WHERE id=?",(args['receipt'],args['request']))
    server.memory.append('character_cooperation_delivered',dict(request=args['request'],sender=sender,recipient=recipient,receipt=args['receipt'],tool=terms['tool'],result=result,basis=BASIS,
        limits='Verified historical capability result, not proof the prose purpose was achieved, current state persists, or NPC labor was animated.'))
    return dict(outcome='cooperation_evidence_delivered',request=args['request'],receipt=args['receipt'],recipient=sender)


BASIS='voluntary_authority_action_cooperation'
TOOLS={'world.request_cooperation','world.respond_cooperation','world.deliver_cooperation'}
def relevant(event,actor):
    return event.get('event') in ('character_cooperation_requested','character_cooperation_decided','character_cooperation_delivered') and event.get('basis')==BASIS and actor in (event.get('sender'),event.get('recipient'))
