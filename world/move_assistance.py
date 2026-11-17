"""Voluntary player requests, independently chosen and executed by real NPCs."""
import json,secrets,time,textwrap
from .guilds import GuildError

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS move_assistance(id INTEGER PRIMARY KEY,actor TEXT,trainer TEXT,session TEXT,terms TEXT,status TEXT,result INTEGER)')

def emit(server,event,actor,key,**data):
    seq=server.memory.append(event,dict(character_id=actor,request=key,basis='explicit_public_move_assistance',**data));server.revision=seq;return seq

def live(server,r):
    p=server.peers.get(r[2]);t=json.loads(r[4])
    return bool(p and not p.get('closing') and p.get('npc_speech_session')==r[3] and t['created']<=time.time()<=t['created']+300)

def catalog(server):
    setup(server.db)
    recover(server)
    return [dict(request=r[0],actor=r[1],**{k:v for k,v in json.loads(r[4]).items() if k!='created'}) for r in server.db.execute("SELECT * FROM move_assistance WHERE status='offered'") if live(server,r)]

def command(server,conn,words):
    return [part for line in _command(server,conn,words) for part in textwrap.wrap(line,110)]

def _command(server,conn,words):
    from .npc_conversations import nearby
    from .object_choices import facing
    from .actor_objects import offers
    from .overworld_moves import requirements
    setup(server.db);recover(server)
    if server.peers.get(conn.get('id')) is not conn or conn.get('closing'):raise GuildError('Authenticated player required')
    session=conn.setdefault('npc_speech_session',secrets.token_hex(16))
    if words and words[0]=='help-accept':return confirm(server,conn,words,session)
    if words==['help-status']:
        return [str(i)+': '+a+' '+s+(' /guild object help-accept '+str(i) if s=='awaiting_confirmation' else '') for i,a,s in server.db.execute('SELECT id,actor,status FROM move_assistance WHERE trainer=? AND session=? ORDER BY id DESC LIMIT 8',(conn['id'],session))] or ['No requests in this session.']
    if len(words)==2 and words[0]=='help-stop' and words[1].isdigit():
        key=int(words[1]);r=server.db.execute('SELECT * FROM move_assistance WHERE id=?',(key,)).fetchone()
        if not r or r[2:4]!=(conn['id'],session):raise GuildError('Choose your own session request')
        if r[5] not in ('offered','awaiting_confirmation','executing'):return ['Request already ended: '+r[5]]
        with server.db:
            server.db.execute("UPDATE move_assistance SET status=? WHERE id=?",('withdrawn_in_flight' if r[5]=='executing' else 'withdrawn',key))
            emit(server,'player_move_help_withdrawn',r[1],key,limits='Stops new acceptance. An already admitted action settles honestly; no rollback or control of autonomous NPC actions.')
        return ['Request withdrawn. Already submitted world actions may still finish.']
    if len(words) not in (3,5) or words[0]!='ask-help':raise GuildError('Face an object: /guild object ask-help NPC ACTION; help-status; help-stop ID.')
    actor,action=words[1:3];_,npc=nearby(server,conn,actor);obj=facing(server,conn);offer=offers(server,obj)
    if (not obj.get('region_revision') or npc.get('region_revision')!=obj['region_revision'] or action not in offer.get('actions',{})
        or action not in requirements(server,obj) or action not in server.module_state.get('world_object_player_choices',{}).get(obj['id'],[])):
        raise GuildError('Choose a currently advertised player move action in this generated place')
    terms=dict(object=obj['id'],action=action,object_revision=offer['object_revision'],revision=obj['region_revision'])
    if len(words)==3:
        token=secrets.token_hex(6);conn['move_help_offer']=dict(actor=actor,terms=terms,token=token,until=time.monotonic()+60)
        return ['OPTIONAL public request: NPC may decline, or use its own learned move on this shared object.',
            'Object action and NPC decision become public history. No party sharing, reward or guaranteed help.',
            'Already submitted effects may finish after withdrawal. No battle PP is used by shared object moves.',
            '/guild object ask-help '+actor+' '+action+' '+token+' yes']
    pending=conn.pop('move_help_offer',None)
    if not pending or pending['actor']!=actor or pending['terms']!=terms or pending['token']!=words[3] or words[4]!='yes' or time.monotonic()>pending['until']:
        raise GuildError('Request changed or expired; inspect again')
    # Only current sessions consume capacity; abandoned requests never block a character forever.
    if any(r['actor']==actor for r in catalog(server)) or server.db.execute("SELECT 1 FROM move_assistance WHERE actor=? AND status IN ('awaiting_confirmation','executing','withdrawn_in_flight')",(actor,)).fetchone():raise GuildError('This NPC already has a request to resolve')
    if sum(live(server,r) for r in server.db.execute("SELECT * FROM move_assistance WHERE trainer=? AND status IN ('offered','awaiting_confirmation')",(conn['id'],)))>=4:raise GuildError('Resolve your existing requests first')
    terms['created']=time.time()
    with server.db:
        seq=emit(server,'player_requested_move_help',actor,None,object=terms['object'],action=action,object_revision=terms['object_revision'],revision=terms['revision'],limits='Request only, not agreement, command, learned-move proof or completion. No player identity published.')
        server.db.execute('INSERT INTO move_assistance VALUES(?,?,?,?,?,?,NULL)',(seq,actor,conn['id'],session,json.dumps(terms,sort_keys=True),'offered'))
    return ['Request '+str(seq)+' sent. NPC chooses independently; expires in five minutes or on disconnect.', 'Use /guild object help-status or /guild object help-stop '+str(seq)+'.']

def respond(server,actor,row,args):
    from .overworld_moves import use
    if set(args)!={'request','decision','individual','move'} or type(args['individual']) is not str or type(args['move']) is not int or type(args['request']) is not int or args['decision'] not in ('help','decline'):raise ValueError('Choose request, help/decline, owned individual and learned move (empty/0 for decline)')
    setup(server.db);r=server.db.execute('SELECT * FROM move_assistance WHERE id=?',(args['request'],)).fetchone()
    if not r or r[1]!=actor or r[5]!='offered' or not live(server,r):raise ValueError('Addressed request is no longer open')
    if args['decision']=='decline':
        server.db.execute("UPDATE move_assistance SET status='declined' WHERE id=?",(r[0],))
        seq=emit(server,'character_move_help_declined',actor,r[0])
        return dict(outcome='move_help_declined',request=r[0],receipt=seq)
    from .actor_runtime import Pending
    from .overworld_moves import prove_companion
    prove_companion(server,actor,args['individual'],args['move'])
    t=json.loads(r[4]);t['execution']=[server.actor_tool_execution[2]['id'],server.actor_tool_execution[3]['id']]
    t['chosen']=dict(individual=args['individual'],move=args['move'])
    server.db.execute("UPDATE move_assistance SET status='awaiting_confirmation',terms=? WHERE id=?",(json.dumps(t,sort_keys=True),r[0]))
    emit(server,'character_move_help_offered',actor,r[0],move=args['move'],limits='NPC independently offered a learned move. Player must inspect and confirm the current action; no effect yet.')
    return Pending(dict(assistance=r[0]),lambda:None)


def confirm(server,conn,words,session):
    from .actor_objects import offers
    from .npc_conversations import nearby
    from .object_choices import facing
    from .overworld_moves import use,requirements
    from .characters import records
    if len(words) not in (2,4) or not words[1].isdigit():raise GuildError('Use help-accept ID, then help-accept ID TOKEN yes')
    key=int(words[1]);r=server.db.execute('SELECT * FROM move_assistance WHERE id=?',(key,)).fetchone()
    if not r or r[2:4]!=(conn['id'],session) or r[5]!='awaiting_confirmation' or not live(server,r):raise GuildError('Your NPC offer is no longer available')
    t=json.loads(r[4]);actor=r[1];character,_=nearby(server,conn,actor);obj=facing(server,conn);offer=offers(server,obj)
    if obj['id']!=t['object'] or obj.get('region_revision')!=t['revision'] or t['action'] not in server.module_state.get('world_object_player_choices',{}).get(obj['id'],[]) or t['chosen']['move'] not in requirements(server,obj).get(t['action'],[]):raise GuildError('Target or move action changed; ask again')
    plan=character.get('plan') or {};execution=t['execution']
    pending=server.db.execute('SELECT status FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',(actor,*execution)).fetchone()
    if plan.get('id')!=execution[0] or pending!=('pending',):raise GuildError('NPC no longer offers this action')
    if len(words)==2:
        token=secrets.token_hex(6);conn['move_help_confirm']=dict(key=key,token=token,revision=offer.get('object_revision'),version=character['version'],until=time.monotonic()+60)
        return [actor+' offers move '+str(t['chosen']['move'])+' for '+t['object']+'/'+t['action']+'.',obj['text'],
            'Confirm the CURRENT shared action. It may finish after withdrawal. No player PP or rewards.',
            '/guild object help-accept '+str(key)+' '+token+' yes']
    p=conn.pop('move_help_confirm',None)
    if not p or p['key']!=key or p['token']!=words[2] or words[3]!='yes' or p['revision']!=offer.get('object_revision') or p['version']!=character['version'] or time.monotonic()>p['until']:raise GuildError('Offer changed or expired; inspect again')
    if server.job is not None or server.deployment is not None or getattr(server,'object_use_pending',None):raise GuildError('World is busy; inspect again')
    previous=server.actor_tool_execution
    try:
        server.actor_tool_execution=(actor,character,dict(id=execution[0]),dict(id=execution[1]))
        with server.db:
            work=use(server,actor,character,dict(object=t['object'],action=t['action'],object_revision=p['revision'],**t['chosen']))
            t['pending']=work.data
            server.db.execute("UPDATE move_assistance SET status='executing',terms=? WHERE id=?",(json.dumps(t,sort_keys=True),key))
            emit(server,'player_confirmed_move_help',actor,key,limits='Submitted actual NPC move under current guards. No completion until admission.')
    except ValueError as exc:raise GuildError(str(exc)) from None
    finally:server.actor_tool_execution=previous
    work.dispatch()
    return ['Submitted. Use /guild object help-status. Completion requires actual shared-world admission.']


def poll(server,actor,row,pending):
    from .actor_objects import poll as poll_object
    r=server.db.execute('SELECT * FROM move_assistance WHERE id=?',(pending['assistance'],)).fetchone()
    if not r:return dict(outcome='move_help_unavailable')
    t=json.loads(r[4])
    if r[5]=='awaiting_confirmation' and live(server,r):return None
    if 'pending' not in t:
        server.db.execute("UPDATE move_assistance SET status='ended' WHERE id=?",(r[0],))
        return dict(outcome='move_help_ended_without_action',request=r[0])
    actual=t['pending']
    try:result=poll_object(server,actor,row,actual)
    except ValueError as exc:
        server.db.execute("UPDATE move_assistance SET status='unconfirmed' WHERE id=?",(pending['assistance'],))
        return dict(outcome='move_help_unconfirmed',assistance=pending['assistance'],reason=str(exc),limits='No completion asserted. Inspect actual current state; historical effects are not undone.')
    if result is None:return
    prior=server.db.execute('SELECT status FROM move_assistance WHERE id=?',(pending['assistance'],)).fetchone()[0]
    receipt=server.db.execute('SELECT seq FROM world_move_intents WHERE id=?',(actual['request'],)).fetchone()
    if not receipt or receipt[0] is None:raise ValueError('Committed learned-move receipt missing')
    status='completed_after_withdrawal' if prior=='withdrawn_in_flight' else 'completed'
    server.db.execute('UPDATE move_assistance SET status=?,result=? WHERE id=?',(status,receipt[0],pending['assistance']))
    emit(server,'character_move_help_completed',actor,pending['assistance'],source_receipt=receipt[0],status=status,limits='Actual shared object action only, not the player intended goal, battle, reward or permanent state guarantee.')
    return dict(result,assistance=pending['assistance'],move_receipt=receipt[0],request_status=status)

def relevant(event,actor):
    return event.get('basis')=='explicit_public_move_assistance' and event.get('character_id')==actor


def recover(server):
    for r in server.db.execute("SELECT * FROM move_assistance WHERE status IN ('offered','awaiting_confirmation')").fetchall():
        if not live(server,r):server.db.execute("UPDATE move_assistance SET status='expired' WHERE id=?",(r[0],))
    # A withdrawn/replaced actor plan must not hold assistance capacity forever.
    # Runtime receipts are authoritative about scheduling, not about the player's goal.
    for key,actor,raw in server.db.execute("SELECT id,actor,terms FROM move_assistance WHERE status IN ('awaiting_confirmation','executing','withdrawn_in_flight')").fetchall():
        execution=json.loads(raw).get('execution')
        if not execution:continue
        receipt=server.db.execute('SELECT status FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',(actor,*execution)).fetchone()
        if receipt and receipt[0]=='blocked':
            server.db.execute("UPDATE move_assistance SET status='unconfirmed' WHERE id=?",(key,))
