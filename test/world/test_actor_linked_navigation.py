import hashlib,json,time,unittest
from copy import deepcopy
from world.mechanics import Candidate
from world import actor_runtime as runtime,cave_links
from world.actor_observation import observe
import test_actor_cave_travel

class LinkedNavigationTests(unittest.TestCase):
 def setUp(self):
  self.f=test_actor_cave_travel.ActorTravelTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.fx=self.f.fx
  blob=bytearray(self.s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(self.f.f.f.f.a,)).fetchone()[0]);blob[8+7*31+7]=ord('#')
  self.target=hashlib.sha256(blob).hexdigest()
  with self.s.db:
   self.s.db.execute('INSERT INTO generated_area_archive VALUES(?,?,?,?,?)',(self.target,'Third cave','cave',bytes(blob),int(time.time())))
   self.place=self.s._pin_region(self.target)['place_id']
  state=deepcopy(self.s.module_state);second=deepcopy(state['world_characters']['harbor_guide']);second.update(version=1,name='Link Keeper',object_id='keeper');state['world_characters']['keeper']=second
  original=next(o for o in self.s.objects if o['id']=='harbor_guide')
  keeper=dict(original,id='keeper',region_revision=self.f.f.habitat)
  door=dict(self.f.f.obj,id='next_door',region_revision=self.f.f.habitat,x=5,y=3)
  objects=self.s.objects+[keeper,door]
  source="def update(context,state):\n return dict(state=state,tiles=[],objects="+repr(objects)+")\n"
  self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.fx.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  entry=next(e for e in observe(self.s,'keeper',{},dict(radius=4))['entities'] if e['id']=='next_door')
  with self.s.db:cave_links.install(self.s,'keeper',{},dict(object='next_door',revision=entry['program_revision'],place=self.place,destination=self.target))
 def plan(self,actor='harbor_guide',x=8,y=6):
  state=deepcopy(self.s.module_state);a=state['world_characters'][actor];a['version']+=1
  a['plan']=dict(id='across',purpose='Reach my chosen destination.',steps=[dict(id='go',tool='world.navigate_places',args=dict(place=self.place,revision=self.target,x=x,y=y),after=[])])
  self.fx.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def mechanics(self,tick):
  self.s.tick=tick
  if self.s.deployment:
   _,path,_=self.s.deployment;source=path.read_text();self.s.deployment=None;self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  ns={};exec(self.fx.candidate.source,ns)
  self.fx.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)));self.assertIsNone(self.s.module_error)
 def test_three_places_real_legs_restart_and_one_persistent_identity(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending')
  restarted=False;complete=None
  for tick in range(1,100):
   result=runtime.tick(self.s,now=10+tick*6)
   self.mechanics(tick)
   saved=json.loads(self.s.db.execute('SELECT data FROM actor_linked_journeys').fetchone()[0])
   if saved['index']==1 and not restarted:
    self.s.close();self.fx.f.server=self.fx.f.open();self.s=self.fx.f.server;self.fx.server=self.s;self.fx.candidate=self.s.candidate;restarted=True
   if result and result['status']=='succeeded':complete=result;break
   if result and result['status']=='blocked':self.fail(str(self.s.inspect()['actor_runtime']['plans']))
  self.assertTrue(restarted);self.assertIsNotNone(complete)
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');self.assertEqual((obj['region_revision'],obj['x'],obj['y']),(self.target,8,6))
  saved=json.loads(self.s.db.execute('SELECT data FROM actor_linked_journeys').fetchone()[0])
  self.assertEqual(sum(l['kind']=='traverse' for l in saved['completed']),2)
  self.assertGreaterEqual(sum(l['kind']=='navigate' for l in saved['completed']),2)
  self.assertEqual(len([o for o in self.s.objects if o['id']=='harbor_guide']),1)
 def test_second_actor_and_different_destination(self):
  self.plan('keeper',9,4);runtime.tick(self.s,now=10)
  for tick in range(1,70):
   result=runtime.tick(self.s,now=10+tick*6);self.mechanics(tick)
   if result and result['status']=='succeeded':break
  else:self.fail('No arrival')
  obj=next(o for o in self.s.objects if o['id']=='keeper');self.assertEqual((obj['region_revision'],obj['x'],obj['y']),(self.target,9,4))
 def test_link_removed_before_execution_blocks_without_arrival(self):
  self.plan();runtime.tick(self.s,now=10)
  self.s.objects=[o for o in self.s.objects if o['id']!='door']
  result=runtime.tick(self.s,now=20);self.assertEqual(result['status'],'blocked')
  data=json.loads(self.s.db.execute('SELECT data FROM actor_linked_journeys').fetchone()[0])
  self.assertEqual(data['completed'],[]);self.assertIsNone(self.s.deployment)

 def test_withdrawn_plan_does_not_start_any_leg(self):
  self.plan();runtime.tick(self.s,now=10)
  state=deepcopy(self.s.module_state);a=state['world_characters']['harbor_guide'];a['version']+=1;a.pop('plan')
  self.fx.commit(dict(state=state,tiles=[],objects=self.s.objects))
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'blocked')
  self.assertIsNone(self.s.deployment)
  data=json.loads(self.s.db.execute('SELECT data FROM actor_linked_journeys').fetchone()[0]);self.assertEqual(data['completed'],[])
