"""Temporary rendered absence, with no inferred off-screen activity."""
import copy,hashlib,json,time,textwrap

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS npc_absence(id TEXT PRIMARY KEY,actor TEXT,data TEXT)')

def save(server,key,data):server.db.execute('UPDATE npc_absence SET data=? WHERE id=?',(json.dumps(data,sort_keys=True),key))

def available(server,revision):
    return bool(server.db.execute('SELECT 1 FROM world_region_revisions WHERE revision=?',(revision,)).fetchone() or (server.shared_cave and server.shared_cave.identity==revision))

def battle(server,actor):
    return any(isinstance(p.get('character_pending'),dict) and p['character_pending'].get('id')==actor for p in server.peers.values())

def guarded(server,actor):
    setup(server.db)
    for raw, in server.db.execute('SELECT data FROM npc_absence WHERE actor=?',(actor,)):
        d=json.loads(raw)
        if d['phase'] in ('departing','waiting','returning'):
            plan=d['plan'];r=server.db.execute('SELECT status FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',(actor,plan,d['step'])).fetchone()
            if r==('pending',):return True
    return False

def validate_objects(server,objects,state):
    setup(server.db)
    for actor,raw in server.db.execute('SELECT actor,data FROM npc_absence'):
        d=json.loads(raw);new=next((o for o in objects if o['id']==actor),None)
        if d['phase']=='departing' and new is None and battle(server,actor):raise ValueError('Absence cannot remove a trainer with a frozen battle')
        if d['phase']=='returning' and new is not None:
            if new!=d['object'] or not available(server,new['region_revision']):raise ValueError('Retained return position or current revision changed')
            for p in server.peers.values():
                if not p.get('closing') and p.get('state') and server._region_scope(p)==new['region_revision'] and p['state'][2:4]==[new['x'],new['y']]:raise ValueError('Returning character overlaps a player, including menus')

def stage(server,actor,current,obj,status):
    from .character_actions import compile_actions
    from .actor_runtime import Pending
    action=dict(id=actor,expected_version=current['version'],evidence=current['evidence'],reason='Change availability at the retained place; no off-screen experience claimed.',changes=dict(status=status),object=obj)
    context=server.inspect();context['runtime']=dict(previous_source=server.candidate.source)
    context['recalled_history']=dict(events=[dict(json.loads(server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(seq,)).fetchone()[0]),seq=seq) for seq in current['evidence']])
    source=compile_actions([action],context);sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('absence_'+sha+'.py')
    try:
        with path.open('x') as f:f.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Absence source conflict')
    return Pending({},lambda:setattr(server,'deployment',(None,path,None)))

def start(server,actor,row,args):
    from .characters import records
    from .character_walks import walking
    from .actor_runtime import Pending
    setup(server.db)
    if set(args)!={'seconds'} or type(args['seconds']) is not int or not 60<=args['seconds']<=86400:raise ValueError('Choose 60..86400 seconds of absence, not simulated activity')
    c=records(server.module_state).get(actor);obj=next((o for o in server.objects if o['id']==actor),None)
    if not c or c['status']!='active' or not obj or not obj.get('region_revision') or c.get('offer') or walking(server.module_state,actor) or battle(server,actor):raise ValueError('An idle generated-place character without a frozen battle is required')
    if not available(server,obj['region_revision']):raise ValueError('Retained place is no longer current')
    if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('World is busy')
    execution=server.actor_tool_execution
    if not execution or execution[0]!=actor:raise ValueError('Durable own capability execution required')
    key=hashlib.sha256(json.dumps([actor,execution[2]['id'],execution[3]['id']]).encode()).hexdigest()
    operation=stage(server,actor,c,None,'away')
    data=dict(phase='departing',original=c,object=obj,seconds=args['seconds'],plan=execution[2]['id'],step=execution[3]['id'],reason='')
    server.db.execute('INSERT INTO npc_absence VALUES(?,?,?)',(key,actor,json.dumps(data,sort_keys=True)))
    return Pending(dict(absence=key),operation.dispatch)

def poll(server,actor,row,pending):
    from .characters import records
    key=pending['absence'];r=server.db.execute('SELECT actor,data FROM npc_absence WHERE id=?',(key,)).fetchone()
    if not r or r[0]!=actor:raise ValueError('Unknown own absence')
    d=json.loads(r[1]);c=records(server.module_state).get(actor);obj=next((o for o in server.objects if o['id']==actor),None)
    original=d['original'];away=dict(original,status='away',version=original['version']+1,reason='Change availability at the retained place; no off-screen experience claimed.')
    if away.get('offer') is None:away.pop('offer',None)
    # The dispatcher uses the unchanged original evidence and retains all other fields.
    if d['phase']=='departing':
        if c!=away or obj is not None:raise ValueError('Absence departure was not admitted')
        d.update(phase='waiting',due=time.time()+d['seconds'],last=time.time());save(server,key,d);return None
    returned=dict(away,status='active',version=away['version']+1)
    if d['phase']=='returning' and c==returned and obj==d['object']:
        d['phase']='returned';save(server,key,d)
        return dict(outcome='character_returned',absence=key,character_id=actor,version=c['version'],revision=obj['region_revision'],x=obj['x'],y=obj['y'],limits='Actual removal and reintroduction at the retained place. No travel, rest benefit, healing, training or off-screen activity inferred.')
    if c!=away or obj is not None:raise ValueError('Absent character changed outside this lifecycle; no automatic restoration')
    if d['phase']=='returning':d['phase']='waiting' # Admission rejected or process stopped before dispatch; revalidate, never assume return.
    now=time.time()
    if now<d['last']:d['due']+=now-d['last']
    d['last']=now
    if now<d['due']:save(server,key,d);return None
    target=d['object']
    try:
        if not available(server,target['region_revision']):raise ValueError('Original place revision is no longer current; no silent relocation')
        if battle(server,actor):raise ValueError('Frozen battle must settle')
        if any(o.get('region_revision')==target['region_revision'] and (o['x'],o['y'])==(target['x'],target['y']) for o in server.objects):raise ValueError('Return tile occupied by object')
        if any(not p.get('closing') and p.get('state') and server._region_scope(p)==target['region_revision'] and p['state'][2:4]==[target['x'],target['y']] for p in server.peers.values()):raise ValueError('Return tile occupied by player')
        from .region_characters import validate_region_objects
        future=copy.deepcopy(server.module_state);future['world_characters'][actor]=returned
        validate_region_objects(server,server.objects+[target],future)
        operation=stage(server,actor,c,target,'active')
    except ValueError as exc:
        d['reason']=str(exc)[:180];save(server,key,d);return None
    d.update(phase='returning',reason='');save(server,key,d);operation.dispatch();return None

def retained(data,actor):
    """Only an actual pending absence preserves an existing host enrollment."""
    for p in data.get('actor_runtime',{}).get('plans',[]):
        if p['actor']!=actor:continue
        steps={s['id']:s for s in p['plan']['steps']}
        if any(r['status']=='pending' and steps.get(r['step'],{}).get('tool')=='world.take_leave' and type(r.get('result',{}).get('absence')) is str for r in p['receipts']):return True
    return False


def catalog(server):
    setup(server.db)
    result=[]
    for key,actor,raw in server.db.execute('SELECT id,actor,data FROM npc_absence ORDER BY rowid DESC'):
        d=json.loads(raw)
        if d['phase']=='returned':continue
        pending=server.db.execute('SELECT status FROM actor_tool_receipts WHERE actor=? AND plan=? AND step=?',(actor,d['plan'],d['step'])).fetchone()
        result.append(dict(id=key,actor=actor,status=d['phase'] if pending==('pending',) else 'interrupted',revision=d['object']['region_revision'],return_tile=[d['object']['x'],d['object']['y']],reason=d.get('reason',''),limits='Return may wait for safe occupancy and unchanged place. No off-screen activity.'))
    return result[:32]

def command(server,words):
    if len(words)!=2:return ['Use /guild npc availability ID for a known character.']
    rows=[r for r in catalog(server) if r['actor']==words[1]]
    if not rows:return ['No outstanding temporary absence for this character.']
    r=rows[0]
    return [part for line in [r['actor']+': '+r['status'],r['reason'] or 'Waiting for the chosen interval and safe original place. No off-screen activity claimed.'] for part in textwrap.wrap(line,110)]
