"""Explicitly shared ordinary native trainer results, never simulated proof."""
import json,re,secrets,time
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('trainer_experience_catalog.json').read_text())['trainers']

def participation(server,conn,run,key,guard):
    if conn.get('core_active_run')!=run:raise ValueError('Battle participation belongs to the active save')
    if (key,guard) not in (('get','private'),('on','confirm'),('off','confirm')):raise ValueError('Unknown battle participation request')
    with server.db:
        server.db.execute('CREATE TABLE IF NOT EXISTS trainer_experience_participation(trainer TEXT,run TEXT,enabled INTEGER NOT NULL,PRIMARY KEY(trainer,run))')
        if key!='get':server.db.execute('INSERT OR REPLACE INTO trainer_experience_participation VALUES(?,?,?)',(conn['id'],run,int(key=='on')))
        row=server.db.execute('SELECT enabled FROM trainer_experience_participation WHERE trainer=? AND run=?',(conn['id'],run)).fetchone()
    return dict(ok=True,battle_mode='ON' if row and row[0] else 'OFF')

def handle(server,conn,run,key,guard,*,automatic=False):
    from .build_catalog import catalog_maps
    if (conn.get('core_active_run')!=run or not conn.get('state')
            or time.monotonic()-conn.get('state_time',0)>3 or not conn['state'][6]):
        raise ValueError('Battle sharing needs this active save and fresh idle field presence')
    if automatic and participation(server,conn,run,'get','private')['battle_mode']!='ON':
        raise ValueError('Future battle participation is off for this save')
    if key not in catalog() or not re.fullmatch(r'[12]:[0-9]{1,3}:[0-9]{1,3}:[1-9][0-9]{0,9}',guard):
        raise ValueError('Unknown ordinary trainer report')
    outcome,group,num,serial=map(int,guard.split(':'))
    place=catalog_maps().get((group,num))
    if not place or place['name'].startswith('GeneratedWorld') or serial>4294967295:
        raise ValueError('Unknown original map or result serial')
    # Loss may return to a different Pokemon Center. The capture map is an
    # attestation, not the current field map and not a server-verified victory.
    session=conn.setdefault('trainer_experience_session',secrets.token_hex(16))
    with server.db:
        server.db.execute('CREATE TABLE IF NOT EXISTS trainer_experience_receipts(trainer TEXT,run TEXT,session TEXT,serial INTEGER,payload TEXT,seq INTEGER,PRIMARY KEY(trainer,run,session,serial))')
        old=server.db.execute('SELECT payload,seq FROM trainer_experience_receipts WHERE trainer=? AND run=? AND session=? AND serial=?',(conn['id'],run,session,serial)).fetchone()
        payload=key+':'+guard
        if old:
            if old[0]!=payload:raise ValueError('Battle result serial changed')
            return dict(ok=True,evidence=old[1])
        trainer=catalog()[key]
        summary='A trainer '+('defeated ' if outcome==1 else 'lost to ')+trainer['name']+' in '+place['name']+'.'
        seq=server.memory.append('canonical_trainer_result',dict(trainer_key=key,opponent=trainer['name'],
            opponent_preset=trainer['symbol'],outcome='won' if outcome==1 else 'lost',summary=summary,
            places=['native:'+place['name']],source='future_battle_participation_opt_in' if automatic else 'explicitly_shared_native_trainer_callback',
            limits='Anonymous client attestation from an ordinary single trainer battle. No party, other save, permanent victory, earned NPC growth or server simulation is implied.'))
        server.db.execute('INSERT INTO trainer_experience_receipts VALUES(?,?,?,?,?,?)',(conn['id'],run,session,serial,payload,seq))
        server.revision=seq
    return dict(ok=True,evidence=seq)

def relevant(event,places,actor=None):
    from .build_catalog import catalog_maps
    row=catalog().get(event.get('trainer_key'))
    if not row or event.get('event')!='canonical_trainer_result' or event.get('source') not in ('explicitly_shared_native_trainer_callback','future_battle_participation_opt_in'):return False
    p=event.get('places')
    own_actor=('canon_wally' if row['symbol'].startswith('TRAINER_WALLY_') else 'canon_steven' if row['symbol']=='TRAINER_STEVEN' else None)
    if not isinstance(p,list) or len(p)!=1 or (p[0] not in places and (actor is None or actor!=own_actor)):return False
    name=p[0].removeprefix('native:')
    if name not in {m['name'] for m in catalog_maps().values()} or name.startswith('GeneratedWorld'):return False
    outcome=event.get('outcome')
    return (outcome in ('won','lost') and event.get('opponent')==row['name'] and event.get('opponent_preset')==row['symbol']
            and event.get('summary')=='A trainer '+('defeated ' if outcome=='won' else 'lost to ')+row['name']+' in '+name+'.')
