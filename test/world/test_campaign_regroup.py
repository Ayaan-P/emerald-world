import sqlite3
from test_shared_campaigns import SharedCampaignTests
from world.battle_campaigns import command, active, install
from world.shared_campaigns import load
from world.campaign_board import rows, handle
from world.guilds import GuildError


class RegroupTests(SharedCampaignTests):
    def checkpoint(self):
        self.start(); self.battle(self.a, 1); self.battle(self.b, 1)

    def test_voluntary_speaker_handoff_through_board(self):
        self.checkpoint()
        with self.assertRaises(GuildError): command(self.s, self.a, ['pass-speaker', self.b['id']])
        command(self.s, self.b, ['volunteer-speaker'])
        page=next(i for i, (_, c) in enumerate(rows(self.s,self.a)) if c==['pass-speaker',self.b['id']])
        response=handle(self.s,self.a,self.a['campaign_run'],'view',str(page))
        handle(self.s,self.a,self.a['campaign_run'],'pick',response['token'])
        with self.assertRaises(GuildError):command(self.s,self.a,['choose','left'])
        command(self.s,self.b,['choose','left'])

    def test_checkpoint_replacement_does_not_inherit_reports(self):
        self.checkpoint(); command(self.s,self.a,['regroup','left'])
        command(self.s,self.b,['withdraw'])
        self.assertEqual(active(self.s,self.b)[1]['status'],'withdrawn')
        self.assertEqual(len(active(self.s,self.b)[1]['history']),1)
        c=self.f.f.peer('Carol','SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1CORE1');self.f.sync(c,'c'*32)
        command(self.s,c,['join',self.key])
        self.assertEqual(active(self.s,c)[1]['history'],[])
        self.assertEqual(load(self.s,self.key)['results'],{})
        command(self.s,self.a,['begin'])
        self.battle(self.a,1)
        self.assertEqual(active(self.s,self.a)[1]['status'],'waiting')
        self.battle(c,1)
        self.assertEqual(len(active(self.s,c)[1]['history']),1)
        self.assertEqual(len(active(self.s,self.a)[1]['history']),2)

    def test_restart_and_save_lineage_and_active_stage_guards(self):
        self.start()
        for action in (['withdraw'],['regroup','left'],['volunteer-speaker']):
            with self.assertRaises(GuildError):command(self.s,self.b,action)
        self.battle(self.a,1);self.battle(self.b,1)
        command(self.s,self.b,['volunteer-speaker'])
        copy=sqlite3.connect(':memory:');self.s.db.backup(copy);old=self.s.db;self.s.db=copy
        try:
            install(copy)
            command(self.s,self.a,['pass-speaker',self.b['id']])
            command(self.s,self.b,['regroup','left'])
            with self.assertRaises(GuildError):command(self.s,self.b,['withdraw'])
            command(self.s,self.a,['withdraw'])
            command(self.s,self.a,['start','circuit'])
            self.assertEqual(active(self.s,self.b)[1]['status'],'lobby')
            self.f.sync(self.a,'d'*32)
            self.assertIsNone(active(self.s,self.a))
        finally:self.s.db=old;copy.close()
