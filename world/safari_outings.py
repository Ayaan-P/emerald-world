"""Optional shared Safari outings. Counts are authenticated client reports, not capture verification."""
import json,re,secrets,time,sqlite3
from .guilds import GuildError


def setup(db):
 db.execute('CREATE TABLE IF NOT EXISTS safari_outings(id TEXT PRIMARY KEY,actor TEXT,title TEXT,target INTEGER,expires REAL)')
 db.execute('CREATE TABLE IF NOT EXISTS safari_participants(outing TEXT,trainer TEXT,lineage TEXT,lease TEXT UNIQUE,seq INTEGER,phase INTEGER,catches INTEGER,battles INTEGER,balls INTEGER,steps INTEGER,status TEXT,PRIMARY KEY(outing,trainer,lineage))')


def summary(server,key):
 setup(server.db)
 row=server.db.execute('SELECT actor,title,target,expires FROM safari_outings WHERE id=?',(key,)).fetchone()
 if not row:raise ValueError('Unknown outing')
 people,catches,finished=server.db.execute("SELECT count(*),coalesce(sum(catches),0),coalesce(sum(status='finished'),0) FROM safari_participants WHERE outing=?",(key,)).fetchone()
 return dict(id=key,actor=row[0],title=row[1],target=row[2],expires=row[3],participants=people,reported_catches=catches,finished_visits=finished,target_reported=catches>=row[2],expired=time.time()>=row[3],basis='opted_in_client_reported_safari_counts_not_verified_captures')


def catalog(server):
 setup(server.db)
 return [summary(server,key) for key, in server.db.execute('SELECT id FROM safari_outings ORDER BY expires DESC LIMIT 32')]


def publish(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id','title','target','hours'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']) or type(args['title']) is not str or not 1<=len(args['title'])<=60 or any(not 32<=ord(c)<127 for c in args['title']) or type(args['target']) is not int or not 1<=args['target']<=120 or type(args['hours']) is not int or not 1<=args['hours']<=24:raise ValueError('Use stable id, public title, group catch target 1..120 and duration 1..24 hours')
 if server.db.execute('SELECT 1 FROM safari_outings WHERE id=?',(args['id'],)).fetchone():raise ValueError('Outing identity already exists')
 if server.db.execute('SELECT count(*) FROM safari_outings WHERE expires>?',(time.time(),)).fetchone()[0]>=16:raise ValueError('Sixteen active outings; wait for one to expire')
 server.db.execute('INSERT INTO safari_outings VALUES(?,?,?,?,?)',(args['id'],actor,args['title'],args['target'],time.time()+3600*args['hours']))
 return dict(outcome='safari_outing_published',**summary(server,args['id']),entry='/guild safari '+args['id'],limits='Players opt in, then enter stock Safari normally. No catch, reward, travel or rule change claimed.')


def command(server,conn,words):
 if len(words)>1:raise GuildError('Use /guild safari or /guild safari ID')
 try:items=[summary(server,words[0])] if words else catalog(server)
 except ValueError as exc:raise GuildError(str(exc)) from None
 lines=['Safari outings: optional stock Safari visits. Counts are client reports.',
        'Joining shares anonymous group counts with ALL world players and agents, including after leaving.',
        'No species, party, save identity or trainer name is published. Host storage remains trusted.']
 for entry in items[:4]:
  lines += [entry['id']+': '+entry['title'],f"Reported catches {entry['reported_catches']}/{entry['target']}; visitors {entry['participants']}/4; ended visits {entry['finished_visits']}",
            'Expired' if entry['expired'] else '/safari '+entry['id']+' yes (outside Safari, before entering)']
 return lines+['Native /safari status checks admission; /safari stop stops reports. No rewards or shared save edits.']


def handle(server,conn,raw):
 """Called only after existing LINK authentication/presence-channel checks."""
 setup(server.db)
 try:
  fields=raw.decode('ascii').split(' ');peer=conn['presence'];trainer=conn['id'];lineage=peer.get('campaign_run')
  if not lineage or server.link_protocol.busy(trainer):raise ValueError('Unavailable')
  with server.db:
   if len(fields)==4 and fields[:3]==['S','JOIN','1']:
    key=fields[3];outing=summary(server,key)
    if outing['expired'] or outing['participants']>=4 or conn.get('safari_lease'):raise ValueError('Closed')
    if server.db.execute('SELECT 1 FROM safari_participants WHERE outing=? AND trainer=? AND lineage=?',(key,trainer,lineage)).fetchone():raise ValueError('Already participated; no automatic replay or rejoin')
    lease=secrets.token_hex(16)
    server.db.execute('INSERT INTO safari_participants VALUES(?,?,?,?,0,0,0,0,30,500,?)',(key,trainer,lineage,lease,'admitted'))
    conn['safari_lease']=lease;conn['safari_lineage']=lineage
    return 'S ADMIT '+lease+'\n'
   if not conn.get('safari_lease') or conn.get('safari_lineage')!=lineage or fields[2]!=conn['safari_lease']:raise ValueError('Lease unavailable')
   lease=fields[2];saved=server.db.execute('SELECT outing,seq,phase,catches,battles,balls,steps,status FROM safari_participants WHERE lease=? AND trainer=? AND lineage=?',(lease,trainer,lineage)).fetchone()
   if not saved or summary(server,saved[0])['expired']:raise ValueError('Expired')
   if len(fields)==3 and fields[:2]==['S','STOP']:
    server.db.execute("UPDATE safari_participants SET status='withdrawn' WHERE lease=? AND status!='finished'",(lease,));conn.pop('safari_lease',None);return 'S ERROR STOPPED\n'
   if len(fields)!=9 or fields[:2]!=['S','REPORT'] or any(not re.fullmatch('[0-9]{1,5}',x) for x in fields[3:]):raise ValueError('Shape')
   seq,phase,catches,battles,balls,steps=map(int,fields[3:])
   if seq==saved[1] and [phase,catches,battles,balls,steps]==list(saved[2:7]):return f'S ACK {lease} {seq}\n'
   if saved[7] in ('finished','withdrawn') or not saved[1]<seq<=1026 or phase not in (1,2,3) or phase<saved[2] or not saved[3]<=catches<=30 or not saved[4]<=battles<=1024 or catches>battles or not 0<=balls<=saved[5] or not 0<=steps<=saved[6] or catches>30-balls:raise ValueError('Invalid cumulative report')
   if seq!=1+battles+(phase==3):raise ValueError('Invalid sequence')
   if phase==2 and not battles:raise ValueError('Missing battle')
   if phase==1 and (seq!=1 or battles or catches or balls!=30 or steps!=500):raise ValueError('Invalid start')
   from .build_catalog import catalog_maps
   state=peer.get('state')
   # Ending can occur after the stock exit warp. Other reports require actual current Safari presence.
   if phase!=3 and (not state or not catalog_maps().get(tuple(state[:2]),{}).get('name','').startswith('SafariZone_')):return 'S WAIT '+lease+'\n'
   server.db.execute('UPDATE safari_participants SET seq=?,phase=?,catches=?,battles=?,balls=?,steps=?,status=? WHERE lease=?',(seq,phase,catches,battles,balls,steps,'finished' if phase==3 else 'active',lease))
   total=summary(server,saved[0])
   server.revision=server.memory.append('safari_outing_reported',dict(total,limits='Anonymous aggregate from consenting clients. Not verified catches, awards, native save edits or NPC growth.'))
   return f'S ACK {lease} {seq}\n'
 except (ValueError,KeyError,IndexError,UnicodeError,sqlite3.IntegrityError):return 'S ERROR UNAVAILABLE\n'


def wait(server,actor,row,args):
 from .actor_runtime import Pending
 if set(args)!={'id'} or type(args['id']) is not str or summary(server,args['id'])['actor']!=actor:raise ValueError('Wait for your own published outing')
 return Pending(dict(args),lambda:None)


def poll(server,actor,row,pending):
 result=summary(server,pending['id'])
 if result['target_reported'] or result['expired']:
  return dict(outcome='safari_target_reported' if result['target_reported'] else 'safari_outing_expired',**result)
 return None
