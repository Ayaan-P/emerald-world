"""Bounded opt-in authors for newly admitted, world-owned NPCs."""
import json
import time
from .character_reactions import actors, cancel_queued

MAX_TURNS = 8
PERIOD_HOURS = 24

def setup(queue):
    queue.db.execute('CREATE TABLE IF NOT EXISTS population_admissions(world TEXT,id TEXT,birth INTEGER,creator TEXT,receipt INTEGER,status TEXT,PRIMARY KEY(world,id))')
    queue.db.execute('CREATE TABLE IF NOT EXISTS population_agents(id TEXT PRIMARY KEY,world TEXT,creation INTEGER,started REAL,status TEXT,attempts INTEGER NOT NULL DEFAULT 0)')

def reserve(queue, actor):
    managed=queue.db.execute('SELECT status,attempts FROM population_agents WHERE id=?',(actor,)).fetchone()
    if managed is None:return True
    if managed['status']!='active':return False
    settings=policy(queue);now=time.time()
    start=queue.db.execute('SELECT started FROM population_agents WHERE id=?',(actor,)).fetchone()[0]
    if now>=start+settings.get('period_hours',PERIOD_HOURS)*3600:
        queue.db.execute('UPDATE population_agents SET attempts=0,started=? WHERE id=?',(now,actor))
        attempts=0
    else:attempts=managed['attempts']
    if attempts>=settings.get('turn_limit',MAX_TURNS):return False
    queue.db.execute('UPDATE population_agents SET attempts=attempts+1 WHERE id=?',(actor,))
    return True

def policy(queue):
    row=queue.db.execute("SELECT value FROM metadata WHERE key='population_agents'").fetchone()
    return json.loads(row[0]) if row else dict(enabled=False)

def configure(queue, inspection, enabled, *, turn_limit=MAX_TURNS, period_hours=PERIOD_HOURS):
    if type(turn_limit) is not int or not 1<=turn_limit<=64 or type(period_hours) is not int or not 1<=period_hours<=168:
        raise ValueError('Use 1..64 turns per 1..168 hours')
    memory=inspection.get('data',inspection).get('world_memory',{})
    if inspection.get('ok') is not True or type(enabled) is not bool or not memory.get('world_id') or type(memory.get('through')) is not int:
        raise ValueError('Inspected world and explicit lifecycle setting required')
    with queue.db:
        queue.db.execute('BEGIN IMMEDIATE')
        prior=policy(queue)
        cursor=prior['cursor'] if prior.get('enabled') and enabled and prior.get('world')==memory['world_id'] else memory['through']
        if not enabled:
            queue.db.execute("UPDATE population_admissions SET status='cancelled' WHERE status IN ('unclaimed','waiting')")
            for actor, in queue.db.execute("SELECT id FROM population_agents WHERE status='active'").fetchall():
                queue.db.execute('DELETE FROM character_reactions WHERE id=?',(actor,));cancel_queued(queue,actor)
            queue.db.execute("UPDATE population_agents SET status='stopped' WHERE status='active'")
        queue.db.execute("INSERT OR REPLACE INTO metadata VALUES('population_agents',?)",
                         (json.dumps(dict(enabled=enabled,world=memory['world_id'],cursor=cursor,turn_limit=turn_limit,period_hours=period_hours)),))

def created(event):
    if (event.get('event')!='actor_tool_result' or event.get('source')!='authority_capability_runtime'
            or event.get('status')!='succeeded' or type(event.get('result')) is not dict):return []
    result=event['result'];tool=event.get('tool');members=[]
    if tool in ('world.populate','world.populate_native') and result.get('outcome')=='population_admitted':members=[result]
    elif tool=='world.populate_group' and result.get('outcome')=='population_group_admitted':
        members=result.get('members',[])
        if type(members) is not list or not 2<=len(members)<=4:return []
    elif tool=='world.build_adventure' and result.get('outcome')=='procedural_adventure_published':
        ids=result.get('trainers',[])
        if type(ids) is not list or not 0<=len(ids)<=4 or any(type(i) is not str for i in ids) or len(set(ids))!=len(ids):return []
        return ids
    return [m['object'] for m in members if type(m) is dict and m.get('kind')=='character' and type(m.get('object')) is str]


def creation(event, identity):
    return identity in created(event)


def admit_waiting(queue,p,cast,data):
    queued=[]
    for pending in queue.db.execute("SELECT * FROM population_admissions WHERE world=? AND status='waiting' ORDER BY receipt,id",(p['world'],)).fetchall():
        identity=pending['id'];child=cast.get(identity,{})
        if (child.get('status')!='active' or child.get('canonical')
                or not queue.db.execute('SELECT 1 FROM character_reactions WHERE id=?',(pending['creator'],)).fetchone()
                or queue.db.execute('SELECT 1 FROM population_agents WHERE id=?',(identity,)).fetchone()
                or queue.db.execute('SELECT 1 FROM character_reactions WHERE id=?',(identity,)).fetchone()):
            queue.db.execute("UPDATE population_admissions SET status='cancelled' WHERE world=? AND id=?",(p['world'],identity));continue
        from .npc_goal_reviews import unfinished
        if unfinished(data,identity,child):continue
        if queue.db.execute('SELECT count(*) FROM character_reactions').fetchone()[0]>=8:break
        purpose='Pursue your own goals and relationships through discovered capabilities and actual results. Decide independently; wait when unsupported. Creation is not evidence of prior experiences.'
        now=time.time();key='population-agent-'+str(pending['receipt'])+'-'+identity
        reaction=dict(id=identity,world_id=p['world'],expected_version=child['version'],canonical=False,evidence=pending['receipt'],purpose=purpose)
        queue.db.execute('INSERT INTO population_agents(id,world,creation,started,status) VALUES(?,?,?,?,?)',(identity,p['world'],pending['receipt'],now,'active'))
        queue.db.execute('INSERT INTO character_reactions VALUES(?,?,?,?)',(identity,purpose,p['world'],pending['receipt']))
        queue.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
            (key,identity,'Choose your own first supported plan from your real location and goals, or wait. Do not copy the creator plan or claim past activity.','character','queued',now,json.dumps(reaction)))
        queue.db.execute("UPDATE population_admissions SET status='admitted' WHERE world=? AND id=?",(p['world'],identity));queued.append(key)
    return queued

def observe(queue, inspection, fetch):
    p=policy(queue)
    if not p.get('enabled'):return []
    data=inspection.get('data',inspection);memory=data.get('world_memory',{})
    if p['world']!=memory.get('world_id'):raise ValueError('Population policy belongs to another world')
    page=fetch(dict(command='world_history',after=p['cursor'],through=memory['through'],limit=32))
    if page.get('ok') is not True or page.get('world_id')!=p['world'] or page.get('through')!=memory['through'] or not p['cursor']<=page.get('cursor',-1)<=memory['through']:
        raise ValueError('Population history does not match inspection')
    cast=actors(data.get('state',{}));queued=[]
    with queue.db:
        queue.db.execute('BEGIN IMMEDIATE')
        if policy(queue)!=p:return []
        # Migrate only old lifetime-budget pauses, never explicit host stops.
        for managed in queue.db.execute("SELECT * FROM population_agents WHERE status='budget_reached'").fetchall():
            child=cast.get(managed['id'],{});now=time.time()
            if (child.get('status')!='active' or now<managed['started']+p.get('period_hours',PERIOD_HOURS)*3600
                or queue.db.execute('SELECT count(*) FROM character_reactions').fetchone()[0]>=8):continue
            identity=managed['id'];purpose='Pursue your own goals through actual supported actions and receipts.'
            queue.db.execute("UPDATE population_agents SET status='active',attempts=0,started=? WHERE id=?",(now,identity))
            queue.db.execute('INSERT OR IGNORE INTO character_reactions VALUES(?,?,?,?)',(identity,purpose,p['world'],memory['through']))
            packet=dict(id=identity,world_id=p['world'],expected_version=child['version'],canonical=False,evidence=managed['creation'],purpose=purpose)
            key='population-resume-'+str(managed['creation'])+'-'+identity
            if not queue.db.execute("SELECT 1 FROM requests WHERE kind='character' AND player=? AND status IN ('queued','running')",(identity,)).fetchone():
                queue.db.execute('INSERT OR IGNORE INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
                    (key,identity,'Resume independent planning from current state. A budget pause is not fictional activity or new experience.','character','queued',now,json.dumps(packet)))
        for managed in queue.db.execute("SELECT * FROM population_agents WHERE status='active'").fetchall():
            actor=managed['id'];sub=queue.db.execute('SELECT 1 FROM character_reactions WHERE id=?',(actor,)).fetchone()
            from .npc_absence import retained
            absent=cast.get(actor,{}).get('status')=='away' and retained(data,actor)
            reason='stopped' if not sub else 'inactive' if cast.get(actor,{}).get('status')!='active' and not absent else None
            if reason:
                queue.db.execute('DELETE FROM character_reactions WHERE id=?',(actor,));cancel_queued(queue,actor)
                queue.db.execute('UPDATE population_agents SET status=? WHERE id=?',(reason,actor))
        previous=p['cursor']
        for event in page.get('events',[]):
            if type(event.get('seq')) is not int or not previous<event['seq']<=page['cursor']:raise ValueError('Invalid population event order')
            previous=event['seq']
            # Capture actual first admission after opt-in, separately from a later
            # resumable publication receipt. A repeat cannot awaken old actors.
            child=event.get('after');identity=event.get('character_id')
            if (event.get('event')=='character_changed' and event.get('before','missing') is None
                    and type(identity) is str and type(child) is dict and child.get('version')==1
                    and child.get('status')=='active' and child.get('object_id')==identity
                    and not cast.get(identity,{}).get('canonical')):
                queue.db.execute("INSERT OR IGNORE INTO population_admissions VALUES(?,?,?,NULL,NULL,'unclaimed')",(p['world'],identity,event['seq']))
            for identity in created(event):
                birth=queue.db.execute("SELECT birth,status FROM population_admissions WHERE world=? AND id=?",(p['world'],identity)).fetchone()
                if not birth or birth['status']!='unclaimed' or birth['birth']>=event['seq']:continue
                creator=event.get('character_id')
                followed=queue.db.execute('SELECT 1 FROM character_reactions WHERE id=?',(creator,)).fetchone()
                queue.db.execute('UPDATE population_admissions SET creator=?,receipt=?,status=? WHERE world=? AND id=?',
                    (creator,event['seq'],'waiting' if followed else 'cancelled',p['world'],identity))
        queued.extend(admit_waiting(queue,p,cast,data))
        p['cursor']=page['cursor']
        queue.db.execute("UPDATE metadata SET value=? WHERE key='population_agents'",(json.dumps(p),))
    return queued
