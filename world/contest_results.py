"""Opt-in guest placements, not trusted native ownership mutations or ribbons."""
import hashlib,json,re,secrets,time
from . import contest_guests
BASIS='opted_in_client_reported_guest_placing'
def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS contest_reports(lease TEXT PRIMARY KEY,trainer TEXT,lineage TEXT,actor TEXT,individual TEXT,category TEXT,revision INTEGER,snapshot TEXT,expires REAL,placing INTEGER,event INTEGER)')
def digest(mon):return hashlib.sha256(json.dumps(mon,sort_keys=True).encode()).hexdigest()
def handle(server,conn,raw):
 setup(server.db)
 try:
  f=raw.decode('ascii').split(' ');peer=conn['presence'];lineage=peer.get('campaign_run')
  if not lineage or server.link_protocol.busy(conn['id']):raise ValueError('Unavailable')
  with server.db:
   if len(f)==6 and f[:3]==['C','JOIN','1']:
    actor,revision,category=f[3:]
    if not re.fullmatch('[0-9]{1,10}',revision) or category not in ('0','1','2','3','4'):raise ValueError('Shape')
    category=contest_guests.CATEGORIES[int(category)]
    entry=server.db.execute('SELECT actor,individual,revision FROM contest_guests WHERE category=?',(category,)).fetchone()
    if not entry or (entry[0],str(entry[2]))!=(actor,revision):raise ValueError('Changed entry')
    # Admission binds the real offered individual, never a caller-chosen species.
    from .build_catalog import catalog_maps
    state=peer.get('state')
    place=catalog_maps().get(tuple(state[:2]),{}).get('name') if state else None
    if not peer.get('contest_guest_capable') or place not in ('LilycoveCity_ContestLobby','LilycoveCity_ContestHall'):raise ValueError('Not at contest venue')
    if time.monotonic()-peer.get('state_time',0)>5:raise ValueError('Stale presence')
    _,_,mon=contest_guests.participant(server,actor,entry[1])
    if server.db.execute('SELECT 1 FROM contest_reports WHERE trainer=? AND placing IS NULL AND expires>?',(conn['id'],time.time())).fetchone():raise ValueError('Pending contest')
    lease=secrets.token_hex(16)
    server.db.execute('INSERT INTO contest_reports VALUES(?,?,?,?,?,?,?,?,?,NULL,NULL)',(lease,conn['id'],lineage,actor,entry[1],category,entry[2],digest(mon),time.time()+3600))
    return 'C ADMIT '+lease+'\n'
   if len(f)!=4 or f[:2]!=['C','RESULT'] or f[3] not in ('0','1','2','3'):raise ValueError('Shape')
   saved=server.db.execute('SELECT actor,individual,category,revision,snapshot,expires,placing FROM contest_reports WHERE lease=? AND trainer=? AND lineage=?',(f[2],conn['id'],lineage)).fetchone()
   if not saved:raise ValueError('Unknown lease')
   actor,individual,category,revision,snapshot,expires,placing=saved
   if placing is not None:
    if placing!=int(f[3]):raise ValueError('Conflicting replay')
    return 'C ACK '+f[2]+'\n'
   if time.time()>expires:raise ValueError('Expired')
   from .character_training import source
   try:unchanged=digest(source(server,actor,individual))==snapshot
   except ValueError:unchanged=False
   # Preserve the report even if ownership/state changed; never overwrite that state.
   seq=server.memory.append('contest_guest_result_reported',dict(character_id=actor,individual=individual,category=category,entry_revision=revision,placing=int(f[3])+1,individual_unchanged=unchanged,basis=BASIS,publication='explicit_single_contest_opt_in',limits='Client-reported guest placing, not verified victory. No human result, ribbon, condition, friendship or Pokemon state change.'))
   server.db.execute('UPDATE contest_reports SET placing=?,event=? WHERE lease=?',(int(f[3]),seq,f[2]));server.revision=seq
   return 'C ACK '+f[2]+'\n'
 except (ValueError,KeyError,UnicodeError):return 'C ERROR UNAVAILABLE\n'
def relevant(event,actor):
 return event.get('event')=='contest_guest_result_reported' and event.get('character_id')==actor and event.get('basis')==BASIS
