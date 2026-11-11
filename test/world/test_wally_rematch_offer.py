"""Actual canonical invitation -> native command -> authority, no invented result."""
import importlib.util,os,subprocess,tempfile,time,unittest
from pathlib import Path
from world import canonical_cast as cast
from world.build_catalog import catalog_maps
import test_canonical_cast as fixture
class WallyRematchOfferTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  a=self.f.action();a['id']='canon_wally';a['changes']['rematch']='wally_native';self.f.apply(a)
  self.p=self.f.peer();self.run='a'*32
  self.p['state'][:2]=next(p for p,m in catalog_maps().items() if m['name']=='VictoryRoad_1F')
 def request(self):return self.s.core_story.handle(self.p,['CORE',self.run,'REMATCH','wally','confirm'])
 def test_original_late_conversation_and_exact_author_invitation_required(self):
  with self.assertRaises(ValueError):self.request()
  reply=cast.response(self.s,self.p,self.run,'wally_vr');self.assertIn('rematch',reply['objective'])
  before=self.s.memory.history();self.assertTrue(self.request()['ok']);self.assertEqual(self.s.memory.history(),before)
  self.p['core_active_run']='b'*32
  with self.assertRaises(ValueError):self.request()
  self.p['core_active_run']=self.run;self.p['canonical_location']['expires']=0
  with self.assertRaises(ValueError):self.request()
  cast.response(self.s,self.p,self.run,'wally_vr')
  withdrawn=self.f.action(1);withdrawn['id']='canon_wally';self.f.apply(withdrawn)
  with self.assertRaises(ValueError):self.request()
 def test_native_command_admitted_without_completion_rewards_or_party_effect(self):
  root=os.environ.get('EW_NATIVE_SOURCE')
  if not root:self.skipTest('native source required')
  spec=importlib.util.spec_from_file_location('wally_native',Path(root)/'tests/test_wally_rematch.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as tmp:
   c=Path(tmp)/'t.c';c.write_text(m.controller_code());exe=Path(tmp)/'t'
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True,capture_output=True)
   lines=subprocess.check_output([str(exe)],text=True).splitlines()
  cast.response(self.s,self.p,self.run,'wally_vr');before=self.s.memory.history();self.p['out'].clear()
  line=next(x for x in lines if x.startswith('CORE '));self.s._line(self.p,line.encode())
  self.assertIn(' REMATCH wally OK',self.p['out'].decode());self.assertEqual(self.s.memory.history(),before)
  self.assertEqual(self.s.objects,[])
 def test_early_location_and_other_cast_cannot_enable_original_rematch(self):
  self.p['state'][:2]=next(p for p,m in catalog_maps().items() if m['name']=='VerdanturfTown_WandasHouse')
  cast.response(self.s,self.p,self.run,'wally')
  with self.assertRaises(ValueError):self.request()
  bad=self.f.action();bad['changes']['rematch']='wally_native'
  with self.assertRaisesRegex(ValueError,'Only Wally'):cast.compile_actions([bad],self.f.context())
