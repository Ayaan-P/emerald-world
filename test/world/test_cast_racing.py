"""Existing cast -> independently authored course -> voluntary actual field race."""
import json,time,unittest
from unittest.mock import patch
import test_cast_world_cooperation as fixture
from test_shared_races import COURSE
from world import actor_cooperation,actor_runtime

class CastRacingTests(unittest.TestCase):
 def test_independent_author_course_can_be_played_without_publicizing_results(self):
  f=fixture.CastWorldWorkTests();f.setUp();self.addCleanup(f.doCleanups);s=f.s
  result=f.act('canon_rydel','actor.request_work',dict(target='researcher',purpose='Consider an optional field course.',tool='world.publish_race',where=json.dumps(dict(outcome='race_course_published',course=COURSE['id']))))
  self.assertEqual(result['status'],'succeeded');request=actor_cooperation.discover(s)[0]['id']
  self.assertNotIn('plan',actor_runtime.actor_records(s)['researcher'])
  self.assertEqual(f.act('researcher','world.respond_cooperation',dict(request=request,decision='accept'))['status'],'succeeded')
  self.assertEqual(f.act('researcher','world.publish_race',dict(course=json.dumps(COURSE)))['status'],'succeeded')
  receipt=s.db.execute("SELECT max(seq) FROM actor_tool_receipts WHERE actor='researcher'").fetchone()[0]
  self.assertEqual(f.act('researcher','world.deliver_cooperation',dict(request=request,receipt=receipt))['status'],'succeeded')
  self.assertEqual(s.races.runs,{})
  self.assertEqual(s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],0)
  self.assertEqual(s.inspect()['actor_runtime']['race_courses'],[COURSE])
  baseline=s.memory.history()['events'];xp=s.db.execute('SELECT xp FROM guild_stats').fetchall()
  peers=[]
  for name in ('Alice','Bob'):
   identity=s.create_identity(name);s.peers.pop(name,None)
   c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
   s._line(c,('HELLO 1 '+name+' '+identity['token']+' SOCIALCHATCOMMANDS1MOUNTS1').encode())
   self.assertEqual(c['id'],name);peers.append(c)
  def chat(c,text):
   c['out'].clear();s._line(c,('CHAT '+str(c['seq']+1)+' * '+text.encode().hex()).encode())
   self.assertFalse(c['closing'])
  def state(c,p):
   s._line(c,('STATE '+str(c['seq']+1)+' '+' '.join(map(str,p))+' 1 7 1 '+'a'*16+' '+'b'*16).encode())
   self.assertFalse(c['closing'])
  now=[time.monotonic()];s.races.clock=lambda:now[0];s.relays.clock=lambda:now[0]
  with patch('time.monotonic',side_effect=lambda:now[0]):
   chat(peers[0],'/guild play start race '+COURSE['id']);run=s.races.current('Alice');self.assertIsNotNone(run)
   chat(peers[0],'/guild play share race');chat(peers[1],'/guild play join Alice')
   for c,p in zip(peers,COURSE['starts']):state(c,p);chat(c,'/guild race ready')
   self.assertEqual(run['phase'],'countdown');now[0]+=3
   for c,p in zip(peers,COURSE['starts']):state(c,p)
   s.races.tick();self.assertEqual(run['phase'],'running')
   for p in COURSE['checkpoints']*COURSE['laps']:
    for c in reversed(peers):now[0]+=0.1;state(c,p)
  self.assertEqual(s.db.execute('SELECT count(*) FROM race_results').fetchone()[0],2)
  self.assertIsNone(s.races.current('Alice'))
  # Publication/work receipts remain public, personal recreation does not become
  # verified campaign history, an NPC achievement, or experience-point income.
  self.assertEqual(s.memory.history()['events'],baseline)
  self.assertEqual(s.db.execute('SELECT xp FROM guild_stats').fetchall(),xp)
  self.assertNotIn('race_results',s.inspect()['actor_runtime'])
