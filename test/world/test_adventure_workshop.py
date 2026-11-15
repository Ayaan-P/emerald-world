import json,time,unittest
from copy import deepcopy
import test_content_ui as fixture
from world import adventure_workshop as workshop
from world.battle_campaigns import command,active,publish
from world.session import SessionError

class AdventureWorkshopTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ContentUI();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.plan=dict(id='open_journey',title='A player-authored journey',entry='arrival',nodes=dict(arrival=dict(visit=dict(label='Meet here',point=[0,9,8,8]),next=[])))
 def preview(self):return self.f.call('preview',kind='adventure',label='',plan=self.plan,outcome_seq=None)
 def test_preview_is_read_only_then_install_readback_and_normal_player_start(self):
  old=self.s.shared_cave.identity;history=self.s.memory.history();review=self.preview()
  self.assertFalse(review['report']['installed']);self.assertFalse(review['report']['shared_only'])
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM battle_campaigns').fetchone()[0],0)
  with self.assertRaises(SessionError):self.f.call('apply',token=review['token'],confirmed=False)
  result=self.f.call('apply',token=review['token'],confirmed=True)
  self.assertTrue(result['adventure']['installed']);self.assertEqual(self.s.shared_cave.identity,old);self.assertEqual(self.s.memory.history(),history)
  self.assertEqual(self.f.call('read')['adventures'][0]['id'],'open_journey')
  peer=dict(id='Visitor',campaign_run='a'*32)
  command(self.s,peer,['start','open_journey']);self.assertEqual(active(self.s,peer)[1]['node'],'arrival')
  self.s.peers[peer['id']]=peer;peer.update(state=[0,9,8,8,4,7,1],state_time=time.monotonic())
  command(self.s,peer,['check-in']);self.assertEqual(active(self.s,peer)[1]['status'],'complete')
  self.s.peers.clear()
  with self.assertRaises(SessionError):self.f.call('apply',token=review['token'],confirmed=True)
 def test_confirmed_install_is_idempotent_and_preserves_run(self):
  review=self.preview();self.f.call('apply',token=review['token'],confirmed=True)
  peer=dict(id='Visitor',campaign_run='a'*32);command(self.s,peer,['start','open_journey']);old=active(self.s,peer)
  review=self.preview();self.assertTrue(review['report']['installed']);self.f.call('apply',token=review['token'],confirmed=True)
  self.assertEqual(active(self.s,peer),old)
 def test_stale_review_and_players_block_without_install(self):
  review=self.preview();self.s.peers['person']=dict(id='person')
  with self.assertRaises(SessionError):self.f.call('apply',token=review['token'],confirmed=True)
  self.s.peers.clear();self.s.memory.append('changed',dict(note='Real public state changed'));self.s.db.commit()
  with self.assertRaises(SessionError):self.f.call('apply',token=review['token'],confirmed=True)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM battle_campaigns').fetchone()[0],0)
 def test_foreign_authorship_conflicting_identity_and_bad_graph_rejected(self):
  with self.s.db:publish(self.s,'another_author',{},dict(campaign=json.dumps(self.plan)))
  with self.assertRaises(SessionError):self.preview()
  self.plan['id']='cycle';self.plan['nodes']['arrival']['next']=['arrival']
  with self.assertRaises(SessionError):self.preview()
 def test_changed_dependency_rechecks_before_save(self):
  reviewed=workshop.inspect(self.s,self.plan);reviewed['entry']='different'
  with self.assertRaises(ValueError):workshop.install(self.s,self.plan,reviewed)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM battle_campaigns').fetchone()[0],0)
 def test_split_adventure_reports_shared_only(self):
  task=deepcopy(self.plan['nodes']['arrival']);task.pop('next')
  self.plan['nodes']['arrival']=dict(roles={'first':task,'second':deepcopy(task)},win=[],loss=[])
  review=self.preview();self.assertTrue(review['report']['shared_only']);self.assertEqual(len(review['report']['stages'][0]['tasks']),2)

 def test_real_mechanism_dependency_change_invalidates_review(self):
  import test_field_expeditions as f
  fixture=f.ExpeditionTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
  plan=deepcopy(fixture.doc);plan['id']='reviewed_expedition';server=fixture.s
  report=workshop.inspect(server,plan)
  self.assertEqual(report['stages'][0]['tasks'][0]['kind'],'expedition')
  self.assertEqual(workshop.catalog(server)['mechanisms'][0]['network'],'mechanism')
  server.module_state['world_object_networks']['mechanism']['program']['initial']='on'
  with self.assertRaises(ValueError):workshop.install(server,plan,report)
  self.assertIsNone(server.db.execute('SELECT id FROM battle_campaigns WHERE id=?',(plan['id'],)).fetchone())
