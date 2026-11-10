import json,sqlite3,time,unittest
from copy import deepcopy
import test_battle_campaigns as fixture
from world.battle_campaigns import publish,command,active,install,bind
from world.campaign_board import rows,handle
from world.shared_campaigns import load
from world.guilds import GuildError

class ParallelTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.BattleCampaignTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.a=self.f.a;self.b=self.f.f.bob;self.f.sync(self.b,'b'*32)
  self.point=list(self.a['state'][:4])
  self.doc=dict(id='split',title='Independent tasks',entry='divide',nodes={
   'divide':dict(roles={'battle':dict(opponent='field_researcher'),'travel':dict(visit=dict(label='Check the meeting point',point=self.point))},win=['regroup'],loss=['recover']),
   'regroup':dict(visit=dict(label='Regroup',point=self.point),next=[]),
   'recover':dict(opponent='field_researcher',win=[],loss=[])})
  self.publish(self.doc)
 def publish(self,d):
  with self.s.db:publish(self.s,'field_researcher',{},dict(campaign=json.dumps(d)))
 def start(self,key='split'):
  command(self.s,self.a,['share',key]);self.key=active(self.s,self.a)[1]['shared']
  command(self.s,self.b,['join',self.key]);command(self.s,self.a,['begin'])
 def check(self,c):
  c['state'][:4]=self.point;c['state_time']=time.monotonic();return command(self.s,c,['check-in'])
 def pick(self,c,role):return command(self.s,c,['role',role])
 def test_native_board_deploy_different_tasks_then_regroup(self):
  self.start();self.assertEqual(active(self.s,self.a)[1]['status'],'deploying')
  page=next(i for i,(_,act) in enumerate(rows(self.s,self.a)) if act==['role','battle'])
  wire=self.f.f.send(self.a,f'CORE {self.a["campaign_run"]} CAMP view {page} 1').strip().split()
  self.assertEqual(wire[:2],['CORE','REPLY']);self.f.f.send(self.a,f'CORE {self.a["campaign_run"]} CAMP pick {wire[9]} 2')
  self.assertEqual(active(self.s,self.a)[1]['role'],'battle')
  self.pick(self.b,'travel');self.assertEqual(active(self.s,self.a)[1]['status'],'ready')
  self.assertTrue(any('Check in' in text for text,_ in rows(self.s,self.b)))
  with self.assertRaises(GuildError):self.check(self.a)
  pending=dict(id='field_researcher');bind(self.s,self.b,pending);self.assertNotIn('campaign_binding',pending)
  replay=self.f.battle(1);self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
  self.check(self.b);self.assertEqual(load(self.s,self.key)['choices'],['regroup'])
  self.assertIn('CHARACTER_REJECT',self.f.f.send(self.a,replay))
  self.assertEqual(active(self.s,self.a)[1]['history'][0]['role'],'battle')
  self.assertEqual(active(self.s,self.b)[1]['history'][0]['basis'],'voluntary_fresh_client_presence')
  command(self.s,self.b,['advise','regroup'])
  with self.assertRaises(GuildError):command(self.s,self.b,['choose','regroup'])
  command(self.s,self.a,['choose','regroup'])
  self.assertNotIn('role',active(self.s,self.a)[1]);self.check(self.a);self.check(self.b)
  self.assertEqual(active(self.s,self.a)[1]['status'],'complete');self.assertEqual(self.f.f.fixture.stats(),(0,0,0))
 def test_claims_are_exclusive_and_stale_native_choices_fail(self):
  self.start();page=next(i for i,(_,act) in enumerate(rows(self.s,self.b)) if act==['role','battle'])
  response=handle(self.s,self.b,self.b['campaign_run'],'view',str(page));self.pick(self.a,'battle')
  with self.assertRaises(ValueError):handle(self.s,self.b,self.b['campaign_run'],'pick',response['token'])
  with self.assertRaises(GuildError):self.pick(self.b,'battle')
  with self.assertRaises(GuildError):self.pick(self.a,'travel')
  with self.assertRaises(GuildError):self.check(self.b)
  self.pick(self.b,'travel')
  with self.assertRaises(GuildError):self.pick(self.b,'travel')
 def test_restart_mid_deployment_and_waiting_save_isolation(self):
  self.start();self.pick(self.a,'battle')
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   install(db);self.assertEqual(active(self.s,self.a)[1]['role'],'battle');self.pick(self.b,'travel');self.check(self.b)
   self.f.sync(self.a,'c'*32);self.assertIsNone(active(self.s,self.a))
   with self.assertRaises(GuildError):self.pick(self.a,'battle')
   self.f.sync(self.a,'a'*32);self.f.battle(2)
   self.assertEqual(load(self.s,self.key)['choices'],['recover'])
  finally:self.s.db=old;db.close()
 def test_party_size_and_solo_reject_without_mutation(self):
  with self.assertRaises(GuildError):command(self.s,self.a,['start','split'])
  self.assertIsNone(active(self.s,self.a))
  self.assertNotIn(['start','split'],[action for _,action in rows(self.s,self.a)])
  self.assertTrue(any('2 trainers' in text and action==['share','split'] for text,action in rows(self.s,self.a)))
  command(self.s,self.a,['share','split']);key=active(self.s,self.a)[1]['shared'];command(self.s,self.b,['join',key])
  c=self.f.f.peer('Carol','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1');self.f.sync(c,'c'*32);command(self.s,c,['join',key])
  with self.assertRaises(GuildError):command(self.s,self.a,['begin'])
  self.assertEqual(load(self.s,key)['status'],'lobby');command(self.s,c,['leave']);self.assertIsNone(active(self.s,self.a))
 def test_declined_or_cancelled_battle_never_completes_role(self):
  self.start();self.pick(self.a,'battle');self.pick(self.b,'travel');self.f.battle(0)
  self.assertEqual(load(self.s,self.key)['results'],{});self.check(self.b)
  command(self.s,self.a,['leave']);self.assertIsNone(active(self.s,self.b));self.assertEqual(load(self.s,self.key)['status'],'cancelled')
 def test_author_runtime_discovers_and_publishes_split_graph(self):
  from world import actor_runtime as runtime
  d=deepcopy(self.doc);d['id']='agent_split'
  plan=dict(id='parallel_plan',purpose='Offer independent optional tasks.',steps=[dict(id='publish',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(d,separators=(',',':'))),after=[])])
  runtime.validate(plan);self.s.module_state['world_characters']['field_researcher']['plan']=plan
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded');self.start('agent_split')
  self.assertEqual(active(self.s,self.a)[1]['history'],[])
 def test_invalid_roles_and_generated_alias_rejected(self):
  for roles in ({'only':dict(opponent='field_researcher')},{'one':dict(opponent='absent'),'two':dict(opponent='field_researcher')},{'one':dict(visit=dict(label='Alias',point=[*self.s.cave_map,1,1])),'two':dict(opponent='field_researcher')}):
   d=deepcopy(self.doc);d['id']='invalid';d['nodes']['divide']['roles']=roles
   with self.assertRaises(ValueError):self.publish(d)
 def test_four_roles_two_locations_and_repeat_deployment(self):
  d=deepcopy(self.doc);d['id']='four';roles=d['nodes']['divide']['roles']
  second=list(self.point);second[2]+=1
  roles.update(other=dict(visit=dict(label='Other tile',point=second)),fourth=dict(visit=dict(label='Return point',point=self.point)))
  d['nodes']['regroup']=dict(roles=deepcopy(roles),win=[],loss=[]);self.publish(d)
  command(self.s,self.a,['share','four']);self.key=active(self.s,self.a)[1]['shared']
  c=self.f.f.peer('Carol','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1');e=self.f.f.peer('Drew','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1')
  self.f.sync(c,'c'*32);self.f.sync(e,'d'*32)
  for p in (self.b,c,e):command(self.s,p,['join',self.key])
  command(self.s,self.a,['begin'])
  for p,role in zip((self.a,self.b,c,e),('battle','travel','other','fourth')):self.pick(p,role)
  self.f.battle(1);self.check(self.b);self.check(e)
  c['state_time']=time.monotonic();c['state'][:4]=self.point
  with self.assertRaises(GuildError):command(self.s,c,['check-in'])
  c['state'][:4]=second;command(self.s,c,['check-in'])
  command(self.s,self.a,['choose','regroup'])
  self.assertEqual(load(self.s,self.key)['roles'],{})
  for p in (self.a,self.b,c,e):self.assertEqual(active(self.s,p)[1]['status'],'deploying');self.assertNotIn('role',active(self.s,p)[1])
 def test_role_preparation_uses_existing_shop_choice(self):
  from world.campaign_preparation import offer
  from world.actor_shops import ITEMS
  d=deepcopy(self.doc);d['id']='prep_split'
  d['nodes']['divide']['roles']['battle']['preparation']={'stock':dict(actor='field_researcher',items=[next(iter(ITEMS))],move=0)}
  self.publish(d);self.start('prep_split');self.pick(self.a,'battle');self.pick(self.b,'travel')
  self.a['character_shop_capable']=True;command(self.s,self.a,['prepare','stock'])
  self.assertEqual(offer(self.s,self.a,'field_researcher')['items'],d['nodes']['divide']['roles']['battle']['preparation']['stock']['items'])
  self.assertIsNone(offer(self.s,self.b,'field_researcher'))
  with self.assertRaises(GuildError):command(self.s,self.b,['prepare','stock'])

 def test_incompatible_later_party_size_is_not_publishable(self):
  d=deepcopy(self.doc);d['id']='wrong_sizes'
  d['nodes']['regroup']=dict(roles=deepcopy(d['nodes']['divide']['roles']),win=[],loss=[])
  d['nodes']['regroup']['roles']['third']=dict(opponent='field_researcher')
  with self.assertRaises(ValueError):self.publish(d)
