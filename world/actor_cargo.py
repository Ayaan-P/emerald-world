"""Carry existing owned props across admitted cave transitions, never mint cargo."""
import json


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_cargo_transfers(definition TEXT PRIMARY KEY,actor TEXT,source TEXT,destination TEXT,cargo TEXT,committed INTEGER NOT NULL DEFAULT 0)')


def freeze(server,definition,actor,source,destination):
    setup(server.db)
    cargo=server.db.execute('SELECT id,object,version FROM world_prop_custody WHERE owner=? ORDER BY id',(actor,)).fetchall()
    if not cargo:return
    if any(json.loads(raw)['region_revision']!=source['region_revision'] for _,raw,_ in cargo):raise ValueError('Cargo scope differs from carrier')
    server.db.execute('INSERT INTO actor_cargo_transfers VALUES(?,?,?,?,?,0)',(definition,actor,json.dumps(source,sort_keys=True),json.dumps(destination,sort_keys=True),json.dumps(cargo)))


def matching(server,state,objects,actor):
    current=state.get('world_character_current_receipt',{})
    if len(current)!=1:return None
    definition=next(iter(current))
    row=server.db.execute('SELECT source,destination,cargo,committed FROM actor_cargo_transfers WHERE definition=? AND actor=?',(definition,actor)).fetchone()
    if not row or row[3]:return None
    source,destination,cargo=json.loads(row[0]),json.loads(row[1]),json.loads(row[2])
    before=next((o for o in server.objects if o['id']==actor),None)
    after=next((o for o in objects if o['id']==actor),None)
    held=[list(r) for r in server.db.execute('SELECT id,object,version FROM world_prop_custody WHERE owner=? ORDER BY id',(actor,))]
    if before!=source or after!=destination or held!=cargo:raise ValueError('Frozen carrier or cargo changed; no transfer')
    return definition,destination,cargo


def commit(server,state,objects):
    # Called inside the same transaction as validated character admission.
    for actor, in server.db.execute('SELECT DISTINCT owner FROM world_prop_custody WHERE owner IS NOT NULL').fetchall():
        value=matching(server,state,objects,actor)
        if not value:continue
        definition,destination,cargo=value
        for identity,raw,version in cargo:
            obj=json.loads(raw)
            for k in ('group','num','region_revision'):obj[k]=destination[k]
            server.db.execute('UPDATE world_prop_custody SET object=?,version=? WHERE id=?',(json.dumps(obj,sort_keys=True),version+1,identity))
        server.db.execute('UPDATE actor_cargo_transfers SET committed=1 WHERE definition=?',(definition,))
        server.revision=server.memory.append('actor_cargo_transferred',dict(character_id=actor,request=definition,destination=destination['region_revision'],objects=[i for i,_,_ in cargo],basis='same_transaction_admitted_cave_transition',limits='Existing portable props, no native bag items or carrying animation.'))
