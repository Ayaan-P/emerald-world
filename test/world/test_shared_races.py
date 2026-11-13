import json,unittest
from copy import deepcopy
from world.shared_races import validate
from world import actor_runtime
import test_field_relays as fixtures

COURSE=dict(id='test_race',title='Open Field Circuit',starts=[[0,0,10,10],[0,0,11,10]],checkpoints=[[0,0,10,12],[0,0,18,13]],laps=2,limit=180,mounted=False)
def connect(self,name):
  who=self.s.create_identity(name);c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s._line(c,f"HELLO 1 {who['id']} {who['token']} SOCIALCHATCOMMANDS1MOUNTS1".encode());self.assertEqual(c['id'],name);c['out'].clear();return c
class RaceTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.FieldRelayTests();self.f.connect=connect.__get__(self.f);self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.s.races.clock=lambda:self.f.now;self.mounted=False;self.ordinary=self.f.state;self.f.state=self.state
  with self.s.db:self.s.races.publish(COURSE)
 def state(self,c,point,trail='.',species=78):
  if not self.mounted:return self.ordinary(c,point)
  self.s._line(c,f"MSTATE {c['seq']+1} {' '.join(map(str,point))} 1 7 1 {'a'*16} {'b'*16} {species} 0 {trail}".encode())
  self.assertFalse(c['closing']);self.assertEqual(c['state'][:4],point)
 def start(self,mounted=False):
  course=deepcopy(COURSE)
  if mounted:
   course.update(id='mount_race',mounted=True);self.mounted=True
   with self.s.db:self.s.races.publish(course)
  self.f.chat(self.f.a,'/guild play start race '+course['id']);r=self.s.races.current('Alice');self.assertIsNotNone(r)
  self.f.chat(self.f.a,'/guild play share race');self.assertTrue(any('race' in x for x in self.f.chat(self.f.b,'/guild play open')))
  self.f.chat(self.f.b,'/guild play join Alice')
  for i,c in enumerate((self.f.a,self.f.b)):self.f.state(c,course['starts'][i]);self.f.chat(c,'/guild race ready')
  self.assertEqual(r['phase'],'countdown');self.f.now+=2
  for i,c in enumerate((self.f.a,self.f.b)):self.f.state(c,course['starts'][i])
  self.f.now+=1;self.s.races.tick();self.assertEqual(r['phase'],'running');return r
 def move(self,c,point):
  self.f.now+=0.2
  other=self.f.b if c is self.f.a else self.f.a
  self.f.state(other,other['state'][:4]);self.f.state(c,point)
 def test_both_run_independently_laps_results_and_private_restart(self):
  r=self.start()
  self.move(self.f.b,COURSE['checkpoints'][1]);self.assertEqual(r['progress']['Bob']['index'],0)
  # Bob can progress first; there is no baton gate on Alice.
  self.move(self.f.b,COURSE['checkpoints'][0]);self.assertEqual(r['progress']['Bob']['index'],1);self.assertEqual(r['progress']['Alice']['index'],0)
  for p in [COURSE['checkpoints'][1],*COURSE['checkpoints']]:self.move(self.f.b,p)
  self.assertIsNotNone(r['progress']['Bob']['finished']);self.assertIsNone(r['progress']['Alice']['finished'])
  for p in COURSE['checkpoints']*2:self.move(self.f.a,p)
  self.assertIsNone(self.s.races.current('Alice'))
  rows=self.s.db.execute('SELECT trainer,splits FROM race_results').fetchall();self.assertEqual(len(rows),2);self.assertTrue(all(len(json.loads(r[1]))==4 for r in rows))
  self.assertTrue(any('test_race' in x for x in self.f.chat(self.f.b,'/guild race records')))
  self.assertTrue(any('No completed race times' in x for x in self.f.chat(self.f.c,'/guild race records')))
  self.s.close();self.f.s=fixtures.MemoryAuthority(self.f.root/'sock',self.f.root/'world');self.s=self.f.s
  self.assertEqual(self.s.races.runs,{});self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],2)
 def test_mount_trails_no_missing_visits_and_changed_mount_cancels(self):
  r=self.start(True)
  self.f.now+=0.2;self.state(self.f.a,[0,0,19,13],'/'.join(['10,11','10,12']+[f'{x},12' for x in range(11,19)]+['18,13','19,13']));self.s.races.tick()
  self.assertEqual(r['progress']['Alice']['index'],2)
  self.s.races.tick();self.assertEqual(r['progress']['Alice']['index'],2)
  self.state(self.f.a,[0,0,19,13],species=59);self.s.races.tick();self.assertIsNone(self.s.races.current('Alice'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],0)
 def test_disconnect_preserves_only_actual_finisher_and_activity_conflicts(self):
  r=self.start()
  self.assertTrue(any('race' in x.lower() for x in self.f.chat(self.f.a,'/guild relay start petalburg_relay1')))
  self.assertIsNone(self.s.relays._current('Alice'))
  for p in COURSE['checkpoints']*2:self.move(self.f.a,p)
  self.f.b['closing']=True;self.s.races.tick();self.assertIsNone(self.s.races.current('Alice'))
  self.assertEqual(self.s.db.execute('SELECT trainer FROM race_results').fetchall(),[('Alice',)])
 def test_validation_immutable_course_and_no_auto_results(self):
  for bad in [dict(laps=0),dict(starts=[COURSE['starts'][0]]),dict(checkpoints=[COURSE['checkpoints'][0]]*2),dict(starts=[[0,0,10,10],[0,0,100,100]])]:
   with self.assertRaises(ValueError):self.s.races.publish(dict(COURSE,**bad))
  with self.assertRaises(ValueError):self.s.races.publish(dict(COURSE,title='Changed'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],0)
 def test_four_players_share_course_without_baton_or_rewards(self):
  d=self.f.connect('Dave');self.f.chat(self.f.a,'/guild invite Dave');self.f.chat(d,'/guild accept Runners')
  course=dict(COURSE,id='four_race',laps=1,starts=[[0,0,10,10],[0,0,11,10],[0,0,10,11],[0,0,11,11]])
  with self.s.db:self.s.races.publish(course)
  peers=(self.f.a,self.f.b,self.f.c,d);self.f.chat(peers[0],'/guild race start four_race');r=self.s.races.current('Alice')
  for c in peers[1:]:self.f.chat(c,'/guild race join '+r['id'])
  for c,p in zip(peers,course['starts']):self.f.state(c,p);self.f.chat(c,'/guild race ready')
  self.f.now+=2
  for c,p in zip(peers,course['starts']):self.f.state(c,p)
  self.f.now+=1;self.s.races.tick();self.assertEqual(r['phase'],'running')
  for point in course['checkpoints']:
   for c in reversed(peers):self.f.now+=0.1;self.f.state(c,point)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],4)
  self.assertFalse(any(e.get('event')=='guild_goal_completed' for e in self.s.memory.history()['events']))

class RaceAuthorTests(unittest.TestCase):
 def test_actual_agent_plan_registers_playable_course_not_a_completed_race(self):
  import test_characters
  f=test_characters.CharacterLifecycleTests();f.setUp();self.addCleanup(f.tearDown);s=f.server
  self.assertIsNone(f.commit({'may':f.character},f.npc))
  c=dict(f.character,version=2,evidence=[s.revision],reason='Offer an open field competition.',plan=dict(id='organize',purpose='Create a course for willing racers.',steps=[dict(id='publish',tool='world.publish_race',args=dict(course=json.dumps(COURSE,separators=(',',':'))),after=[])]))
  self.assertIsNone(f.commit({'may':c},f.npc));self.assertEqual(actor_runtime.tick(s,now=10)['status'],'succeeded')
  self.assertEqual(s.races.course('test_race'),COURSE);self.assertEqual(s.races.runs,{})
  self.assertEqual(s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],0)
  self.assertTrue(any(e['kind']=='race' for e in s.activities.catalog()))
