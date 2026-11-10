"""Authored rod populations on existing Hoenn waters; no simulated catches."""
import json
import time
from .build_catalog import catalog_maps
from .species_cohort import species_id

# Fishing tables in engine #53 src/data/wild_encounters.json. No Safari/Kanto maps.
ROUTES=tuple('Route'+str(n) for n in (102,103,104,105,106,107,108,109,110,111,114,115,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134))
RODS={'old':[70,30], 'good':[60,20,20], 'super':[40,40,15,4,1]}


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS shared_fishing(map TEXT PRIMARY KEY,actor TEXT,population TEXT,expires REAL,revision INTEGER)')


def catalog(server):
    return dict(maps=list(ROUTES),rod_weights=RODS,active=[dict(map=r[0],actor=r[1],rods=json.loads(r[2]),expires=r[3],revision=r[4]) for r in server.db.execute('SELECT * FROM shared_fishing WHERE expires>? ORDER BY map',(time.time(),))],basis='authored_fishing_tables_not_catches',limits='Normal rods, fishing timing and native catches. Special Feebas spots take priority. Ordinary species shuffle remains active.')


def configure(server,actor,row,args):
    if set(args)!={'map','rods','minutes'} or args['map'] not in ROUTES:
        raise ValueError('Choose an existing Hoenn fishing route')
    if type(args['minutes']) is not int or not 0<=args['minutes']<=1440:
        raise ValueError('Duration 0..1440 minutes; zero closes own fishery')
    if type(args['rods']) is not str or len(args['rods'])>2000:
        raise ValueError('Supply rod population JSON')
    rods=json.loads(args['rods'])
    if type(rods) is not dict or set(rods)!=set(RODS):
        raise ValueError('Supply old/good/super rod slot lists')
    for rod,weights in RODS.items():
        if type(rods[rod]) is not list or len(rods[rod])!=len(weights):
            raise ValueError('Old/Good/Super rods use 2/3/5 native slots')
        for slot in rods[rod]:
            if type(slot) is not list or len(slot)!=3 or type(slot[0]) is not str:
                raise ValueError('Each slot is [species,min_level,max_level]')
            species_id(slot[0],'expansion-native')
            if any(type(n) is not int for n in slot[1:]) or not 1<=slot[1]<=slot[2]<=100:
                raise ValueError('Use level ranges within 1..100')
    old=server.db.execute('SELECT actor,expires FROM shared_fishing WHERE map=?',(args['map'],)).fetchone()
    if old and old[0]!=actor and old[1]>time.time():
        raise ValueError('Another actor owns this active fishing population')
    if args['map'] not in {m['name'] for m in catalog_maps().values()}:
        raise ValueError('Route absent from selected build')
    expires=time.time()+60*args['minutes']
    seq=server.memory.append('shared_fishing_configured',dict(character_id=actor,map=args['map'],rods=rods,expires=expires,basis='authority_encounter_authoring',limits='Configured fishing population, not an observed catch, migration, stock count or Pokemon growth.'))
    server.db.execute('INSERT OR REPLACE INTO shared_fishing VALUES(?,?,?,?,?)',(args['map'],actor,json.dumps(rods),expires,seq))
    server.revision=seq
    return dict(outcome='fishing_population_configured' if args['minutes'] else 'fishing_population_closed',map=args['map'],revision=seq,expires=expires)


def lines(server,conn):
    state=conn.get('state')
    if not conn.get('fishing_capable') or not state:return []
    name=catalog_maps().get(tuple(state[:2]),{}).get('name')
    row=server.db.execute('SELECT population,expires FROM shared_fishing WHERE map=?',(name,)).fetchone()
    if not row:return []
    seconds=min(3600,int(row[1]-time.time()))
    if seconds<1:return []
    out=['WILD_FISHERY %d %d %d'%(*state[:2],seconds)]
    slots=[slot for rod in RODS for slot in json.loads(row[0])[rod]]
    return out+['FISH_SLOT %d %d %d %d'%(i,species_id(s,'expansion-native'),lo,hi) for i,(s,lo,hi) in enumerate(slots)]


def command(server,conn,words):
    from .guilds import GuildError
    if len(words)>1 or words and words[0] not in ROUTES:
        raise GuildError('Use /guild fishing [RouteNumber]')
    active=catalog(server)['active']
    if not words:return (['Shared fishing grounds:']+[r['map']+' - /guild fishing '+r['map'] for r in active]) if active else ['No active fishing grounds.']
    rows=[r for r in active if r['map']==words[0]]
    if not rows:return ['No authored fishing population here; normal fishing remains.']
    row=rows[0];out=[row['map']+': rod populations (not sightings):']
    for rod,weights in RODS.items():
        for (s,lo,hi),weight in zip(row['rods'][rod],weights):out.append(f'{rod} rod {weight}%: {s} Lv{lo}-{hi}')
    return out+['Feebas spots and ordinary species shuffle retain native behavior.']
