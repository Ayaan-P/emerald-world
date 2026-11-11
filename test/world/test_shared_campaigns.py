import sqlite3
import unittest
from world.battle_campaigns import command, active, install
from world.campaign_board import rows, handle, state_key
from world.guilds import GuildError
from world.shared_campaigns import load
import test_battle_campaigns as fixture

class SharedCampaignTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.BattleCampaignTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.a=self.f.a;self.b=self.f.f.bob
        self.f.sync(self.b,'b'*32)
    def start(self):
        command(self.s,self.a,['share','circuit'])
        self.key=active(self.s,self.a)[1]['shared']
        command(self.s,self.b,['join',self.key]);command(self.s,self.a,['begin'])
    def battle(self,c,result):
        old=self.f.a;self.f.a=c
        try:return self.f.battle(result)
        finally:self.f.a=old
    def test_two_actual_battles_advice_speaker_and_loss_route(self):
        self.start();self.battle(self.a,1)
        self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
        self.assertEqual(active(self.s,self.b)[1]['status'],'ready')
        self.battle(self.b,1)
        command(self.s,self.b,['advise','right'])
        self.assertTrue(any('advises right' in text for text,_ in rows(self.s,self.a)))
        with self.assertRaises(GuildError):command(self.s,self.b,['choose','right'])
        command(self.s,self.a,['choose','left']) # advice isn't a veto
        self.battle(self.b,2);self.battle(self.a,1)
        for c in (self.a,self.b):
            self.assertEqual(active(self.s,c)[1]['status'],'complete')
            self.assertEqual(len(active(self.s,c)[1]['history']),2)
        self.assertEqual(self.f.f.fixture.stats(),(0,0,0))
        command(self.s,self.a,['start','circuit'])
        command(self.s,self.b,['leave'])
        self.assertEqual(active(self.s,self.a)[1]['status'],'ready')
    def test_private_native_board_lobby_and_save_isolation(self):
        opts=rows(self.s,self.a);page=next(i for i,r in enumerate(opts) if r[1]==['share','circuit'])
        response=handle(self.s,self.a,self.a['campaign_run'],'view',str(page))
        handle(self.s,self.a,self.a['campaign_run'],'pick',response['token'])
        key=active(self.s,self.a)[1]['shared']
        with self.assertRaises(GuildError):command(self.s,self.a,['begin'])
        self.s.guild_chat.handle(self.b,'/guild campaign join '+key)
        self.assertEqual(active(self.s,self.b)[1]['shared'],key)
        self.f.sync(self.b,'c'*32);self.assertIsNone(active(self.s,self.b))
        with self.assertRaises(GuildError):command(self.s,self.b,['join',key])
        self.f.sync(self.b,'b'*32)
        opts=rows(self.s,self.a);page=next(i for i,r in enumerate(opts) if r[1]==['begin'])
        r=handle(self.s,self.a,self.a['campaign_run'],'view',str(page))
        handle(self.s,self.a,self.a['campaign_run'],'pick',r['token'])
        self.assertEqual(active(self.s,self.b)[1]['status'],'ready')
    def test_restart_wait_and_stale_board_and_cancel(self):
        self.start();self.battle(self.a,1)
        db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
        try:
            install(db);self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
            self.battle(self.b,2)
            self.assertEqual(active(self.s,self.a)[1]['choices'],['recover'])
            before=state_key(self.s,self.a)
            r=handle(self.s,self.a,self.a['campaign_run'],'view','0')
            command(self.s,self.b,['advise','recover'])
            self.assertNotEqual(before,state_key(self.s,self.a))
            with self.assertRaises(ValueError):handle(self.s,self.a,self.a['campaign_run'],'pick',r['token'])
            command(self.s,self.b,['leave'])
            self.assertIsNone(active(self.s,self.a));self.assertEqual(load(self.s,self.key)['status'],'cancelled')
        finally:self.s.db=old;db.close()
    def test_cancelled_battle_and_replay_do_not_advance_group(self):
        self.start();self.battle(self.a,0)
        self.assertEqual(load(self.s,self.key)['results'],{})
        replay=self.battle(self.a,1)
        self.assertIn('CHARACTER_REJECT',self.f.f.send(self.a,replay))
        self.assertEqual(len(load(self.s,self.key)['results']),1)
        self.battle(self.a,1) # optional repeat battle cannot credit waiting member twice
        self.assertEqual(len(load(self.s,self.key)['results']),1)
        command(self.s,self.b,['leave'])
        self.assertIsNone(active(self.s,self.a))
    def test_four_trainers_complete_only_after_all_reports(self):
        self.start()
        # Started membership is frozen, even with space remaining.
        c=self.f.f.peer('Carol','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1')
        self.f.sync(c,'c'*32)
        with self.assertRaises(GuildError):command(self.s,c,['join',self.key])
        command(self.s,self.a,['leave'])
        command(self.s,self.a,['share','circuit']);self.key=active(self.s,self.a)[1]['shared']
        d=self.f.f.peer('Drew','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1');self.f.sync(d,'d'*32)
        for conn in (self.b,c,d):command(self.s,conn,['join',self.key])
        command(self.s,self.a,['begin'])
        for conn in (d,c,self.a):self.battle(conn,1)
        self.assertEqual(load(self.s,self.key)['status'],'ready')
        self.battle(self.b,2)
        self.assertEqual(load(self.s,self.key)['choices'],['recover'])
        self.assertEqual(len(load(self.s,self.key)['results']),4)

    def optional(self):
        import json
        from copy import deepcopy
        from world.battle_campaigns import publish
        d=deepcopy(self.f.d);d['id']='optional';d['nodes']['first']['decline']=['recover']
        with self.s.db:publish(self.s,'field_researcher',{},dict(campaign=json.dumps(d)))
        command(self.s,self.a,['share','optional']);self.key=active(self.s,self.a)[1]['shared']
        command(self.s,self.b,['join',self.key]);command(self.s,self.a,['begin'])

    def test_optional_decline_and_real_battle_keep_individual_credit_after_restart(self):
        self.optional()
        opts=rows(self.s,self.b);page=next(i for i,r in enumerate(opts) if r[1]==['decline-challenge'])
        self.assertTrue(any('white out' in text for text,_ in opts))
        response=handle(self.s,self.b,self.b['campaign_run'],'view',str(page))
        handle(self.s,self.b,self.b['campaign_run'],'pick',response['token'])
        record=active(self.s,self.b)[1]['history'][0]
        self.assertEqual(record['basis'],'voluntary_challenge_declined');self.assertNotIn('outcome',record)
        self.assertEqual(active(self.s,self.a)[1]['status'],'ready')
        with self.assertRaises(ValueError):handle(self.s,self.b,self.b['campaign_run'],'pick',response['token'])
        db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
        try:
            install(db);self.battle(self.a,1)
            self.assertEqual(active(self.s,self.a)[1]['choices'],['recover'])
            self.assertEqual(active(self.s,self.a)[1]['history'][0]['outcome'],1)
            self.assertEqual(active(self.s,self.b)[1]['history'],[record])
            self.assertEqual(load(self.s,self.key)['results'],{'Bob':'declined','Alice':1})
        finally:self.s.db=old;db.close()
        self.assertEqual(self.f.f.fixture.stats(),(0,0,0))

    def test_decline_rejects_pending_battle_nonoptional_and_other_lineage(self):
        self.start()
        with self.assertRaises(GuildError):command(self.s,self.a,['decline-challenge'])
        command(self.s,self.a,['leave']);self.optional()
        seq=self.a['seq']+1
        self.f.f.send(self.a,f'CHARACTER_CHALLENGE {seq} field_researcher 1')
        with self.assertRaises(GuildError):command(self.s,self.a,['decline-challenge'])
        self.f.f.send(self.a,f'CHARACTER_RESULT {seq} field_researcher 1 0')
        self.f.sync(self.a,'c'*32)
        with self.assertRaises(GuildError):command(self.s,self.a,['decline-challenge'])
        self.f.sync(self.a,'a'*32)
        command(self.s,self.a,['decline-challenge']);command(self.s,self.b,['decline-challenge'])
        self.assertEqual(load(self.s,self.key)['status'],'choice')
        self.assertTrue(all('outcome' not in active(self.s,c)[1]['history'][0] for c in (self.a,self.b)))
