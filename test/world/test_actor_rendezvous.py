import json,unittest
from copy import deepcopy
from world import actor_runtime as runtime
import test_actor_linked_navigation as fixture

class RendezvousTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.LinkedNavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,actor='harbor_guide',target='keeper'):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1
  c['plan']=dict(id='find_'+str(c['version']),purpose='Find another character to decide what to do together.',steps=[dict(id='seek',tool='world.rendezvous',args=dict(target=target),after=[])])
  self.f.fx.commit(dict(state=state,tiles=[],objects=self.s.objects));self.assertIsNone(self.s.module_error)
 def run_to_arrival(self,actor='harbor_guide',target='keeper',restart=False):
  self.plan(actor,target);self.assertEqual(runtime.tick(self.s,now=10)['status'],'pending');restarted=False
  for tick in range(1,100):
   result=runtime.tick(self.s,now=10+tick*6);self.f.mechanics(tick)
   if restart and tick==3:
    self.s.close();self.f.fx.f.server=self.f.fx.f.open();self.s=self.f.fx.f.server;self.f.s=self.s;self.f.fx.server=self.s;self.f.fx.candidate=self.s.candidate;restarted=True
   if result and result['status']=='blocked':self.fail(str(self.s.inspect()['actor_runtime']['plans']))
   if result and result['status']=='succeeded':break
  else:self.fail('No real rendezvous')
  objects={o['id']:o for o in self.s.objects};a,b=objects[actor],objects[target]
  self.assertEqual(a['region_revision'],b['region_revision']);self.assertEqual(abs(a['x']-b['x'])+abs(a['y']-b['y']),1)
  receipt=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor=? AND status='succeeded' ORDER BY seq DESC LIMIT 1",(actor,)).fetchone()[0])
  self.assertEqual(receipt['outcome'],'authority_rendezvous');self.assertEqual(receipt['target'],target)
  return receipt,restarted
 def test_cross_place_real_movement_restart_and_recipient_not_moved(self):
  old=deepcopy(next(o for o in self.s.objects if o['id']=='keeper'))
  receipt,restarted=self.run_to_arrival(restart=True)
  self.assertTrue(restarted);self.assertTrue(any(l['kind']=='traverse' for l in receipt['legs']))
  self.assertEqual(next(o for o in self.s.objects if o['id']=='keeper'),old)
  # Existing voluntary meeting operation now sees actual co-location.
  from world.actor_social import participants
  participants(self.s,'harbor_guide',dict(target='keeper',expected_version=receipt['target_version']))
  from world.actor_social import address
  with self.s.db:delivered=address(self.s,'harbor_guide',{},dict(target='keeper',expected_version=receipt['target_version'],text='I found you. Shall we talk?'))
  self.assertIsNotNone(delivered)
  self.assertTrue(any(e.get('event')=='character_encounter' for e in self.s.memory.history(limit=64)['events']))
 def test_unavailable_recipient_never_claims_meeting(self):
  self.plan();runtime.tick(self.s,now=10)
  self.s.objects=[o for o in self.s.objects if o['id']!='keeper']
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'blocked');self.assertIsNone(self.s.deployment)
 def test_second_actor_same_map_unseen_position(self):
  # A second independent character seeks the guide on an existing same-map tile.
  state=deepcopy(self.s.module_state);objects=deepcopy(self.s.objects)
  guide=next(o for o in objects if o['id']=='harbor_guide');keeper=next(o for o in objects if o['id']=='keeper')
  keeper.update(region_revision=guide['region_revision'],x=7,y=5)
  import hashlib
  from world.mechanics import Candidate
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
  self.f.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.fx.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error)
  result,_=self.run_to_arrival('keeper','harbor_guide');self.assertFalse(any(l['kind']=='traverse' for l in result['legs']))
 def test_recipient_changes_destination_between_real_legs(self):
  self.plan();runtime.tick(self.s,now=10);changed=False
  for tick in range(1,100):
   result=runtime.tick(self.s,now=10+tick*6);self.f.mechanics(tick)
   data=json.loads(self.s.db.execute('SELECT data FROM actor_rendezvous').fetchone()[0])
   if data['legs'] and data['active'] is None and not changed:
    state=deepcopy(self.s.module_state);state['world_characters']['keeper']['version']+=1
    objects=deepcopy(self.s.objects);next(o for o in objects if o['id']=='keeper').update(x=8,y=5)
    import hashlib
    from world.mechanics import Candidate
    source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(objects)+')\n'
    self.f.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.f.fx.commit(dict(state=state,tiles=[],objects=objects));self.assertIsNone(self.s.module_error);changed=True
   if result and result['status']=='blocked':self.fail(str(self.s.inspect()['actor_runtime']['plans']))
   if result and result['status']=='succeeded':break
  else:self.fail('No updated rendezvous')
  self.assertTrue(changed)
  receipt=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor='harbor_guide' AND status='succeeded' ORDER BY seq DESC LIMIT 1").fetchone()[0])
  self.assertEqual((receipt['target_x'],receipt['target_y']),(8,5))
