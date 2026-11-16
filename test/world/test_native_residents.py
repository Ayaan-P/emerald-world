import copy,json,unittest
from unittest.mock import patch
import test_actor_population as fixture
from world import native_resident_population as residents,actor_runtime as runtime,population_agents
from world.native_resident_sites import catalog,connected

class ResidentTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PopulationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.f.f.plan()
 def definition(self,name='OldaleTown_House2',identity='visitor'):
  x,y=catalog()[name]['sites'][0]
  d=self.f.define(identity);d.pop('kind');d.update(x=x,y=y)
  return dict(map=name,definition=json.dumps(d,separators=(',',':')))
 def publish(self,args,now=10):
  state=copy.deepcopy(self.s.module_state);actor=state['world_characters']['harbor_guide'];actor['version']+=1
  actor['plan']=dict(id='native'+str(now),purpose='Create an original resident, not relocate a story actor.',steps=[dict(id='place',tool='world.populate_native',args=args,after=[])])
  self.f.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
  out=runtime.tick(self.s,now=now)
  if out['status']=='pending':self.f.admit();out=runtime.tick(self.s,now=now+6)
  return out
 def test_actual_native_object_character_chat_and_restart(self):
  result=self.publish(self.definition());self.assertEqual(result['status'],'succeeded')
  obj=next(o for o in self.s.objects if o['id']=='visitor');self.assertNotIn('region_revision',obj)
  peer=self.f.f.connect('Visitor').sock.conn;peer['character_capable']=True
  peer['state']=[obj['group'],obj['num'],obj['x']-1,obj['y'],1,7,1]
  import time
  peer['state_time']=time.monotonic()
  snap=self.s._snapshot(peer);self.assertIn('OBJECT visitor ',snap);self.assertIn('CHARACTER visitor 1',snap)
  from world.npc_conversations import command
  self.assertIn('delivered',command(self.s,peer,['say-public','visitor','Hello'])[0])
  event=next(e for e in self.s.memory.history()['events'] if e.get('tool')=='world.populate_native')
  self.assertTrue(population_agents.creation(event,'visitor'))
  self.s.close();base=self.f.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(next(o for o in self.s.objects if o['id']=='visitor'),obj)
  self.assertIsNone(runtime.tick(self.s,now=40))
 def test_two_distinct_residences_and_retained_projector(self):
  self.assertEqual(self.publish(self.definition())['status'],'succeeded')
  self.assertEqual(self.publish(self.definition('RustboroCity_House2','colleague'),30)['status'],'succeeded')
  self.assertEqual(len(self.s.module_state['world_native_residents']),2)
  self.assertEqual(self.s.candidate.source.count('def _ew_resident_project('),1)
 def test_collision_occupied_room_and_canonical_copy(self):
  self.assertEqual(self.publish(self.definition())['status'],'succeeded')
  self.assertEqual(self.publish(self.definition(identity='second'),30)['status'],'blocked')
  args=self.definition('RustboroCity_House2','steven_copy');d=json.loads(args['definition']);d['name']='Steven';args['definition']=json.dumps(d)
  self.assertEqual(self.publish(args,50)['status'],'blocked')
 def test_unsafe_or_occupied_map_never_stages(self):
  args=self.definition();d=json.loads(args['definition']);d.update(x=0,y=0);args['definition']=json.dumps(d)
  self.assertEqual(self.publish(args)['status'],'blocked');self.assertIsNone(self.s.deployment)
  args=self.definition();entry=catalog()[args['map']];peer=self.f.f.connect('Other').sock.conn;peer['state']=[entry['group'],entry['num'],0,0,1,7,0]
  self.assertEqual(self.publish(args,30)['status'],'blocked')
 def test_anchor_and_terrain_cannot_be_rewritten_after_admission(self):
  self.publish(self.definition());state=copy.deepcopy(self.s.module_state)
  state['world_native_residents']={}
  with self.assertRaises(ValueError):residents.validate(self.s,self.s.objects,state)
  obj=next(o for o in self.s.objects if o['id']=='visitor');moved=copy.deepcopy(self.s.objects);next(o for o in moved if o['id']=='visitor')['x']+=1
  with self.assertRaises(ValueError):residents.validate(self.s,moved,self.s.module_state)
  with self.assertRaises(ValueError):self.s._validated(dict(state=self.s.module_state,objects=self.s.objects,tiles=[dict(group=obj['group'],num=obj['num'],x=0,y=0,metatile=0,collision=0)]))
 def test_catalog_pin_and_connectivity_fail_closed(self):
  self.assertGreaterEqual(len(catalog()),2)
  import tempfile
  from pathlib import Path
  from world import native_resident_sites
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'native_resident_sites.json'
   path.write_text(native_resident_sites.PATH.read_text())
   traits=json.loads(native_resident_sites.PATH.with_name('encounter_traits.json').read_text())
   traits['engine_commit']='0'*40
   path.with_name('encounter_traits.json').write_text(json.dumps(traits))
   with patch.object(native_resident_sites,'PATH',path):
    with self.assertRaises(ValueError):catalog()
    self.assertEqual(residents.discover(self.s)['maps'],{})
  self.assertFalse(connected({(1,1),(3,1)}));self.assertTrue(connected({(1,1),(2,1),(3,1)}))
