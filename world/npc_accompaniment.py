"""Optional session-bound walking companions using real generated-map journeys.

No follower save flags, warps, player control, battles or canonical actor moves.
"""
import json,secrets,time
from .guilds import GuildError
from .characters import records
from . import actor_navigation


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS npc_accompaniment(request INTEGER PRIMARY KEY,actor TEXT,trainer TEXT,session TEXT,revision TEXT,status TEXT,data TEXT)')


def peer(server,saved):
    actor,trainer,session,revision,status,raw=saved
    conn=server.peers.get(trainer)
    if not conn or conn.get('closing') or conn.get('npc_speech_session')!=session:return None
    return conn


def command(server,conn,words):
    from .npc_conversations import nearby
    if words==['walk-stop']:
        with server.db:
            server.db.execute("UPDATE npc_accompaniment SET status='stopped' WHERE trainer=? AND session=? AND status IN ('offered','active')",(conn['id'],conn.get('npc_speech_session','')))
        return ['Walking request stopped. An admitted movement is safely settled at its next authority update.']
    if len(words)!=2 or words[0]!='walk-with':raise GuildError('Use /guild npc walk-with ID, or /guild npc walk-stop.')
    actor=words[1];character,obj=nearby(server,conn,actor)
    if not obj.get('region_revision') or not conn.get('character_walk_capable'):
        raise GuildError('Walking companions need a matched movement client in a generated place.')
    session=conn.setdefault('npc_speech_session',secrets.token_hex(16))
    # Abandoned offers do not permanently lock an actor after a disconnect.
    for key,*saved in server.db.execute("SELECT * FROM npc_accompaniment WHERE status IN ('offered','active')").fetchall():
        if peer(server,saved) is None:
            with server.db:server.db.execute("UPDATE npc_accompaniment SET status='stopped' WHERE request=?",(key,))
    if server.db.execute("SELECT 1 FROM npc_accompaniment WHERE (actor=? OR (trainer=? AND session=?)) AND status IN ('offered','active')",(actor,conn['id'],session)).fetchone():
        raise GuildError('Resolve the existing walking request first.')
    with server.db:
        seq=server.memory.append('player_requested_accompaniment',dict(character_id=actor,character_version=character['version'],revision=obj['region_revision'],
            basis='explicit_session_walking_request',limits='Optional NPC choice. Public request to walk together in this generated place; no movement, battle or player save change yet.'))
        server.db.execute('INSERT INTO npc_accompaniment VALUES(?,?,?,?,?,?,?)',(seq,actor,conn['id'],session,obj['region_revision'],'offered','{}'))
    server.revision=seq
    return ['Walking invitation sent. The character decides whether to join.', 'Stay in this generated place. /guild npc walk-stop ends the invitation or accompaniment.']


def inbox(server):
    return [dict(request=k,actor=a,revision=r,status=st) for k,a,r,st in server.db.execute("SELECT request,actor,revision,status FROM npc_accompaniment WHERE status IN ('offered','active') ORDER BY request")]


def load(server,key):
    saved=server.db.execute('SELECT actor,trainer,session,revision,status,data FROM npc_accompaniment WHERE request=?',(key,)).fetchone()
    if not saved:raise ValueError('Unknown walking request')
    return saved


def start(server,actor,row,args):
    from .actor_runtime import Pending
    from .npc_conversations import nearby
    if set(args)!={'request'} or type(args['request']) is not int:raise ValueError('Choose an actual player walking invitation')
    saved=load(server,args['request']);conn=peer(server,saved)
    if saved[0]!=actor or saved[4]!='offered' or conn is None:raise ValueError('Walking invitation no longer available')
    try:current,obj=nearby(server,conn,actor)
    except GuildError as exc:raise ValueError(str(exc)) from None
    if obj.get('region_revision')!=saved[3]:raise ValueError('Invitation place changed')
    data=dict(active=None,steps=0,expected=dict(version=current['version'],x=obj['x'],y=obj['y']))
    server.db.execute("UPDATE npc_accompaniment SET status='active',data=? WHERE request=?",(json.dumps(data),args['request']))
    server.revision=server.memory.append('character_accompaniment_accepted',dict(character_id=actor,request=args['request'],revision=saved[3],basis='explicit_session_walking_request',limits='NPC agreed to attempt actual walking; no arrival, player movement or battle claimed.'))
    return Pending(dict(request=args['request']),lambda:None)


def store(server,key,data):
    server.db.execute('UPDATE npc_accompaniment SET data=? WHERE request=?',(json.dumps(data,sort_keys=True),key))


def end(server,key,reason,data):
    server.db.execute("UPDATE npc_accompaniment SET status='ended',data=? WHERE request=?",(json.dumps(data,sort_keys=True),key))
    return dict(outcome='accompaniment_ended',request=key,reason=reason,completed_steps=data['steps'],limits='Actual committed NPC steps only. No warp, partner battle, player-save change or rendered playtest inferred.')


def poll(server,actor,row,pending):
    from .region_characters import scoped
    key=pending['request'];saved=load(server,key);data=json.loads(saved[5]);conn=peer(server,saved)
    obj=next((o for o in server.objects if o['id']==actor),None);current=records(server.module_state).get(actor,{})
    if not obj or current.get('status')!='active':return end(server,key,'actor_unavailable',data)
    state=conn.get('state') if conn else None
    stopped=(saved[4]!='active' or conn is None or obj.get('region_revision')!=saved[3]
             or not state or state[:2]!=[obj['group'],obj['num']]
             or not scoped(server,conn,obj,saved[3]))
    # Only a single cardinal step is ever admitted at once. On cancellation or
    # disconnect it may finish/yield under normal collision rules, but no new
    # destination or teleport is issued. Explicit halt removes even a blocked leg.
    if data.get('halting'):
        control=server.module_state.get('world_character_controls',{}).get(actor,{})
        if control.get('journey'):raise ValueError('Accompaniment stop was not admitted; no new motion issued')
        return end(server,key,'stopped',data)
    if stopped and data['active']:
        if server.db.execute('SELECT 1 FROM character_journey_receipts WHERE actor=? AND journey=?',(actor,data['active']['journey'])).fetchone():
            data['steps']+=1
        from .character_actions import compile_actions
        import hashlib
        action=dict(id=actor,expected_version=current['version'],evidence=current['evidence'],reason='Stop optional accompaniment at the actual current tile.',changes={},object=obj)
        context=server.inspect();context['runtime']=dict(previous_source=server.candidate.source)
        context['recalled_history']=dict(events=[dict(json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in current['evidence']])
        source=compile_actions([action],context);digest=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('accompany_stop_'+digest+'.py')
        try:
            with path.open('x') as f:f.write(source)
        except FileExistsError:
            if path.is_symlink() or path.read_text()!=source:raise ValueError('Stop candidate conflict')
        data['halting']=True;store(server,key,data);server.deployment=(None,path,None)
        return None
    if data['active']:
        result=actor_navigation.poll(server,actor,row,data['active'])
        if result is None:return None
        if (obj.get('region_revision'),obj['x'],obj['y'])!=(result['revision'],result['x'],result['y']):raise ValueError('Companion moved outside the admitted step')
        data['steps']+=1;data['active']=None;data['expected']=dict(version=current['version'],x=obj['x'],y=obj['y']);store(server,key,data)
    if stopped:return end(server,key,'player_left_or_stopped',data)
    if data['expected']!=dict(version=current['version'],x=obj['x'],y=obj['y']):raise ValueError('Companion changed outside accompaniment; inspect and replan')
    # Field menus and battles pause following, not teleport the NPC or abort a battle.
    if not state[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or conn.get('character_pending'):return None
    if any(p.get('character_pending',{}).get('id')==actor for p in server.peers.values() if type(p.get('character_pending')) is dict):return None
    if abs(obj['x']-state[2])+abs(obj['y']-state[3])<=2:return None
    paths=[]
    for x,y in ((state[2]-1,state[3]),(state[2]+1,state[3]),(state[2],state[3]-1),(state[2],state[3]+1)):
        try:paths.append(actor_navigation.route(server,actor,[x,y],saved[3])[2])
        except ValueError:continue
    if not paths:return None # Actual occupancy/geometry can make the leader unreachable.
    path=min(paths,key=lambda p:(len(p),p[-1]))[:2]
    operation=actor_navigation.stage(server,actor,current,obj,path,saved[3])
    data['active']=operation.data;store(server,key,data);operation.dispatch()
    return None


def relevant(event,actor):
    return event.get('event')=='player_requested_accompaniment' and event.get('character_id')==actor and event.get('basis')=='explicit_session_walking_request'
