"""Host-directed goals enter the same typed actor/result loop as public events."""
import json
import re
import time
from .character_reactions import actors


def submit(queue, inspection, actor, goal, request_id):
    data=inspection.get('data',inspection)
    character=actors(data.get('state',{})).get(actor)
    memory=data.get('world_memory',{})
    if (inspection.get('ok') is not True or not character or character.get('status')!='active'
        or type(goal) is not str or not 1<=len(goal.strip())<=1024
        or type(request_id) is not str or not re.fullmatch('[a-zA-Z0-9_-]{8,80}',request_id)
        or not character.get('evidence') or not memory.get('world_id')):
        raise ValueError('Choose an existing active actor and a bounded world goal')
    key='world-goal-'+request_id
    text='Pursue this host world-building goal using discovered capabilities, or wait if unsupported: '+goal
    packet=dict(id=actor,world_id=memory['world_id'],expected_version=character['version'],
        canonical=bool(character.get('canonical')),evidence=character['evidence'][-1],purpose=goal,host_goal=True)
    with queue.db:
        queue.db.execute('BEGIN IMMEDIATE')
        old=queue.db.execute('SELECT player,text,kind FROM requests WHERE id=?',(key,)).fetchone()
        if old:
            if tuple(old)!=(actor,text,'character'):raise ValueError('Goal request identity already used')
            return key
        if queue.db.execute("SELECT 1 FROM requests WHERE kind='character' AND player=? AND status IN ('queued','running')",(actor,)).fetchone():
            raise ValueError('Actor already has a pending author turn')
        if queue.db.execute('SELECT count(*) FROM character_reactions').fetchone()[0]>=8 and not queue.db.execute('SELECT 1 FROM character_reactions WHERE id=?',(actor,)).fetchone():
            raise ValueError('Followed actor capacity reached')
        queue.db.execute('DELETE FROM population_agents WHERE id=?',(actor,)) # Explicit host goal takes over the bounded lifecycle.
        queue.db.execute('INSERT OR REPLACE INTO character_reactions VALUES(?,?,?,?)',
                         (actor,goal,memory['world_id'],memory['through']))
        queue.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
                         (key,actor,text,'character','queued',time.time(),json.dumps(packet)))
    return key
