import json,sqlite3,time,unittest
from copy import deepcopy
import test_battle_campaigns as fixture
from world.battle_campaigns import publish,command,active,install
from world.campaign_board import rows,handle
from world.guilds import GuildError

class VisitTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.BattleCampaignTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.a=self.f.a;self.b=self.f.f.bob
  self.f.sync(self.b,'b'*32)
  self.point=list(self.a['state'][:4])
  self.d=dict(id='journey',title='Open shared adventure',entry='arrival',nodes={
   'arrival':dict(visit=dict(label='Meeting point',point=self.point),next=['battle','quiet']),
   'battle':dict(opponent='field_researcher',win=['finish'],loss=['finish']),
   'quiet':dict(visit=dict(label='Optional stop',point=self.point),next=['finish']),
   'finish':dict(visit=dict(label='Return',point=self.point),next=[])})
  with self.s.db:publish(self.s,'field_researcher',{},dict(campaign=json.dumps(self.d)))
 def fresh(self,c):c['state']=list(self.a['state']);c['state_time']=time.monotonic()
 def check(self,c):self.fresh(c);return command(self.s,c,['check-in'])
 def test_native_board_checkin_branch_real_battle_and_finish(self):
  command(self.s,self.a,['start','journey']);self.fresh(self.a)
  page=next(i for i,(_,action) in enumerate(rows(self.s,self.a)) if action==['check-in'])
  wire=self.f.f.send(self.a,f'CORE {self.a["campaign_run"]} CAMP view {page} 1');tokens=wire.strip().split()
  self.assertEqual(tokens[:2],['CORE','REPLY'])
  self.assertIn('Check in',bytes.fromhex(tokens[10]).decode())
  self.f.f.send(self.a,f'CORE {self.a["campaign_run"]} CAMP pick {tokens[9]} 2')
  self.assertEqual(active(self.s,self.a)[1]['choices'],['battle','quiet'])
  command(self.s,self.a,['choose','battle']);self.f.battle(1)
  command(self.s,self.a,['choose','finish']);self.check(self.a)
  data=active(self.s,self.a)[1];self.assertEqual(data['status'],'complete')
  self.assertEqual([x['basis'] for x in data['history']],['voluntary_fresh_client_presence','client_attested','voluntary_fresh_client_presence'])
  self.assertEqual(self.f.f.fixture.stats(),(0,0,0))
 def test_party_waits_for_each_save_and_speaker_decides(self):
  command(self.s,self.a,['share','journey']);key=active(self.s,self.a)[1]['shared']
  command(self.s,self.b,['join',key]);command(self.s,self.a,['begin'])
  self.check(self.a);self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
  with self.assertRaises(GuildError):self.check(self.a)
  self.check(self.b);self.assertEqual(active(self.s,self.a)[1]['status'],'choice')
  command(self.s,self.b,['advise','battle'])
  with self.assertRaises(GuildError):command(self.s,self.b,['choose','battle'])
  command(self.s,self.a,['choose','quiet']);self.assertEqual(active(self.s,self.b)[1]['node'],'quiet')
 def test_stale_wrong_tile_busy_and_save_isolation_restart(self):
  command(self.s,self.a,['start','journey']);self.a['state_time']=0
  with self.assertRaises(GuildError):command(self.s,self.a,['check-in'])
  self.fresh(self.a);self.a['state'][2]+=1
  with self.assertRaises(GuildError):command(self.s,self.a,['check-in'])
  self.a['state'][2]-=1;self.a['state'][6]=0
  with self.assertRaises(GuildError):command(self.s,self.a,['check-in'])
  self.a['state'][6]=1;self.check(self.a)
  self.f.sync(self.a,'c'*32);self.assertIsNone(active(self.s,self.a));self.f.sync(self.a,'a'*32)
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:install(db);self.assertEqual(active(self.s,self.a)[1]['status'],'choice');self.assertIsNone(active(self.s,self.b))
  finally:self.s.db=old;db.close()
 def test_generated_alias_and_unreachable_graph_rejected(self):
  bad=deepcopy(self.d);bad['id']='bad';bad['nodes']['arrival']['visit']['point']=[*self.s.cave_map,1,1]
  with self.assertRaises(ValueError):publish(self.s,'field_researcher',{},dict(campaign=json.dumps(bad)))
  bad=deepcopy(self.d);bad['id']='cycle_visit';bad['nodes']['finish']['next']=['arrival']
  with self.assertRaises(ValueError):publish(self.s,'field_researcher',{},dict(campaign=json.dumps(bad)))

 def test_agent_plan_publishes_mixed_graph_without_claiming_completion(self):
  from world import actor_runtime as runtime
  d=deepcopy(self.d);d['id']='authored_journey'
  plan=dict(id='author_trip',purpose='Offer an open adventure.',steps=[dict(id='publish',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(d,separators=(',',':'))),after=[])])
  runtime.validate(plan);self.s.module_state['world_characters']['field_researcher']['plan']=plan
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  command(self.s,self.a,['start','authored_journey'])
  self.assertEqual(active(self.s,self.a)[1]['history'],[])
