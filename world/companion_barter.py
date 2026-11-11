"""Independent, reciprocal exchanges of two real benched companions.

Both ownership changes share the capability executor's transaction and receipt.
No native player trade, trade evolution, capture or battle is inferred.
"""
import hashlib,json,re
from .companion_exchange import colocated,snapshot,transfer,identity


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS companion_barters(id TEXT PRIMARY KEY,sender TEXT,recipient TEXT,terms TEXT,status TEXT)')


def offers(server):
    result=[]
    for key,sender,recipient,raw,status in server.db.execute("SELECT * FROM companion_barters WHERE status='offered' ORDER BY id"):
        terms=json.loads(raw)
        summary={k:terms[k] for k in ('give','receive','sender_alias','recipient_alias')}
        summary['giving']={k:terms['left']['member'][k] for k in ('species','level','individual')}
        summary['receiving']={k:terms['right']['member'][k] for k in ('species','level','individual')}
        result.append(dict(id=key,sender=sender,recipient=recipient,terms=summary,status=status))
    return result


def propose(server,actor,row,args):
    keys={'target','give','receive','sender_alias','recipient_alias'}
    if set(args)!=keys or any(type(v) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}',v) for v in args.values()):
        raise ValueError('Supply recipient, two existing individual IDs and their receiving local aliases')
    target=args['target'];colocated(server,actor,target)
    if server.db.execute("SELECT 1 FROM companion_barters WHERE status='offered' AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))",(actor,target,target,actor)).fetchone():
        raise ValueError('Resolve or withdraw the existing proposal between these characters first')
    left=snapshot(server,actor,args['give']);right=snapshot(server,target,args['receive'])
    if left['member']['personality']==right['member']['personality'] and left['member']['owner']==right['member']['owner']:
        raise ValueError('Exchange requires distinct native individuals')
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Durable capability executor required')
    # Full state is frozen internally; it is not copied into the public offer.
    terms=dict(args,left=left,right=right)
    key=hashlib.sha256(json.dumps([actor,execution[2]['id'],execution[3]['id']],sort_keys=True).encode()).hexdigest()
    server.db.execute('INSERT INTO companion_barters VALUES(?,?,?,?,?)',(key,actor,target,json.dumps(terms,sort_keys=True),'offered'))
    server.memory.append('companion_barter_offered',dict(sender=actor,recipient=target,offer=key,give=args['give'],receive=args['receive'],basis='adjacent_owned_companion_exchange',limits='Proposal only. Recipient independently decides; both Pokemon remain with their owners.'))
    return dict(outcome='reciprocal_exchange_offered',offer=key,recipient=target)


def respond(server,actor,row,args):
    if set(args)!={'offer','decision'} or args['decision'] not in ('accept','decline','withdraw'):
        raise ValueError('Choose accept, decline or sender withdraw')
    saved=server.db.execute('SELECT sender,recipient,terms,status FROM companion_barters WHERE id=?',(args['offer'],)).fetchone()
    if not saved or saved[3]!='offered':raise ValueError('Exchange proposal unavailable')
    sender,recipient,raw,_=saved;terms=json.loads(raw)
    if actor!=(sender if args['decision']=='withdraw' else recipient):raise ValueError('Only the recipient may decide; only sender may withdraw')
    result=dict(offer=args['offer'],sender=sender,recipient=recipient,decision=args['decision'])
    if args['decision']=='accept':
        colocated(server,sender,recipient)
        left=snapshot(server,sender,terms['give']);right=snapshot(server,recipient,terms['receive'])
        if left!=terms['left'] or right!=terms['right']:
            raise ValueError('A companion changed or left the bench; propose new terms')
        # transfer has no transaction boundary. A failed second leg, public
        # event or tool receipt therefore rolls back the entire exchange.
        first=transfer(server,recipient,terms['recipient_alias'],left)
        second=transfer(server,sender,terms['sender_alias'],right)
        result.update(outcome='reciprocal_companions_transferred',sender_received=terms['sender_alias'],
            recipient_received=terms['recipient_alias'],identities=[identity(first),identity(second)],on_team=False)
    else:result['outcome']='reciprocal_exchange_'+args['decision']
    server.db.execute('UPDATE companion_barters SET status=? WHERE id=?',(args['decision'],args['offer']))
    server.memory.append('companion_barter_resolved',dict(result,basis='adjacent_owned_companion_exchange',limits='Existing world companion custody only. No player save, evolution, new capture, battle, team change or friendship inferred.'))
    return result


def relevant(event,actor):
    return (event.get('event') in ('companion_barter_offered','companion_barter_resolved')
            and event.get('basis')=='adjacent_owned_companion_exchange'
            and actor in (event.get('sender'),event.get('recipient')))
