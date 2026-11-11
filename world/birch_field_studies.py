"""Private retained study invitations, not catch/teaching/completion receipts."""
import copy
import hashlib
import json
import secrets
import time


STOCK_HABITATS = {"WURMPLE":["Route101","Route102","Route104"],"POOCHYENA":["Route101","Route102","Route103","Route104","Route110","Route116","Route117","Route120","Route121","Route123"],"ZIGZAGOON":["Route101","Route102","Route103","Route118","Route119"],"LOTAD":["Route102","Route114"],"RALTS":["Route102"],"SEEDOT":["Route102","Route117","Route120"],"WINGULL":["Route103","Route104","Route110","Route118","Route115","Route121","Route123"],"MARILL":["Route104","Route112","Route117","Route120"],"TAILLOW":["Route104","Route116","Route115"],"ELECTRIKE":["Route110","Route118"],"GULPIN":["Route110"],"MINUN":["Route110"],"ODDISH":["Route110","Route117","Route119","Route120","Route121","Route123"],"PLUSLE":["Route110"],"SANDSHREW":["Route111"],"TRAPINCH":["Route111"],"BALTOY":["Route111"],"CACNEA":["Route111"],"NUMEL":["Route112"],"SPINDA":["Route113"],"SLUGMA":["Route113"],"SKARMORY":["Route113"],"SWABLU":["Route114","Route115"],"LOMBRE":["Route114"],"SEVIPER":["Route114"],"NUZLEAF":["Route114"],"WHISMUR":["Route116"],"NINCADA":["Route116"],"ABRA":["Route116"],"SKITTY":["Route116"],"ILLUMISE":["Route117"],"VOLBEAT":["Route117"],"LINOONE":["Route118","Route119"],"MANECTRIC":["Route118"],"KECLEON":["Route118","Route119","Route120","Route121","Route123"],"SWELLOW":["Route115"],"JIGGLYPUFF":["Route115"],"TROPIUS":["Route119"],"MIGHTYENA":["Route120","Route121","Route123"],"ABSOL":["Route120"],"SHUPPET":["Route121","Route123"],"GLOOM":["Route121","Route123"]}
SOURCE_BLOB = 'ac4c8a1f56063f1d4f284fe43e3b3297a0eee767'

def catalog():
    return dict(species=STOCK_HABITATS, source_blob=SOURCE_BLOB, basis='Verified stock land tables on reviewed Hoenn routes. Personal access, Repel, optional shuffle and actual encounter outcomes are not guaranteed. No inferred sightings.')


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS birch_field_studies(trainer TEXT, run TEXT, body TEXT NOT NULL, expires REAL NOT NULL, PRIMARY KEY(trainer,run))')


def validate(value, identity, appearances):
    from .species_cohort import species_id
    if (identity!='canon_birch' or appearances!=['birch'] or type(value) is not dict
            or set(value)!={'species','days'} or type(value['days']) is not int
            or not 1<=value['days']<=7 or type(value['species']) is not list
            or not 1<=len(value['species'])<=3):
        raise ValueError('Birch research requires 1..3 enabled species and a 1..7 day invitation')
    if any(type(name) is not str or name not in STOCK_HABITATS for name in value['species']):
        raise ValueError('Choose species from the reviewed original Hoenn field-study habitat catalog')
    ids=[species_id(s,'expansion-native') for s in value['species']]
    if len(ids)!=len(set(ids)):raise ValueError('Research species must be distinct')


def retained(server,conn,run):
    setup(server.db)
    row=server.db.execute('SELECT body,expires FROM birch_field_studies WHERE trainer=? AND run=?',(conn['id'],run)).fetchone()
    if not row or row[1]<=time.time():return None
    result=json.loads(row[0])
    if type(result) is not dict or result.get('schema')!=1:
        raise ValueError('Unsupported stored study version; no teaching offer issued')
    result['expires']=row[1]
    return result


def fallback(server,conn,run,key):
    if key!='birch' or not retained(server,conn,run):return None
    # System service reminder, not generated character speech or a completion claim.
    result=dict(schema=1,world_id=server.memory.world_id,run=run,actor='canon_birch',version=0,
                briefing='Your accepted field study is still available here.',objective='L field study.',evidence=[])
    result['digest']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    conn['core_active_run']=run
    conn['canonical_location']=dict(actor='canon_birch',map='LittlerootTown_ProfessorBirchsLab',run=run,version=0,expires=time.monotonic()+120)
    return result


def handle(server,conn,run,key,guard):
    from .canonical_cast import records
    from .species_cohort import species_id
    if key!='birch' or conn.get('core_active_run')!=run:raise ValueError('Current Birch save context required')
    server.core_story._place(conn,'LittlerootTown_ProfessorBirchsLab')
    reached=conn.get('canonical_location') or {}
    if (reached.get('actor')!='canon_birch' or reached.get('run')!=run
            or reached.get('map')!='LittlerootTown_ProfessorBirchsLab'
            or (guard=='view' and reached.get('expires',0)<time.monotonic())):raise ValueError('Talk to Birch here first')
    # Fresh FIELD is valid for this bounded menu while the original script owns its lock.
    # No actor movement, battle, caught flag or teaching result is authorized here.
    setup(server.db)
    old=retained(server,conn,run)
    row=records(server.module_state).get('canon_birch')
    tutor=(row or {}).get('tutor') or {}
    proposal=None
    if tutor.get('research'):
        validate(tutor['research'],'canon_birch',tutor['appearances'])
        proposal=dict(move=tutor['move'],species=[species_id(s,'expansion-native') for s in tutor['research']['species']],
                      days=tutor['research']['days'],version=row['version'])
    status='view'
    if guard!='view':
        words=guard.split(':');preview=conn.pop('birch_study_preview',None)
        if (len(words)!=2 or words[0] not in ('accept','tutor','leave') or not preview
                or words[1]!=preview['token'] or preview['run']!=run or preview['until']<time.monotonic()):
            raise ValueError('Study preview expired; open it again')
        if words[0]=='accept':
            if old or proposal is None or proposal!=preview['proposal'] or reached.get('version')!=proposal['version']:
                raise ValueError('New study changed before acceptance')
            if server.db.execute('SELECT count(*) FROM birch_field_studies WHERE trainer=? AND expires>?',(conn['id'],time.time())).fetchone()[0]>=32:
                raise ValueError('Too many active save invitations; leave an older one first')
            body=dict(proposal,id=secrets.token_hex(16),schema=1)
            expiry=time.time()+body['days']*86400
            with server.db:
                server.db.execute('INSERT OR REPLACE INTO birch_field_studies VALUES(?,?,?,?)',(conn['id'],run,json.dumps(body),expiry))
            old=dict(body,expires=expiry)
        else:
            if not old or old['id']!=preview['id']:raise ValueError('Accepted study changed or expired')
            if words[0]=='leave':
                with server.db:server.db.execute('DELETE FROM birch_field_studies WHERE trainer=? AND run=?',(conn['id'],run))
                old=None;status='left'
            else:
                # Frozen native offer only. Never assert caught/learned/completed.
                return dict(mode='teach',move=old['move'],species=old['species'],token=old['id'],minutes=max(1,min(120,int((old['expires']-time.time())/60))))
    selected=old or proposal
    if selected is None or status=='left':
        return dict(mode='none',move=0,species=[],token='-',minutes=0)
    token=secrets.token_hex(16)
    conn['birch_study_preview']=dict(token=token,run=run,until=time.monotonic()+300,
                                    proposal=copy.deepcopy(proposal),id=old['id'] if old else None)
    return dict(mode='active' if old else 'offer',move=selected['move'],species=selected['species'],token=token,
                minutes=max(1,int((old['expires']-time.time())/60)) if old else selected['days']*1440)


def wire(result):
    return ' '.join([result['mode'],str(result['move']),result['token'],str(result['minutes']),str(len(result['species'])),*map(str,result['species'])])
