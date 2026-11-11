import json,sqlite3,time,unittest
from copy import deepcopy
import test_object_networks as fixture
from world import actor_objects,campaign_mechanisms as mechanisms
from world.actor_objects import digest
from world.battle_campaigns import publish,command,active,install
from world.campaign_board import rows,handle
from world.guilds import GuildError

class MechanismCampaignTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NetworkTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.install();self.s=self.f.s
  self.base=self.f.f.f.f.f
  self.a=self.peer('Witness');self.b=self.peer('Partner')
  goal=dict(network='mechanism',phase='on',definition=mechanisms.fingerprint(self.s,self.s.module_state['world_object_networks']['mechanism']),label='Change the shared mechanism')
  self.doc=dict(id='world_adventure',title='Reusable world adventure',entry='change',nodes=dict(change=dict(mechanism=goal,next=[])))
  with self.s.db:publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(self.doc)))
 def peer(self,name):
  p=self.f.f.f.connect(name,True);self.send(p,'CAVE GET');self.send(p,'CAVE ACK '+self.s.shared_cave.identity)
  self.base.state(p,*self.s.wilds_map,72,69);p['state'][4]=1;p['campaign_run']=('a' if name=='Witness' else 'b')*32
  return p
 def send(self,p,line):return self.base.send(p,line)
 def perform(self,p):
  p['last_interaction']=-10;p['state_time']=time.monotonic()
  self.send(p,'INTERACT_REGION %s fixture %s'%(p['seq']+1,self.s.shared_cave.identity))
  self.f.f.f.f.advance(1,True);actor_objects.poll_player(self.s)
 def check(self,p):
  p['state_time']=time.monotonic();return command(self.s,p,['mechanism-check'])
 def test_real_native_object_transition_then_board_completion(self):
  command(self.s,self.a,['start','world_adventure'])
  page=next(i for i,(_,a) in enumerate(rows(self.s,self.a)) if a==['mechanism-watch'])
  offer=handle(self.s,self.a,self.a['campaign_run'],'view',str(page))
  handle(self.s,self.a,self.a['campaign_run'],'pick',offer['token'])
  with self.assertRaises(GuildError):self.check(self.a)
  self.perform(self.b)
  self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['y'],72)
  self.check(self.a);data=active(self.s,self.a)[1]
  self.assertEqual(data['status'],'complete');self.assertEqual(data['history'][0]['basis'],'committed_world_transition_witness')
  self.assertEqual(data['history'][0]['attribution'],'shared_world_not_personal_action')
  with self.assertRaises(GuildError):self.check(self.a)
 def test_no_old_receipt_no_rearm_or_wrong_location_or_revision(self):
  self.perform(self.b);command(self.s,self.a,['start','world_adventure']);command(self.s,self.a,['mechanism-watch'])
  with self.assertRaises(GuildError):self.check(self.a)
  with self.assertRaises(GuildError):command(self.s,self.a,['mechanism-watch'])
  self.perform(self.b);self.perform(self.b)
  self.a['state'][2]=60
  with self.assertRaises(GuildError):self.check(self.a)
  self.a['state'][2]=72
  saved=deepcopy(self.s.module_state['world_object_networks']['mechanism']);self.s.module_state['world_object_networks']['mechanism']['program']['initial']='on'
  with self.assertRaises(GuildError):self.check(self.a)
  self.s.module_state['world_object_networks']['mechanism']=saved
  self.check(self.a)
 def test_party_independent_watch_and_persistent_receipt(self):
  command(self.s,self.a,['share','world_adventure']);group=active(self.s,self.a)[1]['shared']
  command(self.s,self.b,['join',group]);command(self.s,self.a,['begin'])
  command(self.s,self.a,['mechanism-watch']);command(self.s,self.b,['mechanism-watch']);self.perform(self.b)
  copy=sqlite3.connect(':memory:');self.s.db.backup(copy);old=self.s.db;self.s.db=copy
  try:
   install(copy);self.check(self.a);self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
   self.check(self.b);self.assertEqual(active(self.s,self.a)[1]['status'],'complete')
  finally:self.s.db=old;copy.close()
 def test_reversal_and_rejected_action_do_not_satisfy(self):
  command(self.s,self.a,['start','world_adventure']);command(self.s,self.a,['mechanism-watch'])
  self.perform(self.b);self.perform(self.b)
  with self.assertRaises(GuildError):self.check(self.a)
  self.assertEqual(active(self.s,self.a)[1]['history'],[])
 def test_definition_unknown_phase_and_routes_validation(self):
  for field,value in [('definition','0'*64),('phase','invented'),('network','missing')]:
   bad=deepcopy(self.doc);bad['nodes']['change']['mechanism'][field]=value
   with self.assertRaises(ValueError):publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(bad)))
 def test_occupied_transition_has_no_object_or_campaign_receipt(self):
  command(self.s,self.a,['start','world_adventure']);command(self.s,self.a,['mechanism-watch'])
  self.base.state(self.a,*self.s.wilds_map,72,72)
  before=self.s.db.execute('SELECT count(*) FROM campaign_mechanism_receipts').fetchone()[0]
  with self.assertRaises(AssertionError):self.perform(self.b)
  actor_objects.poll_player(self.s)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM campaign_mechanism_receipts').fetchone()[0],before)
  self.assertEqual(self.s.module_state['world_object_network_state']['mechanism']['phase'],'off')
  self.assertEqual(active(self.s,self.a)[1]['history'],[])
 def test_catalog_binding_region_change_and_save_lineage(self):
  cat=mechanisms.catalog(self.s);self.assertEqual(cat[0]['definition'],self.doc['nodes']['change']['mechanism']['definition'])
  command(self.s,self.a,['start','world_adventure']);command(self.s,self.a,['mechanism-watch'])
  self.a['campaign_run']='c'*32
  with self.assertRaises(GuildError):self.check(self.a)
  self.a['campaign_run']='a'*32
  obj=next(o for o in self.s.objects if o['id']=='fixture');old=obj['region_revision'];obj['region_revision']='f'*64
  try:
   with self.assertRaises(GuildError):self.check(self.a)
  finally:obj['region_revision']=old
