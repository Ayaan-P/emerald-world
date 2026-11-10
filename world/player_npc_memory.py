"""Explicit public pseudonymous NPC memory, never retroactive player tracking."""
import json,secrets,time,textwrap
from .guilds import GuildError
BASIS='consented_public_player_npc_memory'

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS player_npc_memory(handle TEXT PRIMARY KEY,actor TEXT,trainer TEXT,active INTEGER,consent INTEGER,revision INTEGER,appraisal TEXT,battle TEXT,greeting TEXT)')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS player_npc_memory_active ON player_npc_memory(actor,trainer) WHERE active=1')
    db.execute('CREATE TABLE IF NOT EXISTS player_npc_evidence(handle TEXT,seq INTEGER,PRIMARY KEY(handle,seq))')

def current(server,trainer,actor):
    setup(server.db)
    r=server.db.execute('SELECT handle,consent,revision,appraisal,battle,greeting FROM player_npc_memory WHERE trainer=? AND actor=? AND active=1',(trainer,actor)).fetchone()
    return dict(zip(('handle','consent','revision','appraisal','battle','greeting'),r)) if r else None

def emit(server,event,actor,handle,**data):
    seq=server.memory.append(event,dict(character_id=actor,visitor=handle,basis=BASIS,**data));server.revision=seq;return seq

def command(server,conn,words):
    return [chunk for line in _command(server,conn,words) for chunk in textwrap.wrap(line,110)]

def _command(server,conn,words):
    from .npc_conversations import nearby
    if server.peers.get(conn.get('id')) is not conn or conn.get('closing'):raise GuildError('Authenticated player required')
    if len(words)<2:raise GuildError('Use /guild npc remember-public ID, memory ID, or stop-remembering ID')
    operation,actor=words[:2]
    if operation=='memory' and len(words)==2:
        row=current(server,conn['id'],actor)
        return ([actor+': not remembering you.'] if not row else [actor+': public visitor '+row['handle'],
            'Subjective appraisal: '+(row['appraisal'] or 'None yet.'),'Optional challenge: '+row['battle'],
            'Stop future linking: /guild npc stop-remembering '+actor+'. Published history remains.'])
    if operation=='stop-remembering' and len(words)==2:
        row=current(server,conn['id'],actor);conn.pop('npc_memory_offer',None)
        if not row:return ['No active remembering consent for this NPC.']
        with server.db:
            server.db.execute("UPDATE player_npc_memory SET active=0,trainer='',appraisal='',battle='open',greeting='' WHERE handle=?",(row['handle'],))
            emit(server,'player_npc_memory_revoked',actor,row['handle'],limits='Future linking and personalized offers stopped. Already public history remains; accepted battles are not cancelled. No player identity published.')
        return ['Stopped future remembering and personalized offers. Published history remains. An accepted battle is unchanged.']
    if operation!='remember-public':raise GuildError('Unknown remembering command')
    character,_=nearby(server,conn,actor)
    existing=current(server,conn['id'],actor)
    if existing:return ['Already remembering under visitor '+existing['handle']+'. Use /guild npc memory '+actor]
    if len(words)==2:
        token=secrets.token_hex(6);conn['npc_memory_offer']=dict(actor=actor,token=token,version=character['version'],until=time.monotonic()+60)
        return ['Remembering is OPTIONAL. This NPC may personalize dialogue and accept or decline its optional battles.',
            'Future direct public speech and battle reports link to a random visitor handle for this NPC across reconnects.',
            'Linked history and fictional NPC appraisals are PUBLIC to world players/agents, not private. Your login name is not added.',
            'Others may still recognize you from speech or context. Do not enter personal information.',
            'No earlier speech is linked. Revoking stops future links, not published history or already accepted battles.',
            '/guild npc remember-public '+actor+' '+token+' yes']
    pending=conn.pop('npc_memory_offer',None)
    if (len(words)!=4 or words[3]!='yes' or not pending or pending['actor']!=actor or words[2]!=pending['token']
        or pending['version']!=character['version'] or time.monotonic()>pending['until']):raise GuildError('Consent offer changed or expired. Request it again beside the NPC.')
    if server.db.execute('SELECT count(*) FROM player_npc_memory WHERE actor=? AND active=1',(actor,)).fetchone()[0]>=32 or server.db.execute('SELECT count(*) FROM player_npc_memory WHERE trainer=? AND active=1',(conn['id'],)).fetchone()[0]>=16:
        raise GuildError('Active remembering capacity reached; stop an existing relationship first.')
    handle=secrets.token_hex(12)
    with server.db:
        seq=emit(server,'player_npc_memory_consented',actor,handle,limits='Explicit future public pseudonymous linkage for this NPC only. Not friendship, agreement with speech, or consent to battle.')
        server.db.execute('INSERT INTO player_npc_memory VALUES(?,?,?,1,?,?,?, ?,?)',(handle,actor,conn['id'],seq,seq,'','open',''))
    return ['This NPC may now remember future public interactions as visitor '+handle+'. Use /guild npc stop-remembering '+actor+' to stop.']

def speech(server,conn,actor,source):
    row=current(server,conn['id'],actor)
    if not row:return
    seq=emit(server,'remembered_player_speech',actor,row['handle'],speech=source,limits='Post-consent direct public speech. Words are the player\'s claims, not verified acts; no friendship inferred.')
    server.db.execute('INSERT INTO player_npc_evidence VALUES(?,?)',(row['handle'],seq))

def appraise(server,actor,row,args):
    from .characters import records
    if set(args)!={'visitor','evidence','text','battle','greeting'} or type(args['visitor']) is not str or type(args['evidence']) is not int or args['battle'] not in ('open','invite','decline'):raise ValueError('Use a currently consented visitor, exact evidence, subjective text, open/invite/decline and greeting')
    for key,limit in (('text',160),('greeting',28)):
        if type(args[key]) is not str or not 1<=len(args[key])<=limit or any(not 32<=ord(c)<127 for c in args[key]):raise ValueError('Use bounded literal fictional appraisal and native greeting')
    c=records(server.module_state).get(actor)
    if not c or c['status']!='active':raise ValueError('Active generated character required')
    saved=server.db.execute('SELECT consent FROM player_npc_memory WHERE handle=? AND actor=? AND active=1',(args['visitor'],actor)).fetchone()
    if not saved or args['evidence']<=saved[0] or not server.db.execute('SELECT 1 FROM player_npc_evidence WHERE handle=? AND seq=?',(args['visitor'],args['evidence'])).fetchone():raise ValueError('Appraise only own currently consented visitor from exact subsequent linked evidence')
    seq=emit(server,'character_player_appraisal',actor,args['visitor'],source_receipt=args['evidence'],text=args['text'],battle=args['battle'],greeting=args['greeting'],interpretation='subjective_fictional_npc_interpretation_not_verified_fact',limits='Personalized optional dynamic challenge policy, not stock-story access, automatic battle, relationship score, reward or growth. Current policy checked on request; frozen battles unchanged.')
    server.db.execute('UPDATE player_npc_memory SET revision=?,appraisal=?,battle=?,greeting=? WHERE handle=?',(seq,args['text'],args['battle'],args['greeting'],args['visitor']))
    return dict(outcome='player_appraisal_committed',visitor=args['visitor'],receipt=seq,battle=args['battle'])

def caption(server,conn,obj):
    if conn.get('campaign_run'):return obj['text']
    row=current(server,conn.get('id'),obj['id'])
    return row['greeting'] if row and row['greeting'] else obj['text']

def bind(server,conn,frozen):
    if frozen.get('campaign_binding'):return # Explicit campaign enrollment retains its existing rules.
    row=current(server,conn['id'],frozen['id'])
    if not row:return
    if row['battle']=='decline':raise ValueError('This NPC currently declines this optional challenge. Ask again later or stop remembering.')
    frozen['memory_binding']=dict(handle=row['handle'],revision=row['revision'],consent=row['consent'])

def report(server,conn,pending,outcome):
    bound=pending.get('memory_binding');row=current(server,conn['id'],pending['id'])
    # No later consent may identify an earlier or previously revoked battle.
    if not bound or not row or row['handle']!=bound['handle'] or row['consent']!=bound['consent']:return
    seq=emit(server,'remembered_character_battle_report',pending['id'],row['handle'],challenge_sequence=pending['seq'],character_version=pending['version'],invitation_revision=bound['revision'],outcome=outcome,provenance='authenticated_client_report_not_verified_outcome',limits='Result reported for an exactly frozen optional challenge, not a verified victory, capture, earned trust or growth.')
    server.db.execute('INSERT INTO player_npc_evidence VALUES(?,?)',(row['handle'],seq))

def catalog(server):
    setup(server.db)
    return [dict(visitor=h,actor=a,consent=c,revision=r,appraisal=t,battle=b,greeting=g,evidence=[x[0] for x in server.db.execute('SELECT seq FROM player_npc_evidence WHERE handle=? ORDER BY seq DESC LIMIT 8',(h,))]) for h,a,c,r,t,b,g in server.db.execute('SELECT handle,actor,consent,revision,appraisal,battle,greeting FROM player_npc_memory WHERE active=1 ORDER BY actor,handle')]

def relevant(event,actor):
    return event.get('event') in ('remembered_player_speech','remembered_character_battle_report') and event.get('character_id')==actor and event.get('basis')==BASIS
