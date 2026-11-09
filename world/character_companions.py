"""Stable fictional companion identity for actual dynamic native opponent parties."""
import hashlib,json


def setup(db):
    from .character_training import setup as setup_training
    setup_training(db)
    db.execute('''CREATE TABLE IF NOT EXISTS character_companions(
        actor TEXT, individual TEXT, species INTEGER, personality INTEGER, owner INTEGER,
        PRIMARY KEY(actor,individual))''')
    db.execute('CREATE TABLE IF NOT EXISTS character_companion_roster(actor TEXT,individual TEXT,member TEXT,PRIMARY KEY(actor,individual))');db.commit()


def validate(db, identity, character):
    known=dict(db.execute('SELECT individual,species FROM character_companions WHERE actor=?',(identity,)))
    for mon in character['team']:
        from .character_training import saved
        prior=saved(db,identity,mon.get('individual'))
        if prior and mon['level'] not in (prior['authored_level'],prior['state']['level']):raise ValueError('Authored edits cannot reset trained companion level')
        key=mon.get('individual')
        if key and key in known and known[key]!=mon['species']:
            raise ValueError('companion species cannot change without a supported evolution adapter')
    if len(set(known)|{m['individual'] for m in character['team'] if 'individual' in m})>32:
        raise ValueError('companion archive capacity reached')


def commit(db, world, changes):
    for change in changes:
        actor=change['character_id']
        owner=int.from_bytes(hashlib.sha256(('npc-owner:'+world+':'+actor).encode()).digest()[:4],'big')
        for mon in change['after']['team']:
            if 'individual' not in mon:continue
            key=mon['individual']
            personality=int.from_bytes(hashlib.sha256(('npc-mon:'+world+':'+actor+':'+key).encode()).digest()[:4],'big')
            db.execute('INSERT OR IGNORE INTO character_companions VALUES(?,?,?,?,?)',(actor,key,mon['species'],personality,owner))
            db.execute('INSERT INTO character_companion_roster VALUES(?,?,?) ON CONFLICT(actor,individual) DO UPDATE SET member=excluded.member',(actor,key,json.dumps(mon,sort_keys=True)))


def descriptor(server, identity, team):
    values=[]
    for mon in team:
        row=server.db.execute('SELECT species,personality,owner FROM character_companions WHERE actor=? AND individual=?',(identity,mon['individual'])).fetchone()
        if row is None or row[0]!=mon['species']:raise ValueError('companion identity unavailable')
        values.extend((mon['species'],mon['level'],row[1],row[2]))
    return values


def roster(server, actor):
    from .characters import records
    from .character_training import saved
    current=records(server.module_state).get(actor,{})
    members={key:json.loads(raw) for key,raw in server.db.execute('SELECT individual,member FROM character_companion_roster WHERE actor=?',(actor,))}
    members.update({m['individual']:dict(m) for m in current.get('team',[]) if 'individual' in m})
    result=[]
    for key,mon in sorted(members.items()):
        identity=server.db.execute('SELECT species,personality,owner FROM character_companions WHERE actor=? AND individual=?',(actor,key)).fetchone()
        if not identity or identity[0]!=mon['species']:continue
        trained=saved(server.db,actor,key)
        result.append(dict(individual=key,species=mon['species'],level=trained['state']['level'] if trained else mon['level'],authored_level=mon['level'],personality=identity[1],owner=identity[2],trained=trained is not None,on_team=any(m.get('individual')==key for m in current.get('team',[]))))
    return result
