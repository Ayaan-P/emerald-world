"""Authenticated presence -> actual guild reward -> durable builder evidence."""
import json
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch
import test_world_memory as fixtures
from world import gm
from world.guilds import GuildError
from world.world_journal import describe


class GuildWorldMemoryTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.WorldMemoryTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.server = self.case.server
        self.connections = {}
        for name in ('Alice','Bob','Eve'):
            identity = self.server.create_identity(name)
            conn = dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
            self.server._line(conn,('HELLO 1 '+name+' '+identity['token']+' SOCIALTRAVELCHATRALLY').encode())
            self.assertIn(b'WELCOME',conn['out'])
            conn['out'].clear()
            self.connections[name] = conn
        self.server.guilds.command('Alice','create Redwood')
        self.server.guilds.command('Alice','invite Bob')
        self.server.guilds.command('Bob','accept Redwood')

    def command(self, text, trainer='Alice'):
        self.server.guild_chat.handle(self.connections[trainer], '/guild '+text)

    def state(self, name, ready=1, location=(0,9)):
        conn = self.connections[name]
        seq = conn['seq']+1
        self.server._line(conn,(f'STATE {seq} {location[0]} {location[1]} 8 8 1 7 {ready} '+'a'*16+' '+'b'*16).encode())

    def events(self):
        return [e for e in self.server.memory.history()['events'] if e['event']=='guild_goal_completed']

    def stats(self):
        return self.server.db.execute('SELECT xp,expeditions,meetups FROM guild_stats').fetchone()

    def test_existing_goal_completion_and_reward_record_atomically_once(self):
        self.command('chronicle on')
        self.command('expedition start LittlerootTown 2')
        self.state('Eve')
        self.state('Alice',location=(0,0))
        self.assertEqual(self.events(),[])
        self.state('Alice')
        self.state('Alice')
        self.state('Bob',ready=0)
        self.assertEqual(self.events(),[])
        self.assertEqual(self.stats(),(0,0,0))
        self.state('Bob')
        event = self.events()[0]
        self.assertEqual(self.stats(),(10,1,0))
        self.assertEqual((event['guild_name'],event['place_id'],event['target'],event['credited']),('Redwood','native:LittlerootTown',2,2))
        self.assertEqual(event['awarded_guild_xp'],10)
        self.assertEqual(event['basis'],'authority_goal_rules_over_authenticated_client_presence')
        self.state('Bob');self.state('Alice')
        self.assertEqual(len(self.events()),1)
        self.assertEqual(self.server.revision,self.server.db.execute('SELECT max(seq) FROM events').fetchone()[0])
        for name in ('Alice','Bob','Eve','token','party','save_path'):
            self.assertNotIn(name,json.dumps(event))
        self.assertEqual(describe(event)['title'],'Guild expedition completed')
        self.server.close();self.case.server=self.case.open();self.server=self.case.server
        self.assertEqual(self.events(),[event])
        self.assertEqual(self.stats(),(10,1,0))
        self.assertIsNone(self.server.guilds.visit('Bob','LittlerootTown'))
        self.assertEqual(len(self.events()),1)

    def test_private_by_default_no_backfill_leader_toggle_and_disband(self):
        self.command('expedition start LittlerootTown 1')
        self.state('Alice')
        self.assertEqual(self.stats(),(10,1,0))
        self.assertEqual(self.events(),[])
        with self.assertRaises(GuildError):self.server.guilds.command('Bob','chronicle on')
        self.command('chronicle on')
        self.assertEqual(self.events(),[])
        self.command('expedition start LittlerootTown 1')
        self.command('chronicle off')
        self.state('Alice')
        self.assertEqual(self.stats(),(20,2,0))
        self.assertEqual(self.events(),[])
        self.command('chronicle on');self.command('disband')
        self.command('create Redwood')
        self.assertIn('OFF',self.server.guilds.command('Alice','chronicle')[0])

    def test_meetup_requires_fresh_together_presence_and_has_real_reward(self):
        self.command('chronicle on');self.command('meet start LittlerootTown 2')
        self.state('Alice')
        self.connections['Alice']['state_time']=time.monotonic()-100
        self.connections['Alice']['guild_last_ready_time']=time.monotonic()-100
        self.state('Bob')
        self.assertEqual(self.events(),[])
        self.state('Alice')
        event=self.events()[0]
        self.assertEqual(event['goal_kind'],'meetup')
        self.assertEqual(event['awarded_guild_xp'],15)
        self.assertEqual(self.stats(),(15,0,1))
        self.state('Alice');self.state('Bob')
        self.assertEqual(len(self.events()),1)

    def test_history_failure_rolls_back_reward_and_retries_next_valid_report(self):
        self.command('chronicle on');self.command('expedition start LittlerootTown 2')
        self.state('Alice')
        with patch.object(self.server.memory,'_index',side_effect=sqlite3.OperationalError('fixture disk failure')):
            self.state('Bob')
        self.assertEqual(self.stats(),(0,0,0))
        self.assertEqual(self.events(),[])
        self.assertEqual(self.server.db.execute('SELECT complete FROM guild_expeditions').fetchone()[0],0)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expedition_visits').fetchone()[0],1)
        self.assertNotIn('guild_visit_key',self.connections['Bob'])
        self.assertIsNone(self.server.module_error)
        self.state('Bob')
        self.assertEqual(self.stats(),(10,1,0))
        self.assertEqual(len(self.events()),1)

    def test_xp_cap_records_actual_award_not_nominal_reward(self):
        self.command('chronicle on');self.command('expedition start LittlerootTown 1')
        with self.server.db:self.server.db.execute('UPDATE guild_stats SET xp=999999998')
        self.state('Alice')
        self.assertEqual(self.events()[0]['awarded_guild_xp'],2)
        self.assertEqual(self.events()[0]['resulting_guild_xp'],1000000000)

    def test_real_completion_reaches_next_proposal_after_restart(self):
        self.command('chronicle on');self.command('expedition start LittlerootTown 2')
        self.state('Alice');self.state('Bob')
        outcome=self.events()[0]
        for n in range(30):
            self.case.commit_mechanic([dict(id='cityguide',group=0,num=0,x=8,y=8,gfx=7,text='City notice '+str(n)+'.')])
        self.server.close();self.case.server=self.case.open();self.server=self.case.server
        self.assertNotIn(outcome['seq'],[e['seq'] for e in self.server.memory.context(self.server)['recent']])
        proposals=[]
        def request(_socket,payload,timeout):
            if payload['command']=='deploy':
                proposals.append(Path(payload['source_path']).read_text())
                return dict(ok=False,error='proposal fixture; no sandbox acceptance claimed')
            return self.case.admin(payload)
        def author(prompt):
            context=json.loads(prompt.split('Request and snapshot follow:\n',1)[1])['inspection']
            event=next(e for e in context['recalled_history']['events'] if e['seq']==outcome['seq'])
            self.assertEqual(event['event'],'guild_goal_completed')
            self.assertEqual(event['awarded_guild_xp'],10)
            objects=context['objects']+[dict(id='expedition_marker',group=0,num=9,x=9,y=8,gfx=8,text='Redwood expedition honored.')]
            return dict(source="# Confirmed group-goal evidence seq %d.\ndef update(context, state):\n    return {'state':state,'tiles':[],'objects':%r}\n"%(event['seq'],objects),tests="def test_marker():\n    assert update({}, {})['objects'][-1]['id']=='expedition_marker'\n")
        with patch('world.gm.admin_request',side_effect=request):
            report=gm.author_and_deploy(self.case.root/'controller',self.case.root/'socket','Honor the Redwood expedition in the world.',author)
        self.assertIn(outcome['seq'],report['history_evidence']['sequences'])
        self.assertIn('Redwood expedition honored.',proposals[0])
        self.assertFalse(report['ok'])
        self.assertNotIn('expedition_marker',[o['id'] for o in self.server.objects])


if __name__=='__main__':unittest.main()
