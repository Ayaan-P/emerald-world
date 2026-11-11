import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_shared_generated_cave import MemoryAuthority
from world.combined_regions import DIGEST
from world.guilds import GuildError

RACE=dict(id='regional_race',title='Author chosen course',starts=[[38,0,6,8],[38,0,7,8]],checkpoints=[[38,0,6,9],[38,0,6,10]],laps=1,limit=60,mounted=False)
RELAY=dict(id='regional_relay',title='Author chosen relay',limit=180,legs=[
 dict(start=[38,0,6,8],checkpoints=[[38,0,6,9],[38,0,6,10]]),
 dict(start=[38,0,7,10],checkpoints=[[38,0,7,11],[38,0,7,12]])])
class RegionalFieldGames(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.s=MemoryAuthority(self.root/'sock',self.root/'world',combined_regions=True);self.addCleanup(lambda:self.s.close())
  self.now=1000.;p=patch('world.server.time.monotonic',side_effect=lambda:self.now);p.start();self.addCleanup(p.stop)
  self.s.relays.clock=self.s.races.clock=lambda:self.now
  self.a,self.al=self.connect('Alice');self.b,self.bl=self.connect('Bob')
  self.s.guilds.command('Alice','create Travelers');self.s.guilds.command('Alice','invite Bob');self.s.guilds.command('Bob','accept Travelers')
 def connect(self,name):
  who=self.s.create_identity(name);p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s.connections[p['sock']]=p
  self.s._line(p,f"HELLO 1 {name} {who['token']} SOCIALCHATCOMMANDS1".encode())
  link=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s.connections[link['sock']]=link
  self.s._line(link,f"HELLO 1 {name} {who['token']} LINK".encode())
  self.s._line(link,('RGC 2 '+DIGEST).encode());self.assertIn(b'RGC OK',link['out'])
  return p,link
 def state(self,p,point):
  self.s._line(p,f"STATE {p['seq']+1} {' '.join(map(str,point))} 1 7 1 {'a'*16} {'b'*16}".encode())
  self.assertFalse(p['closing']);self.assertEqual(p['state'][:4],point)
 def chat(self,p,text):
  p['chat_credit']=4
  self.s._line(p,f"CHAT {p['seq']+1} * {text.encode().hex()}".encode());self.assertFalse(p['closing'])
 def move(self,p,point):
  self.now+=.2
  other=self.b if p is self.a else self.a
  self.state(other,other['state'][:4]);self.state(p,point)
 def test_race_board_actual_checkpoints_private_records_and_restart(self):
  self.s.races.publish(RACE)
  self.chat(self.a,'/guild play start race regional_race')
  run=self.s.races.current('Alice');self.assertIsNotNone(run)
  self.chat(self.b,'/guild race join '+run['id'])
  for i,p in enumerate((self.a,self.b)):
   self.state(p,RACE['starts'][i]);self.chat(p,'/guild race ready')
  self.assertEqual(run['phase'],'countdown');self.now+=2
  for i,p in enumerate((self.a,self.b)):self.state(p,RACE['starts'][i])
  self.now+=1;self.s.races.tick();self.assertEqual(run['phase'],'running')
  self.move(self.b,RACE['checkpoints'][1]);self.assertEqual(run['progress']['Bob']['index'],0)
  for p in (self.a,self.b):
   for point in RACE['checkpoints']:self.move(p,point)
  self.assertIsNone(self.s.races.current('Alice'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],2)
  self.assertTrue(all(len(json.loads(s))==2 for s, in self.s.db.execute('SELECT splits FROM race_results')))
  self.s.close();self.s=MemoryAuthority(self.root/'sock',self.root/'world',combined_regions=True)
  self.assertFalse(self.s.races.runs);self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],2)
 def test_relay_requires_real_order_and_adjacent_handoff(self):
  self.s.relays.publish(RELAY);self.chat(self.a,'/guild relay start regional_relay')
  run=self.s.relays._current('Alice');self.chat(self.b,'/guild relay join '+run['id'])
  for i,p in enumerate((self.a,self.b)):
   self.state(p,RELAY['legs'][i]['start']);self.chat(p,'/guild relay ready')
  self.now+=2
  for i,p in enumerate((self.a,self.b)):self.state(p,RELAY['legs'][i]['start'])
  self.now+=1;self.s.relays.tick();self.assertEqual(run['phase'],'running')
  self.move(self.b,RELAY['legs'][0]['checkpoints'][0]);self.assertEqual(run['checkpoint'],0)
  self.move(self.b,RELAY['legs'][1]['start'])
  for point in RELAY['legs'][0]['checkpoints']:self.move(self.a,point)
  self.s.relays.tick();self.assertEqual(run['leg'],1)
  for point in RELAY['legs'][1]['checkpoints']:self.move(self.b,point)
  self.assertIsNone(self.s.relays._current('Alice'));self.assertEqual(self.s.db.execute('SELECT count(*) FROM relay_records').fetchone()[0],1)
 def test_missing_admission_never_counts_ready_or_arrival(self):
  self.s.races.publish(RACE);self.chat(self.a,'/guild race start regional_race')
  run=self.s.races.current('Alice');self.chat(self.b,'/guild race join '+run['id'])
  self.state(self.a,RACE['starts'][0]);self.al.pop('registry_digest')
  self.assertFalse(self.s.relays._fresh(self.a,self.now))
  with self.assertRaises(GuildError):self.s.races.command(self.a,['ready'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],0)
  self.al['registry_digest']=DIGEST;self.s.races.command(self.a,['leave'])
  self.assertFalse(self.s.races.runs)
 def test_default_and_bounds_reject_kanto_and_flags_share_validator(self):
  self.s.close();self.s=MemoryAuthority(self.root/'legacy-sock',self.root/'legacy')
  with self.assertRaises(ValueError):self.s.races.publish(RACE)
  with self.assertRaises(ValueError):self.s.relays.publish(RELAY)
  self.s.close();self.s=MemoryAuthority(self.root/'sock2',self.root/'world',combined_regions=True)
  bad=json.loads(json.dumps(RACE));bad['starts'][0][2]=24
  with self.assertRaises(ValueError):self.s.races.publish(bad)
  self.s.flags.publish(dict(id='regional_flags',title='Optional flag field',bases=[[38,0,5,8],[38,0,15,8]],limit=60,captures=1))
 def test_flag_capture_and_disconnect_have_distinct_outcomes(self):
  arena=dict(id='kanto_flags',title='Player chosen arena',bases=[[38,0,5,8],[38,0,15,8]],limit=60,captures=1)
  self.s.flags.publish(arena)
  def begin():
   self.chat(self.a,'/guild flag start kanto_flags');run=self.s.flags.current('Alice')
   self.chat(self.b,'/guild flag join '+run['id'])
   for i,p in enumerate((self.a,self.b)):
    self.state(p,arena['bases'][i]);self.chat(p,'/guild flag ready')
   self.now+=2
   for i,p in enumerate((self.a,self.b)):self.state(p,arena['bases'][i])
   self.now+=1;self.s.flags.tick();self.assertEqual(run['phase'],'playing')
   return run
  run=begin();self.state(self.b,[38,0,17,10])
  self.state(self.a,arena['bases'][1]);self.assertTrue(run['carrying'][0])
  self.state(self.a,arena['bases'][0]);self.assertEqual(run['scores'],[1,0])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM flag_results').fetchone()[0],1)
  run=begin();self.b['closing']=True;self.s.flags.tick()
  self.assertFalse(self.s.flags.runs);self.assertEqual(self.s.db.execute('SELECT count(*) FROM flag_results').fetchone()[0],1)
