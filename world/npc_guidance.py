"""Voluntary player groups following a real, independently directed world actor.

NPC steps use the existing authority executor. Players retain all input; their
presence is client-attested, not proof of an achievement or a save mutation.
"""
import hashlib,json,secrets,time
from . import actor_navigation
from .characters import records
from .guilds import GuildError


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS npc_guidance(id INTEGER PRIMARY KEY,actor TEXT,status TEXT,data TEXT)')


def load(server,key):
    saved=server.db.execute('SELECT actor,status,data FROM npc_guidance WHERE id=?',(key,)).fetchone()
    if not saved:raise ValueError('Unknown guided journey')
    return saved[0],saved[1],json.loads(saved[2])


def store(server,key,status,data):
    server.db.execute('UPDATE npc_guidance SET status=?,data=? WHERE id=?',(status,json.dumps(data,sort_keys=True),key))


def current_plan(server,actor,data):
    return (records(server.module_state).get(actor,{}).get('plan') or {}).get('id')==data.get('plan')


def discover(server):
    return [dict(id=key,actor=actor,status=status,destination=json.loads(raw)['destination'],revision=json.loads(raw)['revision'],text=json.loads(raw)['text'],participants=len(json.loads(raw)['members']))
        for key,actor,status,raw in server.db.execute("SELECT * FROM npc_guidance WHERE status IN ('offered','active') ORDER BY id") if current_plan(server,actor,json.loads(raw)) and time.time()<=json.loads(raw)['expires']]


def member(server,m):
    conn=server.peers.get(m['trainer'])
    return conn if conn and not conn.get('closing') and conn.get('npc_speech_session')==m['session'] else None


def command(server,conn,words):
    from .npc_conversations import nearby
    if words==['leave-guide']:
        with server.db:
            for key,actor,status,raw in server.db.execute("SELECT * FROM npc_guidance WHERE status IN ('offered','active')").fetchall():
                data=json.loads(raw);data['members']=[m for m in data['members'] if member(server,m) is not conn];store(server,key,status,data)
        return ['You left the guided journey. Your game stays under your control.']
    if len(words)!=2 or words[0] not in ('guide','join-guide'):raise GuildError('Use /guild npc guide ID, join-guide ID, or leave-guide.')
    actor=words[1];nearby(server,conn,actor)
    found=server.db.execute("SELECT id FROM npc_guidance WHERE actor=? AND status IN ('offered','active') ORDER BY id DESC LIMIT 1",(actor,)).fetchone()
    if not found:raise GuildError('This character has no current guided journey.')
    key=found[0];_,status,data=load(server,key)
    if time.time()>data['expires'] or not current_plan(server,actor,data):raise GuildError('This invitation has expired or the character chose another plan.')
    if words[0]=='join-guide':
        if not conn.get('character_walk_capable'):raise GuildError('Guided journeys require the matched walking client.')
        session=conn.setdefault('npc_speech_session',secrets.token_hex(16))
        for old in discover(server):
            _,_,saved=load(server,old['id'])
            if old['id']!=key and any(member(server,m) is conn for m in saved['members']):raise GuildError('Leave your existing guided journey first.')
        data['members']=[m for m in data['members'] if member(server,m) is not None]
        if not any(member(server,m) is conn for m in data['members']):
            if len(data['members'])>=4:raise GuildError('This journey already has four participants.')
            data['members'].append(dict(trainer=conn['id'],session=session));data['joined']=True
            with server.db:store(server,key,status,data)
    return [data['text'],f"Destination ({data['destination'][0]},{data['destination'][1]}) in this exact generated place.",
        'Follow the actual NPC on foot; it waits when the group falls behind. No automatic player movement.',
        f"{len(data['members'])}/4 participants. /guild npc leave-guide to leave. Status: {data.get('waiting',status)}."]


def start(server,actor,row,args):
    from .actor_runtime import Pending
    if set(args)!={'revision','x','y','text'} or type(args['text']) is not str or not 1<=len(args['text'])<=60 or any(not 32<=ord(c)<127 for c in args['text']):raise ValueError('Choose a real destination and 1..60 literal public invitation characters')
    current,obj,path=actor_navigation.route(server,actor,[args['x'],args['y']],args['revision'])
    for old_key,raw in server.db.execute("SELECT id,data FROM npc_guidance WHERE actor=? AND status IN ('offered','active')",(actor,)).fetchall():
        old=json.loads(raw)
        if current_plan(server,actor,old) and time.time()<=old['expires']:raise ValueError('Actor already has a guided journey')
        finish(server,old_key,actor,old,'superseded')
    data=dict(plan=current['plan']['id'],revision=args['revision'],destination=path[-1],text=args['text'],members=[],joined=False,expires=time.time()+900,steps=0,active=None,expected=[current['version'],obj['x'],obj['y']],waiting='waiting for voluntary participants')
    key=server.memory.append('character_guidance_offered',dict(character_id=actor,revision=args['revision'],destination=path[-1],text=args['text'],basis='actor_selected_reachable_destination',limits='Invitation only. Players choose whether to follow. No departure, visit or achievement claimed.'))
    server.db.execute("INSERT INTO npc_guidance VALUES(?,?,'offered',?)",(key,actor,json.dumps(data)))
    server.revision=key
    return Pending(dict(journey=key),lambda:None)


def finish(server,key,actor,data,reason):
    result=dict(outcome='guided_destination_reached' if reason=='arrived' else 'guided_journey_ended',reason=reason,revision=data['revision'],destination=data['destination'],completed_steps=data['steps'],
        limits='Committed NPC movement and current client-attested following presence only. No player warp, battle, reward, canonical travel or save change.')
    data['members']=[];data['result']=result;store(server,key,'ended',data)
    server.revision=server.memory.append('character_guidance_ended',dict(character_id=actor,journey=key,**result))
    return result


def halt(server,actor,current,obj,*,reason='End a voluntary guided journey at the actual current tile.'):
    from .character_actions import compile_actions
    action=dict(id=actor,expected_version=current['version'],evidence=current['evidence'],reason=reason,changes={},object=obj)
    context=server.inspect();context['runtime']=dict(previous_source=server.candidate.source)
    context['recalled_history']=dict(events=[dict(json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in current['evidence']])
    source=compile_actions([action],context);digest=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('guidance_stop_'+digest+'.py')
    try:
        with path.open('x') as f:f.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Stop candidate conflict')
    server.deployment=(None,path,None)


def poll(server,actor,row,pending):
    from .region_characters import scoped
    key=pending['journey'];owner,status,data=load(server,key)
    if owner!=actor:raise ValueError('Guided journey belongs to another actor')
    if status=='ended':return data['result']
    obj=next((o for o in server.objects if o['id']==actor),None);current=records(server.module_state).get(actor,{})
    if not obj or current.get('status')!='active' or obj.get('region_revision')!=data['revision']:
        return finish(server,key,actor,data,'actor_or_place_changed')
    if data.get('halting'):
        if server.module_state.get('world_character_controls',{}).get(actor,{}).get('journey'):raise ValueError('Guided movement stop not admitted')
        return finish(server,key,actor,data,data['halting'])
    data['members']=[m for m in data['members'] if member(server,m) is not None and scoped(server,member(server,m),obj,data['revision']) and (member(server,m).get('state') or [])[:2]==[obj['group'],obj['num']]]
    reason='expired' if time.time()>data['expires'] else 'participants_left' if data['joined'] and not data['members'] else None
    if data['active']:
        try:result=actor_navigation.poll(server,actor,row,data['active'])
        except ValueError:return finish(server,key,actor,data,'movement_interrupted')
        if result is None:
            if reason:
                halt(server,actor,current,obj);data['halting']=reason
            store(server,key,status,data);return None
        if [obj['x'],obj['y']]!=[result['x'],result['y']]:return finish(server,key,actor,data,'guide_changed')
        data['steps']+=1;data['active']=None;data['expected']=[current['version'],obj['x'],obj['y']]
    if reason:return finish(server,key,actor,data,reason)
    if data['expected']!=[current['version'],obj['x'],obj['y']]:return finish(server,key,actor,data,'guide_changed')
    def wait(text):
        data['waiting']=text;store(server,key,'active' if data['joined'] else 'offered',data);return None
    if not data['members']:return wait('waiting for voluntary participants')
    followers=[member(server,m) for m in data['members']]
    if any(not p.get('state',[0]*7)[6] or not 0<=time.monotonic()-p.get('state_time',0)<=5 or p.get('character_pending') for p in followers):return wait('waiting for group readiness')
    distances=[abs(obj['x']-p['state'][2])+abs(obj['y']-p['state'][3]) for p in followers]
    if [obj['x'],obj['y']]==data['destination']:
        return finish(server,key,actor,data,'arrived') if max(distances)<=2 else wait('at destination; waiting for group')
    if max(distances)>4:return wait('waiting for group to catch up')
    if any(p.get('character_pending',{}).get('id')==actor for p in server.peers.values() if type(p.get('character_pending')) is dict):return wait('guide is in a player interaction')
    try:_,_,path=actor_navigation.route(server,actor,data['destination'],data['revision'])
    except ValueError:return wait('route currently blocked')
    operation=actor_navigation.stage(server,actor,current,obj,path[:2],data['revision'])
    data['active']=operation.data;data['waiting']='walking';store(server,key,'active',data);operation.dispatch()
    return None
