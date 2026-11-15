import json,sqlite3,unittest
from copy import deepcopy
import test_actor_agreements as fixture
from world import npc_organizations as org,actor_agreements as agreements,shared_outbreaks
from world.battle_campaigns import publish,active
from world.guilds import GuildError

class OrganizationTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.AgreementTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.i=0
 def tool(self,a,t,args):
  self.i+=1;return self.f.run_tool(a,t,args,'organization_'+str(self.i))
 def found(self):
  self.assertEqual(self.tool('harbor_guide','world.found_organization',dict(id='field_society',name='Field Society',goal='Choose projects from actual local conditions.'))['status'],'succeeded')
 def join(self):
  self.assertEqual(self.tool('harbor_guide','world.invite_organization',dict(organization='field_society',target='other'))['status'],'succeeded')
  self.assertEqual(self.tool('other','world.decide_organization',dict(organization='field_society',decision='join'))['status'],'succeeded')
 def propose(self,campaign=''):
  self.assertEqual(self.tool('harbor_guide','world.propose_organization_project',dict(organization='field_society',purpose='Coordinate a native outbreak.',tool='world.configure_outbreak',args=json.dumps(self.f.f.args),hours=1,campaign=campaign))['status'],'succeeded')
  return self.s.db.execute('SELECT agreement FROM npc_organization_actions ORDER BY rowid DESC LIMIT 1').fetchone()[0]
 def test_independent_membership_agreement_real_effect_and_player_adventure(self):
  self.found();self.assertEqual(org.load(self.s,'field_society')['members'],['harbor_guide']);self.join()
  point=list(self.f.peer['state'][:4]);doc=dict(id='society_visit',title='Visit the current field',entry='visit',nodes=dict(visit=dict(visit=dict(label='Field meeting',point=point),next=[])))
  with self.s.db:publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(doc)))
  key=self.propose('society_visit');self.assertEqual(agreements.load(self.s,key)[1]['campaign'],'society_visit')
  with self.assertRaises(GuildError):org.command(self.s,self.f.peer,['field_society','play','society_visit'])
  self.assertEqual(self.tool('harbor_guide','world.commit_agreement',dict(agreement=key))['status'],'blocked')
  self.assertEqual(self.tool('other','world.decide_agreement',dict(agreement=key,decision='accept'))['status'],'succeeded')
  self.assertEqual(self.tool('harbor_guide','world.commit_agreement',dict(agreement=key))['status'],'succeeded')
  self.assertIn('WILD_OUTBREAK',self.s._snapshot(self.f.peer))
  self.f.peer['campaign_run']='a'*32
  org.command(self.s,self.f.peer,['field_society','play','society_visit']);self.assertEqual(active(self.s,self.f.peer)[1]['status'],'lobby')
  self.assertEqual(org.load(self.s,'field_society')['members'],['harbor_guide','other'])
  self.assertTrue(any('/guild org field_society play society_visit' in line for line in org.command(self.s,self.f.peer,['field_society'])))
 def test_leave_cancels_joint_consent_even_after_rejoin(self):
  self.found();self.join();key=self.propose();self.tool('other','world.decide_agreement',dict(agreement=key,decision='accept'))
  self.tool('other','world.decide_organization',dict(organization='field_society',decision='leave'));self.join()
  self.assertEqual(self.tool('harbor_guide','world.commit_agreement',dict(agreement=key))['status'],'blocked')
  self.assertEqual(agreements.load(self.s,key)[3],'cancelled');self.assertIsNone(shared_outbreaks.line(self.s,self.f.peer))
 def test_decline_and_uninvited_join_do_not_enrol(self):
  self.found();self.assertEqual(self.tool('other','world.decide_organization',dict(organization='field_society',decision='join'))['status'],'blocked')
  self.tool('harbor_guide','world.invite_organization',dict(organization='field_society',target='other'))
  self.tool('other','world.decide_organization',dict(organization='field_society',decision='decline'))
  self.assertEqual(org.load(self.s,'field_society')['members'],['harbor_guide'])
 def test_restart_and_existing_operation_ownership_guards(self):
  self.found();self.join();key=self.propose();self.tool('other','world.decide_agreement',dict(agreement=key,decision='accept'))
  copy=sqlite3.connect(':memory:');self.s.db.backup(copy);old=self.s.db;self.s.db=copy
  try:
   self.assertEqual(org.load(self.s,'field_society')['members'],['harbor_guide','other'])
   with copy:shared_outbreaks.configure(self.s,'other',{},self.f.f.args)
   before=copy.execute('SELECT * FROM shared_outbreaks').fetchall()
   with self.assertRaises(ValueError):agreements.commit(self.s,'harbor_guide',{},dict(agreement=key))
   self.assertEqual(copy.execute('SELECT * FROM shared_outbreaks').fetchall(),before)
  finally:self.s.db=old;copy.close()
 def test_in_game_discovery_and_reaction_routing(self):
  self.found();self.tool('harbor_guide','world.invite_organization',dict(organization='field_society',target='other'))
  event=next(e for e in self.s.memory.history()['events'] if e['event']=='npc_organization_invited')
  self.assertTrue(org.relevant(event,'other'));self.assertFalse(org.relevant(event,'unrelated'))
  self.s.guild_chat.handle(self.f.peer,'/guild org field_society')
  messages=[bytes.fromhex(m[-1]).decode() for m in self.f.peer['chat_history']]
  self.assertIn('Guild: Field Society',messages)
 def test_campaign_not_owned_and_retired_membership_do_not_grant_authority(self):
  self.found();self.join()
  result=self.tool('harbor_guide','world.propose_organization_project',dict(organization='field_society',purpose='No invented content.',tool='world.configure_outbreak',args=json.dumps(self.f.f.args),hours=1,campaign='absent'))
  self.assertEqual(result['status'],'blocked');self.assertEqual(self.s.db.execute('SELECT count(*) FROM npc_organization_actions').fetchone()[0],0)
  self.tool('other','world.decide_organization',dict(organization='field_society',decision='leave'))
  self.tool('harbor_guide','world.decide_organization',dict(organization='field_society',decision='leave'))
  self.assertEqual(org.load(self.s,'field_society')['members'],[])

 def test_long_goal_is_readable_and_rejoining_cannot_revive_old_invitation(self):
  self.assertEqual(self.tool('harbor_guide','world.found_organization',dict(id='long_goal',name='An institution',goal='x'*120))['status'],'succeeded')
  self.s.guild_chat.handle(self.f.peer,'/guild org long_goal')
  self.assertTrue(all(len(bytes.fromhex(m[-1]).decode())<=120 for m in self.f.peer['chat_history']))
  self.assertEqual(org.command(self.s,self.f.peer,['list','4'])[-1],'No organizations on this page.')
