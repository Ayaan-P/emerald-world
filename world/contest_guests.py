"""Real owned companions offered as optional normal-rank native contestants."""
import re
from .characters import records
from .character_training import source
from .build_catalog import catalog_maps
CATEGORIES=('cool','beauty','cute','smart','tough')
LOCATION='LilycoveCity_ContestLobby'
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS contest_guests(category TEXT PRIMARY KEY,actor TEXT,individual TEXT,revision INTEGER)')
def participant(server,actor,individual):
 c=records(server.module_state).get(actor)
 obj=next((o for o in server.objects if o['id']==actor),None)
 if not c or c['status']!='active' or not obj or obj.get('region_revision') or catalog_maps().get((obj['group'],obj['num']),{}).get('name')!=LOCATION:
  raise ValueError('Recurring actor must actually occupy the Lilycove contest lobby')
 if not re.fullmatch('[A-Za-z0-9 ]{1,7}',c['name']):raise ValueError('Native guest trainer name needs 1..7 ASCII letters, digits or spaces')
 return c,obj,source(server,actor,individual)
def available(server):
 result=[]
 for category,actor,individual,revision in server.db.execute('SELECT * FROM contest_guests ORDER BY category'):
  try:c,obj,mon=participant(server,actor,individual)
  except ValueError:continue
  result.append(dict(category=category,actor=actor,individual=individual,revision=revision,name=c['name'],species=mon['species'],level=mon['trained']['state']['level'] if mon['trained'] else mon['authored_level']))
 return result

def configure(server,actor,row,args):
 if set(args)!={'category','individual'} or args['category'] not in CATEGORIES or type(args['individual']) is not str:raise ValueError('Choose contest category and own on-team individual, or empty individual to withdraw')
 prior=server.db.execute('SELECT actor FROM contest_guests WHERE category=?',(args['category'],)).fetchone()
 if prior and prior[0]!=actor:raise ValueError('This category already has another actor entry')
 if args['individual']:participant(server,actor,args['individual'])
 seq=server.memory.append('contest_guest_entry_changed',dict(character_id=actor,**args,rank='normal',basis='authority_entry_configuration',limits='Optional guest opponent entry, not travel, actual attendance, contest result, ribbon or training.'))
 if args['individual']:server.db.execute('INSERT INTO contest_guests VALUES(?,?,?,?) ON CONFLICT(category) DO UPDATE SET individual=excluded.individual,revision=excluded.revision',(args['category'],actor,args['individual'],seq))
 else:server.db.execute('DELETE FROM contest_guests WHERE category=? AND actor=?',(args['category'],actor))
 server.revision=seq
 return dict(outcome='contest_guest_offered' if args['individual'] else 'contest_guest_withdrawn',category=args['category'],revision=seq)

def lines(server,conn):
 state=conn.get('state')
 if not conn.get('contest_guest_capable') or not state or catalog_maps().get(tuple(state[:2]),{}).get('name')!=LOCATION:return []
 result=[]
 for entry in available(server):
  c,obj,mon=participant(server,entry['actor'],entry['individual']);trained=mon['trained'];s=trained['state'] if trained else None
  result.append('CONTEST_GUEST '+' '.join(map(str,[entry['actor'],entry['revision'],CATEGORIES.index(entry['category']),mon['species'],s['level'] if s else mon['authored_level'],mon['personality'],mon['owner'],int(obj['gfx']==8),c['name'].encode('ascii').hex(),s['blob'] if s else '-'])))
 return result

def command(server,conn,words):
 from .guilds import GuildError
 if words:raise GuildError('Use /guild contests for optional normal-rank guests')
 return ['Optional Lilycove normal-rank guests:']+[f"{e['category']}: {e['name']} (owned species {e['species']}, Lv{e['level']}). Ask the receptionist normally." for e in available(server)]
