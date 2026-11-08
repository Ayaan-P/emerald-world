"""Existing guild goals over exact admitted generated-place presence."""
import time
import unittest
from unittest.mock import patch
import test_region_characters as region_fixture
from world.generated_goals import observed_place
from world.guilds import GuildError
from world.characters import history_feed


class GeneratedExpeditionTests(unittest.TestCase):
    def setUp(self):
        self.f=region_fixture.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.server=self.f.server
        self.alice=self.f.connect('Alice',self.f.f.ra['place_id'],self.f.f.a)
        self.bob=self.f.connect('Bob',self.f.f.rb['place_id'],self.f.f.b)
        self.server.guilds.command('Alice','create Explorers')
        self.server.guilds.command('Alice','invite Bob');self.server.guilds.command('Bob','accept Explorers')

    def command(self,text,conn=None):
        self.server.guild_chat.handle(conn or self.alice,'/guild '+text)

    def visits(self):return self.server.db.execute('SELECT count(*) FROM guild_expedition_visits').fetchone()[0]
    def events(self):return [e for e in self.server.memory.history()['events'] if e['event']=='guild_goal_completed']
    def report(self,conn):self.f.state(conn,*self.server.cave_map,2,3)

    def move_bob_to_alice(self):
        self.f.state(self.bob,0,9,8,8)
        self.f.send(self.bob,'REGION SELECT '+self.f.f.ra['place_id'])
        self.f.send(self.bob,'CAVE GET');self.f.send(self.bob,'CAVE ACK '+self.f.f.a)
        self.report(self.bob)

    def test_generated_aliases_and_meetups_reject_without_starting(self):
        for command in ('expedition','meet'):
            for name in ('GeneratedWorld_Cave','GeneratedWorld_Wilds'):
                with self.assertRaises(GuildError):self.server.guilds.command('Alice',f'{command} start {name} 2')
        self.command('meet start here 2')
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_meetups').fetchone()[0],0)

    def test_same_coordinates_other_place_cannot_complete_exact_destination(self):
        self.command('chronicle on');self.command('expedition start here 2')
        self.assertEqual(self.server.db.execute('SELECT place_id,revision FROM guild_expedition_places').fetchone(),(self.f.f.ra['place_id'],self.f.f.a))
        self.report(self.alice);self.assertEqual(self.visits(),1)
        self.report(self.alice);self.report(self.bob)
        self.assertEqual(self.visits(),1);self.assertEqual(self.events(),[])
        self.move_bob_to_alice()
        event=self.events()[0]
        self.assertEqual((event['place_id'],event['region_revision']),(self.f.f.ra['place_id'],self.f.f.a))
        self.assertEqual(event['awarded_guild_xp'],10)
        self.report(self.bob);self.report(self.alice)
        self.assertEqual(len(self.events()),1)
        feed=history_feed(self.server.db,{'character_history_cursor':event['seq']-1})
        self.assertEqual(feed['events'][0]['region_revision'],self.f.f.a)
        self.server.close();self.f.f.server=self.f.f.open();self.server=self.f.f.server;self.f.server=self.server
        self.assertEqual(self.server.db.execute('SELECT complete FROM guild_expeditions').fetchone()[0],1)
        self.assertEqual(self.server.db.execute('SELECT revision FROM guild_expedition_places').fetchone()[0],self.f.f.a)

    def test_shared_xl_replacement_same_place_waits_for_exact_revision(self):
        revision=self.f.enable_shared_xl()
        leader=self.f.connect_shared_xl('XLLeader');partner=self.f.connect_shared_xl('XLPartner')
        self.server.guilds.command('XLLeader','create Highlands')
        self.server.guilds.command('XLLeader','invite XLPartner');self.server.guilds.command('XLPartner','accept Highlands')
        self.command('chronicle on',leader);self.command('expedition start here 2',leader)
        self.f.state(leader,*self.server.wilds_map,70,70)
        self.assertEqual(self.visits(),1)
        for conn in (leader,partner):self.f.state(conn,0,9,8,8)
        replacement=bytearray(self.f.xl_blob);replacement[8+10*127+10]=ord('#')
        other=self.server._replace_cave(bytes(replacement),label='Highlands changed',previous_revision=revision)
        self.assertEqual(self.server.memory.place(other),self.server.memory.place(revision))
        def enter(conn,identity):
            with patch('world.server.time.monotonic',return_value=max(time.monotonic(),conn['cave_next']+.01)):
                self.assertIn('XLWILDS',self.f.send(conn,'CAVE GET'))
            self.assertIn('CAVE OK',self.f.send(conn,'CAVE ACK '+identity))
            self.f.state(conn,*self.server.wilds_map,70,70)
        enter(partner,other)
        self.assertEqual(self.visits(),1);self.assertEqual(self.events(),[])
        self.f.state(partner,0,9,8,8)
        self.server.activate_generated_area(revision)
        enter(partner,revision)
        self.assertEqual(self.visits(),2)
        self.assertEqual(self.events()[0]['region_revision'],revision)
        self.assertEqual(self.events()[0]['awarded_guild_xp'],10)

    def test_leader_privacy_freshness_and_cancel_preserve_existing_rules(self):
        self.command('expedition start here 2',self.bob)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.alice['state_time']=time.monotonic()-20
        self.command('expedition start here 2')
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.assertIsNone(observed_place(self.server,self.alice))
        self.report(self.alice);self.command('expedition start here 2');self.report(self.alice)
        saved=self.alice['cave_ack'];self.alice['cave_ack']='0'*64
        self.assertIsNone(observed_place(self.server,self.alice));self.alice['cave_ack']=saved
        self.move_bob_to_alice();self.assertEqual(self.events(),[]) # private by default
        self.assertEqual(self.server.db.execute('SELECT xp FROM guild_stats').fetchone()[0],10)
        self.command('expedition cancel')
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expedition_places').fetchone()[0],0)
        self.command('expedition start Route101 2')
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expedition_places').fetchone()[0],0)


if __name__=='__main__':unittest.main()
