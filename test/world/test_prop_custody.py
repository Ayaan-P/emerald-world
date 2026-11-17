from copy import deepcopy
import hashlib,json,unittest
from unittest.mock import patch
import test_actor_objects as fixture
from world import actor_runtime as runtime
from world.actor_objects import digest
from world.mechanics import Candidate

class CustodyTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ObjectTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  objects=deepcopy(self.s.objects);objects[-1]['portable']=True
  source=self.f.f.f.candidate.source.replace("'kind': 'prop'", "'kind': 'prop', 'portable': True")
  self.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
 def plan(self,actor,identity,tool,args):
  state=deepcopy(self.s.module_state);row=state['world_characters'][actor];row['version']+=1
  row['plan']=dict(id=identity,purpose='Use existing props without creating resources.',steps=[dict(id='act',tool=tool,args=args,after=[])])
  self.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def take(self):
  obj=next(o for o in self.s.objects if o['id']=='fixture')
  self.plan('harbor_guide','take','world.take_prop',dict(object='fixture',object_revision=digest(obj)))
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
 def test_take_restore_source_restart_place_and_reclaim_same_identity(self):
  self.take();self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['owner'],'harbor_guide')
  self.f.f.advance(1);self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.s.close();self.f.f.f.f.server=self.f.f.f.f.open();self.s=self.f.f.f.f.server;self.f.s=self.s;self.f.f.s=self.s;self.f.f.f.server=self.s;self.f.f.f.candidate=self.s.candidate
  self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.plan('harbor_guide','place','world.place_prop',dict(object='fixture',version=1,x=71,y=71))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  obj=next(o for o in self.s.objects if o['id']=='fixture');self.assertEqual((obj['x'],obj['y']),(71,71))
  self.f.f.advance(2);self.assertEqual(next(o for o in self.s.objects if o['id']=='fixture')['y'],71)
  self.plan('harbor_guide','reclaim','world.take_prop',dict(object='fixture',object_revision=digest(obj)))
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded');self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['version'],3)
 def test_other_actor_cannot_place_or_duplicate_owned_prop(self):
  self.take();self.plan('second','steal','world.place_prop',dict(object='fixture',version=1,x=73,y=70))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['owner'],'harbor_guide')
  self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
 def test_failed_receipt_rolls_back_custody_and_visible_object(self):
  obj=next(o for o in self.s.objects if o['id']=='fixture');self.plan('harbor_guide','take','world.take_prop',dict(object='fixture',object_revision=digest(obj)))
  original=runtime._receipt
  def fail(server,actor,row,plan,step,status,result):
   if status=='succeeded':raise ValueError('Injected custody receipt failure')
   return original(server,actor,row,plan,step,status,result)
  with patch.object(runtime,'_receipt',side_effect=fail):self.assertEqual(runtime.tick(self.s,now=10)['status'],'blocked')
  self.assertIn('fixture',[o['id'] for o in self.s.objects]);self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'],[])
 def test_collision_on_place_keeps_custody_and_revision_change_is_refused(self):
  self.take();peer=self.f.connect('Capable',True);self.f.f.f.send(peer,'CAVE GET');self.f.f.f.send(peer,'CAVE ACK '+self.s.shared_cave.identity);self.f.f.f.state(peer,*self.s.wilds_map,71,71)
  self.plan('harbor_guide','place','world.place_prop',dict(object='fixture',version=1,x=71,y=71))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'blocked');self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['owner'],'harbor_guide')
  from world.character_rebinding import prepare
  with self.assertRaises(ValueError):prepare(self.s,self.s.shared_cave.identity,'f'*64)

 def test_carried_prop_follows_real_navigation_then_places_same_identity(self):
  from world.character_actions import compile_actions
  self.take()
  def author(identity,tool,args,tick):
   row=self.s.module_state['world_characters']['harbor_guide'];obj=next(o for o in self.s.objects if o['id']=='harbor_guide')
   plan=dict(id=identity,purpose='Transport the same existing prop.',steps=[dict(id='act',tool=tool,args=args,after=[])])
   action=dict(id='harbor_guide',expected_version=row['version'],evidence=row['evidence'],reason='Choose another supported action.',changes=dict(plan=plan),object=obj)
   context=self.s.inspect();context['runtime']=dict(previous_source=self.s.candidate.source)
   context['recalled_history']=dict(events=[dict(json.loads(self.s.db.execute("SELECT data FROM events WHERE seq=?",(seq,)).fetchone()[0]),seq=seq) for seq in row['evidence']])
   source=compile_actions([action],context);self.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.advance(tick)
  author('transport','world.navigate',dict(revision=self.s.shared_cave.identity,x=71,y=74),1)
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending');self.f.f.advance(2,True)
  for tick in range(3,12):self.f.f.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded');self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  author('place_there','world.place_prop',dict(object='fixture',version=1,x=72,y=74),12)
  self.assertEqual(runtime.tick(self.s,now=28)['status'],'succeeded')
  prop=next(o for o in self.s.objects if o['id']=='fixture');self.assertEqual((prop['x'],prop['y']),(72,74))
  self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['owner'],None)
 def test_placing_allows_another_adjacent_actor_to_take_same_prop(self):
  objects=deepcopy(self.s.objects);objects[1].update(x=72,y=71)
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  source+='def actor_interact'+self.s.candidate.source.split('def actor_interact',1)[1]
  self.f.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  self.take();self.plan('harbor_guide','offer_ground','world.place_prop',dict(object='fixture',version=1,x=72,y=70))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'succeeded')
  obj=next(o for o in self.s.objects if o['id']=='fixture')
  self.plan('second','take_existing','world.take_prop',dict(object='fixture',object_revision=digest(obj)))
  self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['owner'],'second')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_prop_custody').fetchone()[0],1)
