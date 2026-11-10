"""Temporary public land encounters, not simulated migration or saved TV records."""
import time
from .build_catalog import catalog_maps
from .species_cohort import species_id

# Actual land_mons entries in pinned Expansion src/data/wild_encounters.json.
# Route130/Mirage Island excluded: story/conditional land availability is not modeled.
ROUTES=tuple('Route'+str(n) for n in (101,102,103,104,110,111,112,113,114,115,116,117,118,119,120,121,123))

def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS shared_outbreaks(map TEXT PRIMARY KEY,actor TEXT,species TEXT,level INTEGER,chance INTEGER,expires REAL,revision INTEGER)')

def catalog(server):
 return dict(maps=list(ROUTES),active=[dict(map=r[0],actor=r[1],species=r[2],level=r[3],chance=r[4],expires=r[5],revision=r[6]) for r in server.db.execute('SELECT * FROM shared_outbreaks WHERE expires>? ORDER BY map',(time.time(),))],basis='authored_encounter_configuration_not_sightings')

def configure(server,actor,row,args):
 if set(args)!={'map','species','level','chance','minutes'} or args['map'] not in ROUTES:raise ValueError('Choose a reviewed Hoenn land-encounter route')
 if any(type(args[k]) is not int or not lo<=args[k]<=hi for k,lo,hi in (('level',1,100),('chance',1,50),('minutes',0,60))):raise ValueError('Level 1..100, chance 1..50 percent, minutes 0..60')
 species_id(args['species'],'expansion-native')
 old=server.db.execute('SELECT actor,expires FROM shared_outbreaks WHERE map=?',(args['map'],)).fetchone()
 if old and old[0]!=actor and old[1]>time.time():raise ValueError('Another actor owns this active outbreak; wait for expiry')
 if not any(m['name']==args['map'] for m in catalog_maps().values()):raise ValueError('Route absent from selected build')
 expires=time.time()+args['minutes']*60
 seq=server.memory.append('shared_outbreak_configured',dict(character_id=actor,**args,expires=expires,
  basis='authority_encounter_authoring',limits='Temporary native land encounter configuration, not an observed migration, sighting, catch or training. Personal saved outbreaks take priority.'))
 server.db.execute('INSERT INTO shared_outbreaks VALUES(?,?,?,?,?,?,?) ON CONFLICT(map) DO UPDATE SET actor=excluded.actor,species=excluded.species,level=excluded.level,chance=excluded.chance,expires=excluded.expires,revision=excluded.revision',(args['map'],actor,args['species'],args['level'],args['chance'],expires,seq))
 server.revision=seq
 return dict(outcome='shared_outbreak_configured' if args['minutes'] else 'shared_outbreak_closed',map=args['map'],revision=seq,expires=expires)

def line(server,conn):
 state=conn.get('state')
 if not conn.get('outbreak_capable') or not state:return None
 name=catalog_maps().get(tuple(state[:2]),{}).get('name')
 r=server.db.execute('SELECT species,level,chance,expires FROM shared_outbreaks WHERE map=?',(name,)).fetchone()
 if not r:return None
 seconds=min(3600,int(r[3]-time.time()))
 if seconds<1:return None
 return 'WILD_OUTBREAK '+' '.join(map(str,[*state[:2],species_id(r[0],'expansion-native'),r[1],r[2],seconds]))

def command(server,conn,words):
 from .guilds import GuildError
 if words:raise GuildError('Use /guild outbreaks for current public populations')
 rows=catalog(server)['active']
 if not rows:return ['No active shared outbreaks.']
 return ['Shared land outbreaks (saved personal outbreaks take priority):']+[f"{r['map']}: {r['species']} Lv{r['level']}, {r['chance']}%, {max(0,int((r['expires']-time.time())/60))} min left" for r in rows]
