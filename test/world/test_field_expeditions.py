import json,sqlite3,time,unittest
from copy import deepcopy
import test_campaign_mechanisms as fixture
from world import field_expeditions as expeditions
from world.battle_campaigns import publish,command,active
from world.shared_campaigns import load
from world.campaign_board import rows,handle
from world.guilds import GuildError

class ExpeditionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.MechanismCampaignTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.a=self.f.a;self.b=self.f.b
  goal=deepcopy(self.f.doc['nodes']['change']['mechanism']);goal.pop('phase')
  goal['resolutions']={'on':dict(label='Open the linked panel',next=['follow']), 'off':dict(label='Restore the linked panel',next=[])}
  self.doc=dict(id='expedition',title='An authored field expedition',entry='field',nodes=dict(field=dict(expedition=goal),follow=self.f.doc['nodes']['change']))
  with self.s.db:publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(self.doc)))
 def start(self,shared=True):
  command(self.s,self.a,['share' if shared else 'start','expedition'])
  if shared:
   self.group=active(self.s,self.a)[1]['shared'];command(self.s,self.b,['join',self.group]);command(self.s,self.a,['begin'])
 def ready(self,p):command(self.s,p,['expedition-ready'])
 def check(self,p,phase):
  p['state_time']=time.monotonic();return command(self.s,p,['expedition-check',phase])
 def test_party_readies_then_real_change_selects_only_its_route(self):
  self.start();self.ready(self.a);self.ready(self.b);self.f.perform(self.b)
  self.check(self.a,'on');self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
  self.check(self.b,'on')
  self.assertEqual(load(self.s,self.group)['choices'],['follow'])
  for p in (self.a,self.b):
   data=active(self.s,p)[1];self.assertEqual(data['choices'],['follow']);self.assertEqual(data['history'][0]['phase'],'on')
  command(self.s,self.a,['choose','follow']);self.assertEqual(active(self.s,self.a)[1]['node'],'follow')
 def test_early_one_way_change_not_misattributed_and_readiness_survives_restart(self):
  self.start();self.ready(self.a);self.f.perform(self.b)
  with self.assertRaises(GuildError):self.check(self.a,'on')
  self.ready(self.b)
  with self.assertRaises(GuildError):self.check(self.a,'on')
  copy=sqlite3.connect(':memory:');self.s.db.backup(copy);old=self.s.db;self.s.db=copy
  try:
   self.f.perform(self.b);self.check(self.a,'off');self.check(self.b,'off')
   self.assertEqual(active(self.s,self.a)[1]['status'],'complete')
   self.assertEqual(load(self.s,self.group)['expedition']['phase'],'off')
  finally:self.s.db=old;copy.close()
 def test_no_divergent_party_resolution_after_first_witness(self):
  self.start();self.ready(self.a);self.ready(self.b);self.f.perform(self.b);self.check(self.a,'on');self.f.perform(self.b)
  with self.assertRaises(GuildError):self.check(self.b,'off')
  self.assertEqual(active(self.s,self.b)[1]['history'],[])
  self.f.perform(self.b);self.check(self.b,'on');self.assertEqual(active(self.s,self.b)[1]['choices'],['follow'])
 def test_private_alternative_and_no_retroactive_initial_phase(self):
  self.start(False);self.ready(self.a)
  with self.assertRaises(GuildError):self.check(self.a,'off')
  self.f.perform(self.b);self.f.perform(self.b);self.check(self.a,'off')
  self.assertEqual(active(self.s,self.a)[1]['status'],'complete')
 def test_board_readiness_stale_tokens_and_target_phase_revalidation(self):
  self.start();page=next(i for i,(_,a) in enumerate(rows(self.s,self.a)) if a==['expedition-ready'])
  pending=handle(self.s,self.a,self.a['campaign_run'],'view',str(page));self.ready(self.b)
  with self.assertRaises(ValueError):handle(self.s,self.a,self.a['campaign_run'],'pick',pending['token'])
  self.ready(self.a);self.f.perform(self.b)
  page=next(i for i,(_,a) in enumerate(rows(self.s,self.a)) if a==['expedition-check','on'])
  pending=handle(self.s,self.a,self.a['campaign_run'],'view',str(page));self.f.perform(self.b)
  with self.assertRaises(GuildError):handle(self.s,self.a,self.a['campaign_run'],'pick',pending['token'])
 def test_stale_presence_wrong_revision_and_lineage_cannot_complete(self):
  self.start(False);self.ready(self.a);self.f.perform(self.b)
  self.a['state_time']=0
  with self.assertRaises(GuildError):command(self.s,self.a,['expedition-check','on'])
  self.a['campaign_run']='c'*32
  with self.assertRaises(GuildError):self.check(self.a,'on')
  self.a['campaign_run']='a'*32
  self.s.module_state['world_object_networks']['mechanism']['program']['initial']='on'
  with self.assertRaises(GuildError):self.check(self.a,'on')
 def test_invalid_outcome_and_cycles_rejected(self):
  for mutation in ('phase','cycle','route','label'):
   doc=deepcopy(self.doc);doc['id']='bad_'+mutation;goal=doc['nodes']['field']['expedition']
   if mutation=='phase':goal['resolutions']['missing']=goal['resolutions'].pop('on')
   if mutation=='cycle':goal['resolutions']['on']['next']=['field']
   if mutation=='route':goal['resolutions']['on']['next']=['absent']
   if mutation=='label':goal['resolutions']['on']['label']='x'*41
   with self.assertRaises(ValueError):publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(doc)))
 def test_cancel_does_not_reset_world_or_leave_active_party(self):
  self.start();self.ready(self.a);self.ready(self.b);self.f.perform(self.b)
  command(self.s,self.a,['leave'])
  self.assertIsNone(active(self.s,self.a));self.assertIsNone(active(self.s,self.b))
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['phase'],'on')

 def test_agent_plan_publishes_outcomes_without_running_or_resetting_them(self):
  from world import actor_runtime as runtime
  doc=deepcopy(self.doc);doc['id']='agent_expedition'
  actor=self.s.module_state['world_characters']['harbor_guide']
  actor['plan']=dict(id='offer_expedition',purpose='Offer several real field outcomes.',steps=[dict(id='publish',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(doc,separators=(',',':'))),after=[])])
  runtime.validate(actor['plan'])
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'succeeded')
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['phase'],'off')
  command(self.s,self.a,['start','agent_expedition']);self.ready(self.a);self.f.perform(self.b);self.check(self.a,'on')
  self.assertEqual(active(self.s,self.a)[1]['choices'],['follow'])
