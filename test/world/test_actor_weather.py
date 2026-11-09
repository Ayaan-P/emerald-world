import unittest
from world import actor_weather as weather,actor_runtime
import test_region_characters

class WeatherTests(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.server;self.revision=self.f.enable_shared_xl()
 def peer(self,name='Alice',capable=True):
  token=self.s.create_identity(name)['token']
  p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  role='SOCIALCAVE16CHAR1CHARREG1'+('WEATHER1' if capable else '')
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} {role}'))
  self.f.state(p,0,9,8,8);self.f.send(p,'CAVE GET');self.f.send(p,'CAVE ACK '+self.revision)
  self.f.state(p,*self.s.wilds_map,70,70);return p
 def test_real_plan_persistent_weather_exact_scope_and_restore(self):
  peer=self.peer();old=self.peer('Old',False)
  c=dict(self.f.character,version=3,evidence=[self.s.memory.history()['events'][-1]['seq']],reason='Author a rainy outdoor atmosphere.',
   plan=dict(id='environment',purpose='Choose destination weather.',steps=[dict(id='rain',tool='world.set_weather',args=dict(revision=self.revision,mode='rain'),after=[])]))
  self.f.commit(dict(state={'world_characters':{'harbor_guide':c}},tiles=[],objects=[self.f.obj]))
  self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertIn('OUTDOOR_WEATHER '+self.revision,self.s._snapshot(peer))
  self.assertNotIn('OUTDOOR_WEATHER',self.s._snapshot(old))
  peer['cave_ack']='f'*64;self.assertIsNone(weather.line(self.s,peer))
  peer['cave_ack']=self.revision;self.f.state(peer,0,9,8,8);self.assertIsNone(weather.line(self.s,peer))
  self.s.close();self.f.f.server=self.f.f.open();self.s=self.f.f.server;self.f.server=self.s
  self.assertEqual(weather.current(self.s,self.revision)['mode'],'rain')
  with self.s.db:weather.configure(self.s,'harbor_guide',{},dict(revision=self.revision,mode='default'))
  self.assertEqual(weather.current(self.s,self.revision)['mode'],'default')
 def test_no_foreign_revision_cave_or_severe_story_weather(self):
  for args in (dict(revision='f'*64,mode='rain'),dict(revision=self.revision,mode='drought')):
   with self.assertRaises(ValueError):weather.configure(self.s,'harbor_guide',{},args)
  self.assertEqual(weather.current(self.s,self.revision)['mode'],'default')

 def test_actual_snapshot_to_native_weather_pump(self):
  import importlib.util,pathlib,tempfile,subprocess,os
  path=pathlib.Path(os.environ.get('EW_WEATHER_NATIVE_SOURCE','../native-shared-weather')).resolve()
  if not (path/'tests/test_weather.py').exists():self.skipTest('Exact weather native source unavailable')
  peer=self.peer()
  with self.s.db:weather.configure(self.s,'harbor_guide',{},dict(revision=self.revision,mode='rain'))
  wire=next(x for x in self.s._snapshot(peer).splitlines() if x.startswith('OUTDOOR_WEATHER '))
  spec=importlib.util.spec_from_file_location('weather_native',path/'tests/test_weather.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:subprocess.run([str(module.build(d,wire))],check=True,capture_output=True)
