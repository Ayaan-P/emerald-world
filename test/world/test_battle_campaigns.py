import json
import sqlite3
import unittest
from copy import deepcopy
import test_character_offers as fixture
from world.battle_campaigns import publish,command,active,install
from world.guilds import GuildError

class BattleCampaignTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.CharacterOfferTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.server;self.a=self.f.peer('Alice','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1');self.f.bob=self.f.peer('Bob','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1')
        self.sync(self.a,'a'*32)
        self.d=dict(id='circuit',title='Open circuit',entry='first',nodes={
            'first':dict(opponent='field_researcher',win=['left','right'],loss=['recover']),
            'left':dict(opponent='field_researcher',win=[],loss=[]),
            'right':dict(opponent='field_researcher',win=[],loss=[]),
            'recover':dict(opponent='field_researcher',win=['right'],loss=[])})
        with self.s.db:publish(self.s,'field_researcher',{},dict(campaign=json.dumps(self.d)))
    def sync(self,conn,lineage):
        self.assertIn('CORE RESULT',self.f.send(conn,f'CORE {lineage} MILE 0 private'))
    def battle(self,outcome):
        seq=self.a['seq']+1
        self.assertIn('CHARACTER_BATTLE_V1',self.f.send(self.a,f'CHARACTER_CHALLENGE {seq} field_researcher 1'))
        line=f'CHARACTER_RESULT {seq} field_researcher 1 {outcome}'
        self.assertIn('CHARACTER_RESULT_ACK',self.f.send(self.a,line));return line
    def test_actual_battles_choose_branch_and_finish(self):
        command(self.s,self.a,['start','circuit'])
        replay=self.battle(1)
        self.assertEqual(active(self.s,self.a)[1]['choices'],['left','right'])
        self.assertIn('CHARACTER_REJECT',self.f.send(self.a,replay))
        with self.assertRaises(GuildError):command(self.s,self.a,['choose','recover'])
        command(self.s,self.a,['choose','right']);self.battle(2)
        data=active(self.s,self.a)[1]
        self.assertEqual(data['status'],'complete');self.assertEqual(len(data['history']),2)
        self.assertEqual(self.f.fixture.stats(),(0,0,0))
    def test_abort_does_not_complete_and_loss_route(self):
        command(self.s,self.a,['start','circuit']);self.battle(0)
        self.assertEqual(active(self.s,self.a)[1]['status'],'ready')
        self.battle(2);self.assertEqual(active(self.s,self.a)[1]['choices'],['recover'])
    def test_save_and_player_isolation_and_restart(self):
        command(self.s,self.a,['start','circuit']);self.battle(1)
        self.sync(self.a,'b'*32);self.assertIsNone(active(self.s,self.a))
        self.sync(self.f.bob,'a'*32);self.assertIsNone(active(self.s,self.f.bob))
        self.sync(self.a,'a'*32)
        # Re-open durable SQLite image, not the process-local session.
        db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
        try:install(db);self.assertEqual(active(self.s,self.a)[1]['choices'],['left','right'])
        finally:self.s.db=old;db.close()
    def test_lineage_change_during_battle_cannot_credit_new_save(self):
        command(self.s,self.a,['start','circuit']);seq=self.a['seq']+1
        self.f.send(self.a,f'CHARACTER_CHALLENGE {seq} field_researcher 1')
        self.sync(self.a,'b'*32)
        self.f.send(self.a,f'CHARACTER_RESULT {seq} field_researcher 1 1')
        self.sync(self.a,'a'*32);self.assertEqual(active(self.s,self.a)[1]['status'],'ready')
    def test_normal_battle_without_campaign_and_immutable_graph(self):
        self.battle(1);self.assertIsNone(active(self.s,self.a))
        bad=deepcopy(self.d);bad['title']='Changed'
        with self.assertRaises(ValueError):publish(self.s,'field_researcher',{},dict(campaign=json.dumps(bad)))
        bad['id']='cycle';bad['nodes']['right']['win']=['first']
        with self.assertRaises(ValueError):publish(self.s,'field_researcher',{},dict(campaign=json.dumps(bad)))
    def test_actual_private_chat_entrypoint(self):
        before=len(self.a['chat_history'])
        self.s.guild_chat.handle(self.a,'/guild campaign start circuit')
        self.assertGreater(len(self.a['chat_history']),before)
        self.assertEqual(active(self.s,self.a)[1]['node'],'first')

    def test_discovered_agent_plan_publishes_real_playable_graph(self):
        from world import actor_runtime as runtime
        d=deepcopy(self.d);d['id']='agent_circuit'
        plan=dict(id='publish_campaign',purpose='Organize optional opponents.',steps=[dict(
            id='publish',tool='world.publish_battle_campaign',args=dict(campaign=json.dumps(d,separators=(',',':'))),after=[])])
        runtime.validate(plan)
        self.s.module_state['world_characters']['field_researcher']['plan']=plan
        self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
        self.assertIsNone(runtime.tick(self.s,now=16))
        catalog=self.s.inspect()['actor_runtime']['battle_campaigns']
        self.assertIn('agent_circuit',[r['id'] for r in catalog])
        command(self.s,self.a,['start','agent_circuit']);self.battle(1)
        self.assertEqual(active(self.s,self.a)[1]['choices'],['left','right'])
