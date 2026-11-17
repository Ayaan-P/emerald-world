import importlib.util,pathlib,subprocess,tempfile,unittest
import test_campaign_preparation as fixture
from world.battle_campaigns import active,command

class BoardTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PreparationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.a=self.f.a;self.n=0
 def request(self,key='view',guard='0',conn=None,run=None):
  self.n+=1;c=conn or self.a
  wire=self.f.f.f.send(c,f'CORE {run or "a"*32} CAMP {key} {guard} {self.n}')
  return wire,wire.strip().split()
 def test_real_native_board_entry_start_prepare_route_and_leave(self):
  wire,t=self.request();self.assertEqual(t[:2],['CORE','REPLY']);self.assertEqual(bytes.fromhex(t[10]).decode(),'Start Preparation choices')
  path=pathlib.Path('../native-campaign-board/tests/test_campaign_board.py').resolve()
  if path.exists():
   spec=importlib.util.spec_from_file_location('native_board',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   with tempfile.TemporaryDirectory() as d:subprocess.run([str(m.build(d,wire))],check=True,capture_output=True)
  self.request('pick',t[9]);self.assertEqual(active(self.s,self.a)[1]['status'],'ready')
  _,t=self.request('view','3');self.assertIn('Prepare defend',bytes.fromhex(t[10]).decode())
  self.request('pick',t[9]);self.assertEqual(active(self.s,self.a)[1]['preparation'],'defend')
  self.assertIn('CHARACTER_TUTOR may 1',self.s._snapshot(self.a))
  # Ordinary NPC battle still supplies its real pending report, never a board victory button.
  seq=self.a['seq']+1;self.f.f.f.send(self.a,f'CHARACTER_CHALLENGE {seq} may 1');self.f.f.f.send(self.a,f'CHARACTER_RESULT {seq} may 1 1')
  _,t=self.request('view','1');self.assertIn('Take route last',bytes.fromhex(t[10]).decode());self.request('pick',t[9])
  self.assertEqual(active(self.s,self.a)[1]['node'],'last')
  _,t=self.request('view','2');self.assertIn('Leave campaign',bytes.fromhex(t[10]).decode());self.request('pick',t[9]);self.assertIsNone(active(self.s,self.a))
 def test_tokens_are_private_single_use_and_state_bound(self):
  _,t=self.request();token=t[9]
  self.assertIn('REFUSED',self.request('pick',token,conn=self.f.b)[0])
  self.request('pick',token);self.assertIn('REFUSED',self.request('pick',token)[0])
  _,t=self.request('view','2');command(self.s,self.a,['prepare','attack'])
  self.assertIn('REFUSED',self.request('pick',t[9])[0]);self.assertEqual(active(self.s,self.a)[1]['preparation'],'attack')
 def test_cancel_timeout_lineage_and_reconnect_do_not_execute(self):
  _,t=self.request();self.a['campaign_board']['until']=0
  self.assertIn('REFUSED',self.request('pick',t[9])[0]);self.assertIsNone(active(self.s,self.a))
  _,t=self.request();self.assertIn('REFUSED',self.request('pick',t[9],run='b'*32)[0])
  self.a.pop('campaign_board',None);self.assertIn('REFUSED',self.request('pick',t[9])[0])
  self.assertIsNone(active(self.s,self.a))
