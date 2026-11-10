import json,pathlib,importlib.util,tempfile,subprocess,unittest,os
from unittest.mock import patch
import test_region_characters as fixture
from world import battle_watch

class BattleWatchTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.a=self.peer('Alice');self.b=self.peer('Bob');self.c=self.peer('Carol',False)
 def peer(self,name,cap=True):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} SOCIAL'+('CHAR1CHARPK1OUTBREAK1CONTEST1RENTALS1WORLDTV1CHARFORM1FISHING1WATCH1' if cap else '')))
  # Exercise the dormant protocol in component fixtures only. The real release
  # admission remains disabled and is covered by test_next_release_boundaries.
  p['battle_watch_capable']=cap
  return p
 def send(self,p,line):return self.f.send(p,line)
 def test_actual_native_stream_optional_view_no_history_or_outcomes(self):
  native=pathlib.Path(os.environ.get('EW_WATCH_NATIVE_SOURCE','../native-battle-spectating'))/'tests/test_watch.py'
  if not native.exists():self.skipTest('Native spectating source unavailable')
  spec=importlib.util.spec_from_file_location('native_watch',native.resolve());mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  with tempfile.TemporaryDirectory() as d:frame=subprocess.check_output([str(mod.build(d))],text=True).strip()
  before=self.s.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
  self.send(self.a,frame);self.assertFalse(self.a.get('watch_sharing'))
  self.assertIn('WATCH_PERMISSION 1',self.send(self.a,'WATCH SHARE 1'))
  self.send(self.b,'WATCH TARGET Alice');self.send(self.a,frame)
  view=next(l for l in self.s._snapshot(self.b).splitlines() if l.startswith('WATCH_VIEW'))
  decoded=[bytes.fromhex(h).decode() for h in view.split()[1:]]
  self.assertIn('RALTS',str(decoded));self.assertIn('23/30',str(decoded));self.assertIn('WINGULL',str(decoded))
  self.assertNotIn('WATCH_VIEW',self.s._snapshot(self.c));self.assertNotIn('WATCH_VIEW',self.s._snapshot(self.a))
  self.assertEqual(before,self.s.db.execute('SELECT COUNT(*) FROM events').fetchone()[0])
  self.assertNotIn('watch_frame',json.dumps(self.s.inspect()))
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(mod.build(d,view))],check=True,capture_output=True)
  self.send(self.a,'WATCH SHARE 0');self.assertNotIn('23/30',str(battle_watch.lines(self.s,self.b)))
 def test_stale_frames_disconnect_reconnect_and_legacy(self):
  self.send(self.a,'WATCH SHARE 1');self.send(self.b,'WATCH TARGET Alice')
  with patch('world.battle_watch.time.monotonic',return_value=100):self.send(self.a,'WATCH SOLO 1 2 0:280:12:23:30 1:278:15:40:40')
  with patch('world.battle_watch.time.monotonic',return_value=103):
   text=bytes.fromhex(battle_watch.lines(self.s,self.b)[0].split()[1]).decode()
   self.assertIn('waiting',text)
  # An identically named new connection is never silently subscribed.
  self.s.peers['Alice']=dict(self.a)
  self.assertIn('ended',bytes.fromhex(battle_watch.lines(self.s,self.b)[0].split()[1]).decode())
  self.assertNotIn('watch_target',self.b)
  self.send(self.c,'WATCH SHARE 1');self.assertFalse(self.c.get('watch_sharing'))
 def test_list_off_invalid_frame_and_replay(self):
  self.send(self.a,'WATCH SHARE 1');self.send(self.b,'WATCH LIST')
  self.assertIn('Alice',str([bytes.fromhex(x).decode() for x in battle_watch.lines(self.s,self.b)[0].split()[1:]]))
  self.send(self.b,'WATCH OFF');self.assertEqual(battle_watch.lines(self.s,self.b),[])
  self.send(self.a,'WATCH SOLO 1 2 0:280:12:23:30 1:278:15:40:40')
  self.send(self.a,'WATCH SOLO 1 2 0:280:12:23:30 1:278:15:40:40')
  self.assertFalse(self.a.get('watch_sharing'));self.assertNotIn('watch_frame',self.a)
  self.send(self.a,'WATCH SHARE 1');self.send(self.a,'WATCH SOLO 2 1 0:280:12:100:30')
  self.assertFalse(self.a['watch_sharing'])
  self.assertNotIn('watch_frame',self.a)
 def test_old_unfiltered_frame_is_refused_and_withdrawn(self):
  self.send(self.a,'WATCH SHARE 1');self.send(self.b,'WATCH TARGET Alice')
  self.send(self.a,'WATCH FRAME 1 1 1:280:12:23:30')
  self.assertFalse(self.a['watch_sharing']);self.assertNotIn('watch_frame',self.a)
  self.assertNotIn('RALTS',str(battle_watch.lines(self.s,self.b)))
