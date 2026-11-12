"""Simultaneous opt-in field races. Native presence is recreational evidence,
not anti-cheat proof. No rewards, saves, warps or authored completion events.
"""
import json,re,secrets,time,sqlite3
from .guilds import GuildError

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

def validate(course,coords,generated):
 if type(course) is not dict or set(course)!={'id','title','starts','checkpoints','laps','limit','mounted'} or len(encode(course))>4096:raise ValueError('Invalid race course')
 if type(course['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',course['id']):raise ValueError('Stable course ID required')
 if type(course['title']) is not str or not 1<=len(course['title'])<=55 or any(not 32<=ord(c)<127 for c in course['title']):raise ValueError('Bounded title required')
 if type(course['mounted']) is not bool or type(course['laps']) is not int or not 1<=course['laps']<=8 or type(course['limit']) is not int or not 60<=course['limit']<=1800:raise ValueError('Invalid race rules')
 if type(course['starts']) is not list or not 2<=len(course['starts'])<=4 or type(course['checkpoints']) is not list or not 2<=len(course['checkpoints'])<=16:raise ValueError('Two to four start pads and two to sixteen checkpoints required')
 for point in course['starts']+course['checkpoints']:
  if type(point) is not list or len(point)!=4 or any(type(n) is not int for n in point):raise ValueError('Integer map and tile coordinates required')
  coords(*point)
  if tuple(point[:2]) in generated:raise ValueError('Race courses currently use ordinary stable maps, not generated aliases')
 if len({tuple(p) for p in course['starts']})!=len(course['starts']):raise ValueError('Distinct start pads required')
 first=course['starts'][0]
 if any(p[:2]!=first[:2] or abs(p[2]-first[2])+abs(p[3]-first[3])>4 for p in course['starts']):raise ValueError('Start grid must be nearby on one map')
 points=course['checkpoints']
 if any(a==b for a,b in zip(points,points[1:]+points[:1])):raise ValueError('Consecutive checkpoints and lap boundary must differ')
 return course

class SharedRaces:
 def __init__(self,server,coords,clock=time.monotonic):
  self.s=server;self.db=server.db;self.coords=coords;self.clock=clock;self.runs={}
  self.db.executescript('CREATE TABLE IF NOT EXISTS race_courses(id TEXT PRIMARY KEY,document TEXT); CREATE TABLE IF NOT EXISTS race_results(run TEXT,course TEXT,trainer TEXT,milliseconds INTEGER,splits TEXT,PRIMARY KEY(run,trainer));');self.db.commit()
 def publish(self,course):
  validate(course,self.coords,(self.s.cave_map,self.s.wilds_map));raw=encode(course)
  old=self.db.execute('SELECT document FROM race_courses WHERE id=?',(course['id'],)).fetchone()
  if old and old[0]!=raw:raise ValueError('Course ID already names different content')
  self.db.execute('INSERT OR IGNORE INTO race_courses VALUES(?,?)',(course['id'],raw))
  return dict(outcome='race_course_published',course=course['id'],players=len(course['starts']),limits='Coordinate bounds checked, not static-map walkability or fairness; playtest route before competition. No races or results fabricated.')
 def catalog(self):return [json.loads(raw) for raw, in self.db.execute('SELECT document FROM race_courses ORDER BY id LIMIT 32')]
 def course(self,key):
  row=self.db.execute('SELECT document FROM race_courses WHERE id=?',(key,)).fetchone()
  if not row:raise GuildError('Race course unavailable')
  course=json.loads(row[0]);validate(course,self.coords,(self.s.cave_map,self.s.wilds_map))
  return course
 def current(self,name):return next((r for r in self.runs.values() if any(c['id']==name for c in r['members'])),None)
 def tell(self,r,lines):
  for c in r['members']:
   if self.s.peers.get(c['id']) is c and not c.get('closing'):
    for line in lines:self.s.guild_chat.message(c,c['id'],line[:120])
 def fresh(self,c,now):return self.s.relays._fresh(c,now)
 def at(self,c,point,now):return self.fresh(c,now) and c['state'][:4]==point
 def busy(self,name):return self.s.relays._current(name) or self.s.flags.current(name) or self.s.mysteries._current(name)
 def status(self,r,c):
  i=r['members'].index(c);course=r['course']
  if r['phase'] in ('lobby','countdown'):return [course['title']+f" - racer {i+1}/{len(course['starts'])}", 'Start pad: '+self.s.relays._location(course['starts'][i]),'/guild race ready at your pad. Invite: /guild race join '+r['id']]
  progress=r['progress'][c['id']]
  if progress['finished'] is not None:return [f"You finished in {progress['finished']/1000:.2f}s. Other racers may still be running."]
  point=course['checkpoints'][progress['index']%len(course['checkpoints'])]
  return [course['title']+f" - lap {progress['index']//len(course['checkpoints'])+1}/{course['laps']}",'Next: '+self.s.relays._location(point),'Positions are client reports; recreational race, no item or XP reward.']
 def command(self,c,words):
  self.tick()
  if not c.get('private_commands'):raise GuildError('Racing needs the matched private-command client')
  guild=self.s.guilds._require(c['id']);r=self.current(c['id']);now=self.clock()
  if words==['list']:return ['Race courses:']+[key+': '+json.loads(raw)['title'] for key,raw in self.db.execute('SELECT id,document FROM race_courses ORDER BY id LIMIT 16')]
  if words==['records']:
   rows=self.db.execute('SELECT course,milliseconds FROM race_results WHERE trainer=? ORDER BY milliseconds LIMIT 12',(c['id'],)).fetchall()
   return [f'{course}: {ms/1000:.2f}s' for course,ms in rows] or ['No completed race times yet.']
  if len(words)==2 and words[0] in ('start','join'):
   if r or self.busy(c['id']):raise GuildError('Leave your existing field activity first')
   if words[0]=='start':
    if len(self.runs)>=32 or any(v['guild']==guild[0] for v in self.runs.values()):raise GuildError('Guild race already active or race capacity busy')
    course=self.course(words[1]);r=dict(id=secrets.token_hex(6),guild=guild[0],course=course,members=[c],ready=set(),phase='lobby',until=now+300)
    self.runs[r['id']]=r
   else:
    r=self.runs.get(words[1])
    if not r or r['guild']!=guild[0] or r['phase']!='lobby' or len(r['members'])>=len(r['course']['starts']):raise GuildError('Race invitation unavailable')
    r['members'].append(c)
   return self.status(r,c)
  if not r:return ['Use /guild race list, start COURSE, join CODE, records, or /guild play.']
  if not words or words==['status']:return self.status(r,c)
  if words==['leave']:
   self.tell(r,['Race stopped by a racer. Already completed individual times remain saved.']);self.runs.pop(r['id'],None);return ['You left the race.']
  if words==['ready']:
   if r['phase']!='lobby':raise GuildError('Race already started')
   if not self.at(c,r['course']['starts'][r['members'].index(c)],now):raise GuildError('Stand ready on your assigned start pad')
   if r['course']['mounted'] and (not c.get('mount_capable') or not c.get('mount',(0,0))[0]):raise GuildError('Mount a supported party Pokemon first with /mount 1..6')
   r['ready'].add(c['id'])
   if len(r['ready'])==len(r['course']['starts']):
    r.update(phase='countdown',started=now+3,mounts={p['id']:p.get('mount',(0,0)) for p in r['members']})
    self.tell(r,['Race starts in three seconds. All racers run at once. Stay on your start pads.'])
   return ['Ready. Stay on your pad.']
  raise GuildError('Use race list/start/join/ready/status/records/leave')
 def tick(self):
  now=self.clock()
  for r in list(self.runs.values()):
   course=r['course']
   if any(self.s.peers.get(c['id']) is not c or c.get('closing') or not self.s.guilds._member(c['id']) or self.s.guilds._member(c['id'])[0]!=r['guild'] for c in r['members']):
    self.tell(r,['Race interrupted by disconnect/guild change. Completed individual times remain saved.']);self.runs.pop(r['id'],None);continue
   if r['phase']=='lobby':
    if now>r['until']:self.runs.pop(r['id'],None)
    continue
   if course['mounted'] and any(c.get('mount')!=r['mounts'][c['id']] or not c.get('mount',(0,0))[0] or c.get('mount_trail_lost') for c in r['members']):
    self.tell(r,['Race stopped: mount changed or movement reports were lost. No missing visits inferred.']);self.runs.pop(r['id'],None);continue
   if r['phase']=='countdown':
    if not all(self.at(c,course['starts'][i],now) for i,c in enumerate(r['members'])):
     r['phase']='lobby';r['ready'].clear();self.tell(r,['Countdown cancelled. Return to pads and ready again.']);continue
    if now<r['started']:continue
    r['phase']='running';r['progress']={c['id']:dict(index=0,splits=[],finished=None,seq=c['seq'],trace=len(c.get('mount_trail',[]))-1) for c in r['members']};self.tell(r,['Go! Everyone follows the same checkpoints. /guild race status for your next target.'])
   if now-r['started']>course['limit'] or any(now-c.get('state_time',-100)>10 for c in r['members']):
    self.tell(r,['Race ended: time limit or stale reports. Only actual completed times remain saved.']);self.runs.pop(r['id'],None);continue
   failed=False
   for c in r['members']:
    p=r['progress'][c['id']]
    if p['finished'] is not None or not self.fresh(c,now):continue
    target=course['checkpoints'][p['index']%len(course['checkpoints'])];hit=False
    if course['mounted']:
     if p['seq']!=c['seq']:p['seq']=c['seq'];p['trace']=-1
     for i,point in enumerate(c.get('mount_trail',[])):
      if i>p['trace'] and point==target:p['trace']=i;hit=True;break
    if not hit:hit=self.at(c,target,now)
    if not hit:continue
    p['index']+=1;ms=max(0,round((now-r['started'])*1000));p['splits'].append(ms)
    if p['index']==len(course['checkpoints'])*course['laps']:
     try:
      with self.db:self.db.execute('INSERT OR IGNORE INTO race_results VALUES(?,?,?,?,?)',(r['id'],course['id'],c['id'],ms,encode(p['splits'])))
     except sqlite3.Error:
      self.tell(r,['Race stopped: finish could not be saved. No uncommitted result claimed.']);self.runs.pop(r['id'],None);failed=True;break
     p['finished']=ms;self.tell(r,[c['id']+f' finished in {ms/1000:.2f}s.'])
    else:
     for line in self.status(r,c):self.s.guild_chat.message(c,c['id'],line[:120])
   if failed:continue
   if all(p['finished'] is not None for p in r['progress'].values()):
    self.tell(r,['Race complete. /guild race records shows your own retained times.']);self.runs.pop(r['id'],None)

def publish(server,actor,row,args):
 if set(args)!={'course'} or type(args['course']) is not str:raise ValueError('Supply course JSON')
 try:course=json.loads(args['course'])
 except ValueError:raise ValueError('Invalid race JSON')
 return server.races.publish(course)
