"""Trusted host-only capture import. Never accepts a client battle report.

Experimental runner must first pass exact-binary linked QA. Imports bench state,
not a team rewrite. Ledger access is a host privilege, not an agent tool.
"""
import hashlib,json
from .characters import records
from .character_training import source


def queue(server, ledger, actor, individual, engine, ball, name):
    current=source(server,actor,individual)
    trained=current['trained']
    if not trained or trained['engine']!=engine:
        raise ValueError('Exact-engine full owned companion state required')
    obj=next((o for o in server.objects if o.get('id')==actor),None)
    if not obj or not obj.get('region_revision'):
        raise ValueError('Actual generated-region actor placement required')
    revision=obj['region_revision']
    row=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
    if not row:raise ValueError('Archived actual habitat unavailable')
    from .shared_cave import SharedCave
    cave=SharedCave(row[0])
    if cave.version!=10 or not cave.walkable(obj['x'],obj['y']):raise ValueError('Actor must occupy a supported habitat tile')
    # Do not infer a catch from the actor being near a map or from authored prose.
    owner=int.from_bytes(hashlib.sha256(('npc-owner:'+server.memory.world_id+':'+actor).encode()).digest()[:4],'big')
    job=ledger.queue(actor,trained['state'],row[0],owner,name,ball,engine)
    ledger.db.execute('CREATE TABLE IF NOT EXISTS capture_world_binding(job TEXT PRIMARY KEY,world TEXT,source TEXT,object TEXT)')
    with ledger.db:
        ledger.db.execute('INSERT INTO capture_world_binding VALUES(?,?,?,?)',(job,server.memory.world_id,json.dumps(current,sort_keys=True),json.dumps(obj,sort_keys=True)))
    return job


def reconcile(server,ledger,job):
    binding=ledger.db.execute('SELECT world,source,object FROM capture_world_binding WHERE job=?',(job,)).fetchone()
    row=ledger.db.execute('SELECT actor,engine,status,result FROM capture_jobs WHERE id=?',(job,)).fetchone()
    if not binding or not row or binding[0]!=server.memory.world_id or row[2]!='completed':
        raise ValueError('Completed host-bound attempt in this world required')
    actor,engine,_,encoded=row; result=json.loads(encoded)
    if not result['caught']:raise ValueError('Failed throw remains unresolved; no companion to import')
    server.db.execute('CREATE TABLE IF NOT EXISTS character_capture_receipts(job TEXT PRIMARY KEY,fingerprint TEXT,result TEXT)')
    fingerprint=hashlib.sha256(json.dumps([binding,row],sort_keys=True).encode()).hexdigest()
    old=server.db.execute('SELECT fingerprint,result FROM character_capture_receipts WHERE job=?',(job,)).fetchone()
    if old:
        if old[0]!=fingerprint:raise ValueError('Capture receipt changed')
        return json.loads(old[1])
    frozen=json.loads(binding[1]);current=source(server,actor,frozen['individual'])
    obj=next((o for o in server.objects if o.get('id')==actor),None)
    if current!=frozen or obj!=json.loads(binding[2]):raise ValueError('Actor or owned source changed during attempt')
    if records(server.module_state)[actor]['status']!='active':raise ValueError('Actor no longer active')
    mon=result['state'];key='catch_'+job[:18]
    from .companion_exchange import identity
    native=(mon['species'],mon['personality'],mon['owner'])
    if server.db.execute('SELECT 1 FROM character_companions WHERE species=? AND personality=? AND owner=?',native).fetchone():raise ValueError('Native individual already exists; do not duplicate')
    if server.db.execute('SELECT count(*) FROM character_companions WHERE actor=?',(actor,)).fetchone()[0]>=32:raise ValueError('Companion archive full; captured result retained for host review')
    member=dict(individual=key,species=mon['species'],level=mon['level'])
    with server.db:
        server.db.execute('INSERT INTO character_companions VALUES(?,?,?,?,?)',(actor,key,*native))
        server.db.execute('INSERT INTO companion_custody VALUES(?,?)',(identity(native),actor))
        server.db.execute('INSERT INTO character_companion_roster VALUES(?,?,?)',(actor,key,json.dumps(member,sort_keys=True)))
        server.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',(actor,key,engine,mon['level'],json.dumps(mon,sort_keys=True)))
        seq=server.memory.append('character_capture_completed',dict(character_id=actor,individual=key,job=job,region_revision=result['revision'],species=mon['species'],basis='trusted_host_native_first_throw',limits='No battle victory or player-save mutation; benched companion.'))
        receipt=dict(outcome='captured_companion_imported',individual=key,world_receipt=seq,on_team=False)
        server.db.execute('INSERT INTO character_capture_receipts VALUES(?,?,?)',(job,fingerprint,json.dumps(receipt,sort_keys=True)))
    server.revision=seq
    return receipt
