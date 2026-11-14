"""Agent-chosen one-shot reconsideration, never clock-invented experience."""
import json,re,time,uuid

def validate(review,goals):
    if review is None:return
    if (type(review) is not dict or set(review)!={'id','goal','after_seconds'}
        or type(review['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',review['id'])
        or review['goal'] not in goals or type(review['after_seconds']) is not int or not 60<=review['after_seconds']<=86400):
        raise ValueError('Goal review needs a unique id, an exact current goal and 60..86400 seconds')

def setup(queue):
    queue.db.execute('CREATE TABLE IF NOT EXISTS npc_goal_reviews(world TEXT,actor TEXT,id TEXT,definition TEXT,due REAL,last_seen REAL,status TEXT,PRIMARY KEY(world,actor,id))')
    queue.db.execute('CREATE TABLE IF NOT EXISTS npc_goal_review_budget(world TEXT,actor TEXT,day INTEGER,attempts INTEGER,PRIMARY KEY(world,actor))')

def unfinished(data,actor,character):
    from .character_walks import walking
    if walking(data.get('state',{}),actor):return True
    plan=character.get('plan')
    if not plan:return False
    found=next((p for p in data.get('actor_runtime',{}).get('plans',[]) if p['actor']==actor and p['plan']['id']==plan['id']),None)
    if not found:return True
    receipts={r['step']:r['status'] for r in found['receipts']}
    if 'pending' in receipts.values():return True
    # A blocked plan will never start its unexecuted dependents; it is safe to reconsider.
    if 'blocked' in receipts.values():return False
    steps=(found.get('expanded_method') or plan)['steps']
    return any(receipts.get(s['id']) not in ('succeeded','skipped') for s in steps)

def enqueue(queue,sub,character,data,*,defer=False):
    if character.get('canonical'):return None
    review=character.get('goal_review');now=time.time();key=(sub['world'],sub['id'])
    if review is None or character.get('status')!='active':
        queue.db.execute("UPDATE npc_goal_reviews SET status='cancelled' WHERE world=? AND actor=? AND status='waiting'",key)
        return None
    validate(review,character['goals']);encoded=json.dumps(review,sort_keys=True)
    queue.db.execute("UPDATE npc_goal_reviews SET status='cancelled' WHERE world=? AND actor=? AND id!=? AND status='waiting'",(*key,review['id']))
    row=queue.db.execute('SELECT definition,due,last_seen,status FROM npc_goal_reviews WHERE world=? AND actor=? AND id=?',(*key,review['id'])).fetchone()
    if not row:
        queue.db.execute('INSERT INTO npc_goal_reviews VALUES(?,?,?,?,?,?,?)',(*key,review['id'],encoded,now+review['after_seconds'],now,'waiting'));return None
    if row[0]!=encoded or row[3]!='waiting':return None # New intent requires a new id; never replay.
    if now<row[2]:
        queue.db.execute('UPDATE npc_goal_reviews SET due=?,last_seen=? WHERE world=? AND actor=? AND id=?',(now+review['after_seconds'],now,*key,review['id']));return None
    queue.db.execute('UPDATE npc_goal_reviews SET last_seen=? WHERE world=? AND actor=? AND id=?',(now,*key,review['id']))
    if defer or now<row[1] or unfinished(data,sub['id'],character):return None
    day=int(now//86400);budget=queue.db.execute('SELECT day,attempts FROM npc_goal_review_budget WHERE world=? AND actor=?',key).fetchone()
    count=budget[1] if budget and budget[0]>=day else 0;day=max(day,budget[0]) if budget else day
    if count>=8:return None
    packet=dict(world_id=sub['world'],id=sub['id'],expected_version=character['version'],evidence=character['evidence'][-1],purpose=sub['purpose'],canonical=False,goal_review=review)
    identity=uuid.uuid4().hex
    queue.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',(identity,sub['id'],
        'Reconsider your own retained goal from current state and real history. Choose a supported action, revise the goal, or wait. A review window proves no activity or accomplishment. A new future review requires a new id; never repeat a plan or past outcome blindly.',
        'character','queued',now,json.dumps(packet)))
    queue.db.execute("UPDATE npc_goal_reviews SET status='queued' WHERE world=? AND actor=? AND id=?",(*key,review['id']))
    queue.db.execute('INSERT OR REPLACE INTO npc_goal_review_budget VALUES(?,?,?,?)',(*key,day,count+1))
    return identity

def check(packet,character):
    review=packet.get('goal_review')
    if review is None:return False
    if character.get('canonical') or review!=character.get('goal_review') or character.get('status')!='active':raise ValueError('Goal review changed or withdrawn')
    validate(review,character['goals'])
    return True
