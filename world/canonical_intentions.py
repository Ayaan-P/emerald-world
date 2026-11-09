"""Retained actor-owned work with bounded initiative and real action receipts."""
import json
import re
import time
import uuid


def validate(row, bindings, identity):
    tasks=row.get('intentions',[])
    if type(tasks) is not list or len(tasks)>3:raise ValueError('at most three pending intentions')
    seen=set()
    for task in tasks:
        if (type(task) is not dict or set(task)!={'id','kind','target','reason'}
                or type(task['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',task['id'])
                or task['id'] in seen or task['kind'] not in ('letter','project','study','construction','contribution','practice')
                or type(task['reason']) is not str or not 1<=len(task['reason'])<=160
                or any(not 32<=ord(c)<=126 for c in task['reason'])):raise ValueError('invalid retained intention')
        seen.add(task['id'])
        if task['kind']=='letter':
            if type(task['target']) is not str or task['target'] not in bindings or task['target']==identity:raise ValueError('letter intention requires a bound actor')
        elif task['kind'] in ('study','construction'):
            if type(task['target']) is not str or not re.fullmatch('[0-9a-f]{64}',task['target']):raise ValueError('map project intention requires exact archived revision')
        elif task['kind']=='project':
            if task['target']!='petalburg_relay':raise ValueError('unsupported project intention')
        elif type(task['target']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',task['target']):
            raise ValueError('intention target requires a bounded course or registered companion ID')
    if row.get('fulfill') is not None and (type(row['fulfill']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',row['fulfill'])):
        raise ValueError('invalid intention fulfillment')


def selected(before, after):
    key=after.get('fulfill')
    if key is None or key==before.get('fulfill'):return None
    task=next((t for t in before.get('intentions',[]) if t['id']==key),None)
    if not task:raise ValueError('fulfill only a previously retained intention')
    if any(t['id']==key for t in after.get('intentions',[])):raise ValueError('fulfilled intention must leave pending agenda')
    if task['kind']=='construction':raise ValueError('construction completion belongs to actual authority geometry commit')
    if task['kind']=='practice':raise ValueError('practice completion requires a verified host receipt; live fulfillment is not enabled')
    effect=after.get(task['kind'])
    if not effect or effect==before.get(task['kind']):raise ValueError('fulfillment requires a new actual action')
    target=effect.get('revision') if task['kind']=='study' else effect.get('to') if task['kind']=='letter' else effect.get('kind') if task['kind']=='project' else effect.get('course')
    if target!=task['target']:raise ValueError('action does not match retained intention target')
    return task


def complete(server, change, after_seq):
    task=selected(change.get('before') or {},change['after'])
    if not task:return
    identity=change['character_id']
    if server.db.execute('SELECT 1 FROM canonical_intent_receipts WHERE actor=? AND intention=?',(identity,task['id'])).fetchone():
        raise ValueError('intention was already fulfilled')
    expected={'letter':'canonical_letter_delivered','project':'canonical_project_published','study':'canonical_study_published','contribution':'canonical_contribution_proposed'}[task['kind']]
    receipt=None
    for seq,raw in server.db.execute("SELECT seq,data FROM events WHERE seq>? AND kind='world_memory' ORDER BY seq",(after_seq,)):
        event=json.loads(raw)
        if event.get('event')==expected and event.get('sender',event.get('character_id'))==identity:receipt=seq
    if receipt is None:raise ValueError('intention has no actual new action receipt')
    server.db.execute('INSERT INTO canonical_intent_receipts VALUES(?,?,?)',(identity,task['id'],receipt))
    server.revision=server.memory.append('canonical_intention_fulfilled',dict(character_id=identity,
        intention=task['id'],kind=task['kind'],target=task['target'],action_receipt=receipt,
        places=change['places'],publication='public_cast_intention',outcome='supported_action_committed'))


def setup(queue):
    queue.db.execute('CREATE TABLE IF NOT EXISTS canonical_intent_attempts(world TEXT, actor TEXT, intention TEXT, request TEXT, PRIMARY KEY(world,actor,intention))')


def enqueue(queue, sub, character):
    """Called in reaction queue transaction. At most eight attempts per actor/world."""
    if not character.get('canonical'):return None
    if queue.db.execute('SELECT count(*) FROM canonical_intent_attempts WHERE world=? AND actor=?',(sub['world'],sub['id'])).fetchone()[0]>=8:return None
    for task in character.get('intentions',[]):
        if task['kind'] in ('practice','construction'):continue # Host/authority dispatchers own these actions, not the public author queue.
        if queue.db.execute('SELECT 1 FROM canonical_intent_attempts WHERE world=? AND actor=? AND intention=?',(sub['world'],sub['id'],task['id'])).fetchone():continue
        key=uuid.uuid4().hex
        packet=dict(world_id=sub['world'],id=sub['id'],expected_version=character['version'],
                    evidence=character['evidence'][-1],purpose=sub['purpose'],canonical=True,intention=task)
        queue.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
                         (key,sub['id'],'Consider this retained intention. Execute only its supported action, or explicitly wait. Never claim an unsimulated outcome.',
                          'character','queued',time.time(),json.dumps(packet)))
        queue.db.execute('INSERT INTO canonical_intent_attempts VALUES(?,?,?,?)',(sub['world'],sub['id'],task['id'],key))
        return key


def fulfilled(event, identity):
    return (event.get('event')=='canonical_intention_fulfilled' and event.get('character_id')==identity
            and event.get('publication')=='public_cast_intention' and event.get('outcome')=='supported_action_committed'
            and type(event.get('action_receipt')) is int)
