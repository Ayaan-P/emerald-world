"""Stable fictional companion identity for actual dynamic native opponent parties."""
import hashlib


def setup(db):
    db.execute('''CREATE TABLE IF NOT EXISTS character_companions(
        actor TEXT, individual TEXT, species INTEGER, personality INTEGER, owner INTEGER,
        PRIMARY KEY(actor,individual))''');db.commit()


def validate(db, identity, character):
    known=dict(db.execute('SELECT individual,species FROM character_companions WHERE actor=?',(identity,)))
    for mon in character['team']:
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


def descriptor(server, identity, team):
    values=[]
    for mon in team:
        row=server.db.execute('SELECT species,personality,owner FROM character_companions WHERE actor=? AND individual=?',(identity,mon['individual'])).fetchone()
        if row is None or row[0]!=mon['species']:raise ValueError('companion identity unavailable')
        values.extend((mon['species'],mon['level'],row[1],row[2]))
    return values
