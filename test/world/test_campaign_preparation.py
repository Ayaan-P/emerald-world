import importlib.util,json,pathlib,sqlite3,subprocess,tempfile,unittest
from copy import deepcopy
import test_actor_tutors as fixture
from world.battle_campaigns import command,publish,active,install
from world import actor_shops,actor_tutors,actor_runtime
from world.guilds import GuildError

class PreparationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.TutorTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.a=self.f.f.peer(role='SOCIALCHAR1CORE1CHARSHOP1CHARTUTOR1')
  self.b=self.f.f.peer('Bob',role='SOCIALCHAR1CORE1CHARSHOP1CHARTUTOR1')
  for c in (self.a,self.b):self.sync(c,'a'*32)
  self.d=dict(id='prepare',title='Preparation choices',entry='first',nodes=dict(first=dict(opponent='may',win=['last'],loss=['last'],preparation={
   'defend':dict(actor='may',items=[1,28,114],move=164),
   'attack':dict(actor='may',items=[29],move=38)}),last=dict(opponent='may',win=[],loss=[])))
  with self.s.db:
   publish(self.s,'may',{},dict(campaign=json.dumps(self.d)))
   actor_shops.configure(self.s,'may',{},dict(items='[1]'))
   actor_tutors.configure(self.s,'may',{},dict(move=102))
 def sync(self,c,run):
  self.assertIn('CORE RESULT',self.f.f.send(c,f'CORE {run} MILE 0 private'))
 def test_personal_native_descriptors_and_ordinary_services_unchanged(self):
  command(self.s,self.a,['start','prepare']);command(self.s,self.a,['prepare','defend'])
  a=self.s._snapshot(self.a);b=self.s._snapshot(self.b)
  self.assertIn('CHARACTER_SHOP may 1 1 3 1 28 114',a);self.assertIn('CHARACTER_TUTOR may 1 1 164',a)
  self.assertIn(' 1 1\n',b);self.assertTrue(actor_tutors.line(self.s,self.b,'may',1).endswith(' 102'))
  self.sync(self.a,'b'*32);self.assertTrue(actor_tutors.line(self.s,self.a,'may',1).endswith(' 102'))
  self.sync(self.a,'a'*32);self.assertTrue(actor_tutors.line(self.s,self.a,'may',1).endswith(' 164'))
  command(self.s,self.a,['leave']);self.assertTrue(actor_tutors.line(self.s,self.a,'may',1).endswith(' 102'))
 def test_real_battle_closes_camp_and_next_route_resets_choice(self):
  command(self.s,self.a,['start','prepare']);command(self.s,self.a,['prepare','attack'])
  seq=self.a['seq']+1
  self.assertIn('CHARACTER_BATTLE',self.f.f.send(self.a,f'CHARACTER_CHALLENGE {seq} may 1'))
  with self.assertRaises(GuildError):command(self.s,self.a,['prepare','defend'])
  self.f.f.send(self.a,f'CHARACTER_RESULT {seq} may 1 1')
  self.assertTrue(actor_tutors.line(self.s,self.a,'may',1).endswith(' 102'))
  command(self.s,self.a,['choose','last']);self.assertNotIn('preparation',active(self.s,self.a)[1])
 def test_restart_preserves_selected_offer_without_claiming_teaching(self):
  command(self.s,self.a,['start','prepare']);command(self.s,self.a,['prepare','defend'])
  before=actor_tutors.line(self.s,self.a,'may',1)
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   install(db);self.assertEqual(actor_tutors.line(self.s,self.a,'may',1),before)
   command(self.s,self.a,['prepare','defend'])
   self.assertEqual(db.execute('SELECT count(*) FROM campaign_preparation_choices').fetchone()[0],1)
   self.assertEqual(db.execute('SELECT count(*) FROM character_training').fetchone()[0],0)
  finally:self.s.db=old;db.close()
 def test_actual_native_shop_and_tutor_menus(self):
  command(self.s,self.a,['start','prepare']);command(self.s,self.a,['prepare','defend'])
  for name,root,wire in [('shop','native-npc-retail',actor_shops.line(self.s,self.a,'may',1)),('tutor','native-npc-tutoring',actor_tutors.line(self.s,self.a,'may',1))]:
   path=pathlib.Path('..',root,'tests','test_retail.py' if name=='shop' else 'test_tutoring.py').resolve()
   if not path.exists():self.skipTest('Exact native source unavailable')
   spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   with tempfile.TemporaryDirectory() as d:subprocess.run([str(m.build(d,wire))],check=True,capture_output=True)
 def test_agent_plan_publishes_preparation_and_legacy_refuses_choice(self):
  d=deepcopy(self.d);d['id']='agent';d['nodes']['first']['preparation'].pop('attack')
  c=self.s.module_state['world_characters']['may'];c['plan']=dict(id='plan',purpose='Offer preparation.',steps=[dict(id='publish',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(d,separators=(',',':'))),after=[])])
  actor_runtime.validate(c['plan']);self.assertEqual(actor_runtime.tick(self.s,now=10)['status'],'succeeded')
  command(self.s,self.a,['start','agent']);self.a['character_tutor_capable']=False
  with self.assertRaises(GuildError):command(self.s,self.a,['prepare','defend'])
  self.assertNotIn('preparation',active(self.s,self.a)[1])
 def test_invalid_services_and_private_command_entry(self):
  d=deepcopy(self.d);d['id']='bad';d['nodes']['first']['preparation']['defend']['items']=[9999]
  with self.assertRaises(ValueError):publish(self.s,'may',{},dict(campaign=json.dumps(d)))
  self.s.guild_chat.handle(self.a,'/guild campaign start prepare')
  self.s.guild_chat.handle(self.a,'/guild campaign prepare defend')
  self.assertEqual(active(self.s,self.a)[1]['preparation'],'defend')
