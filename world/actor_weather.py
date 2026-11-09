"""Persistent exact-destination weather, using existing native weather effects."""
WEATHER={'clear':2,'clouds':1,'rain':3,'snow':4,'fog':6,'overcast':11}
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS outdoor_weather(identity TEXT PRIMARY KEY,revision INTEGER,mode TEXT)')

def configure(server,actor,row,args):
 if set(args)!={'revision','mode'} or type(args['mode']) is not str or args['mode'] not in (*WEATHER,'default'):raise ValueError('Choose a supported outdoor weather or default')
 cave=server.shared_cave
 obj=next((o for o in server.objects if o['id']==actor),None)
 if (not cave or cave.version!=16 or not server.archive_generated_areas or not obj
     or obj.get('region_revision')!=args['revision'] or cave.identity!=args['revision']
     or (obj['group'],obj['num'])!=server.wilds_map or not cave.walkable(obj['x'],obj['y'])):
  raise ValueError('Actor must occupy this exact active archived outdoor destination')
 seq=server.memory.append('outdoor_weather_changed',dict(character_id=actor,region_revision=cave.identity,mode=args['mode'],
  basis='authority_environment_authoring',limits='Shared native weather setting, not observed climate, a character power or proof of client application. Native weather effects apply normally.'))
 server.db.execute('INSERT INTO outdoor_weather VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,mode=excluded.mode',(cave.identity,seq,args['mode']))
 server.revision=seq
 return dict(outcome='outdoor_weather_configured',revision=cave.identity,weather_revision=seq,mode=args['mode'])

def current(server,revision):
 saved=server.db.execute('SELECT revision,mode FROM outdoor_weather WHERE identity=?',(revision,)).fetchone()
 return dict(revision=saved[0],mode=saved[1]) if saved else dict(revision=0,mode='default')

def line(server,conn):
 cave=server._connection_cave(conn);state=conn.get('state')
 if (not conn.get('outdoor_weather_capable') or not cave or cave.version!=16 or not state
     or tuple(state[:2])!=server.wilds_map or conn.get('cave_ack')!=cave.identity):return None
 weather=current(server,cave.identity)
 if weather['mode']=='default':return None
 return f"OUTDOOR_WEATHER {cave.identity} {weather['revision']} {WEATHER[weather['mode']]}"
