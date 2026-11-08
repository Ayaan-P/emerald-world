"""Native acceptance reuses real guild goals, consent, rewards and opt-in privacy."""
from concurrent.futures import Future
from copy import deepcopy
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_guild_world_memory as guild_fixture
from test_character_chapters import plan
from world.character_chapters import chapter_step, compile_plan, validate_plan
from world.characters import validate_transition, validate_offer
from world.mechanics import Candidate


class CharacterOfferTests(unittest.TestCase):
    def setUp(self):
        self.fixture=guild_fixture.GuildWorldMemoryTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.server=self.fixture.server
        p=plan();p['chapters']=[p['chapters'][0],p['chapters'][2]]
        p['chapters'][0]['offer']=dict(id='cedar_trip',revision=1,kind='expedition',place_id='native:LittlerootTown',target=2)
        p['chapters'][1]['when']=dict(event='guild_goal_completed',character_id=p['id'],character_offer_id='cedar_trip',character_offer_revision=1)
        self.plan=validate_plan(p)
        self.definition=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()
        context=self.server.inspect();self.after=context['world_memory']['through']
        source=compile_plan(p,context)
        self.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
        self.tick()
        self.alice=self.peer('Alice');self.bob=self.peer('Bob')

    def tick(self):
        result=chapter_step(self.plan,self.definition,self.after,self.server._context(),
                           dict(state=self.server.module_state,tiles=[],objects=self.server.objects))
        future=Future();future.set_result((self.candidate,result))
        self.server.job=(future,'tick',None,self.server.interaction_cursor);self.server.next_tick=float('inf')
        self.server._poll_mechanics();self.assertIsNone(self.server.module_error)

    def peer(self,name,role='SOCIALTRAVELCHATRALLYCHAR1CHARQUEST1'):
        token=self.server.create_identity(name)['token']
        self.server.peers.pop(name,None)
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.server._line(conn,('HELLO 1 '+name+' '+token+' '+role).encode())
        self.assertIn(b'WELCOME',conn['out']);conn['out'].clear()
        self.fixture.connections[name]=conn
        self.send(conn,'STATE 1 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        return conn

    def send(self,conn,line):
        self.server._line(conn,line.encode());out=conn['out'].decode();conn['out'].clear();return out

    def accept(self,conn=None,version=1,revision=1):
        conn=conn or self.alice
        return self.send(conn,f'CHARACTER_ACCEPT {conn["seq"]+1} field_researcher {version} cedar_trip {revision}')

    def receipts(self):
        return self.server.db.execute('SELECT count(*) FROM guild_character_offer_receipts').fetchone()[0]

    def test_explicit_leader_acceptance_and_real_completion_changes_character(self):
        self.assertIn('CHARACTER_OFFER field_researcher 1 cedar_trip 1 2 LittlerootTown',self.server._snapshot(self.alice))
        self.assertIn(' PRIVATE',self.accept());self.assertEqual(self.receipts(),0)
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.fixture.command('chronicle on')
        self.assertIn(' LEADER',self.accept(self.bob));self.assertEqual(self.receipts(),0)
        self.assertIn(' STARTED',self.accept());self.assertEqual(self.receipts(),1)
        self.assertEqual(self.fixture.events(),[]);self.assertEqual(self.fixture.stats(),(0,0,0))
        self.fixture.state('Alice');self.fixture.state('Bob')
        outcome=self.fixture.events()[0]
        self.assertEqual((outcome['character_id'],outcome['character_offer_id'],outcome['character_offer_revision']),('field_researcher','cedar_trip',1))
        self.assertEqual(self.fixture.stats(),(10,1,0))
        self.send(self.alice,f'STATE {self.alice["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertIn(' ALREADY',self.accept());self.assertEqual(self.fixture.stats(),(10,1,0))
        self.tick()
        character=self.server.module_state['world_characters']['field_researcher']
        self.assertEqual(character['team'],[dict(species=278,level=18)])
        self.assertEqual(character['evidence'],[outcome['seq']])
        self.assertNotIn('offer',character)
        self.assertEqual(self.server.objects[0]['text'],'I have new field notes.')

    def test_offered_chapter_requires_bound_completion(self):
        invalid=deepcopy(self.plan)
        invalid['chapters'][1]['when']=dict(event='guild_goal_completed',place_id='native:LittlerootTown')
        with self.assertRaisesRegex(ValueError,'exact character and offer identity'):
            validate_plan(invalid)
        self.fixture.command('chronicle on')
        self.fixture.command('expedition start LittlerootTown 2')
        self.fixture.state('Alice');self.fixture.state('Bob')
        self.assertEqual(len(self.fixture.events()),1)
        self.tick()
        self.assertEqual(self.server.module_state['world_characters']['field_researcher']['version'],1)
        self.assertIn('offer',self.server.module_state['world_characters']['field_researcher'])

    def test_stale_busy_and_old_capability_are_non_mutating(self):
        self.fixture.command('chronicle on')
        self.assertIn(' STALE',self.accept(version=2))
        self.assertIn(' STALE',self.accept(revision=2))
        self.alice['state'][2]=1;self.assertIn(' UNAVAILABLE',self.accept());self.alice['state'][2]=8
        self.alice['character_pending']={'seq':1};self.assertIn(' UNAVAILABLE',self.accept());self.alice.pop('character_pending')
        old=self.peer('Alice','SOCIALTRAVELCHATRALLYCHAR1')
        self.assertNotIn('CHARACTER_OFFER ',self.server._snapshot(old))
        self.assertIn(' UNAVAILABLE',self.accept(old));self.assertEqual(self.receipts(),0)

    def test_active_goal_and_insufficient_members_are_preserved(self):
        self.fixture.command('chronicle on');self.fixture.command('expedition start LittlerootTown 1')
        before=self.server.db.execute('SELECT * FROM guild_expeditions').fetchall()
        self.assertIn(' ACTIVE',self.accept());self.assertEqual(self.server.db.execute('SELECT * FROM guild_expeditions').fetchall(),before)
        self.fixture.command('expedition cancel');self.server.guilds.command('Alice','kick Bob')
        self.assertIn(' MEMBERS',self.accept());self.assertEqual(self.receipts(),0)

    def test_acceptance_receipt_failure_rolls_back_goal_start(self):
        self.fixture.command('chronicle on')
        with self.server.db:
            self.server.db.execute("CREATE TRIGGER fail_offer BEFORE INSERT ON guild_character_offer_receipts BEGIN SELECT RAISE(ABORT,'fixture'); END")
        self.assertIn(' REFUSED',self.accept())
        self.assertEqual(self.server.db.execute('SELECT count(*) FROM guild_expeditions').fetchone()[0],0)
        self.assertEqual(self.receipts(),0)

    def test_cancel_clears_binding_and_completed_receipt_survives_restart(self):
        self.fixture.command('chronicle on');self.assertIn(' STARTED',self.accept())
        self.fixture.command('expedition cancel');self.assertEqual(self.receipts(),0)
        self.fixture.command('expedition start LittlerootTown 2')
        self.fixture.state('Alice');self.fixture.state('Bob')
        self.assertNotIn('character_offer_id',self.fixture.events()[0])
        self.send(self.alice,f'STATE {self.alice["seq"]+1} 0 9 8 8 4 7 1 '+'a'*16+' '+'b'*16)
        self.assertIn(' STARTED',self.accept());self.fixture.state('Alice');self.fixture.state('Bob')
        self.assertEqual(self.receipts(),1)
        self.server.close();self.fixture.case.server=self.fixture.case.open();self.fixture.server=self.fixture.case.server;self.server=self.fixture.server
        self.alice=self.peer('Alice')
        self.assertIn(' ALREADY',self.accept())
        self.assertEqual(self.server.db.execute('SELECT complete FROM guild_expeditions').fetchone()[0],1)

    def test_privacy_off_after_acceptance_stays_private_and_disband_cleans_receipts(self):
        self.fixture.command('chronicle on');self.assertIn(' STARTED',self.accept())
        self.fixture.command('chronicle off');self.fixture.state('Alice');self.fixture.state('Bob')
        self.assertEqual(self.fixture.events(),[]);self.assertEqual(self.fixture.stats(),(10,1,0))
        self.tick();self.assertEqual(self.server.module_state['world_characters']['field_researcher']['version'],1)
        self.fixture.command('disband');self.assertEqual(self.receipts(),0)

    def test_offer_terms_need_new_revision_and_valid_native_destination(self):
        before=deepcopy(self.server.module_state);after=deepcopy(before)
        after['world_characters']['field_researcher']['version']=2
        after['world_characters']['field_researcher']['offer']['target']=1
        with self.assertRaises(ValueError):validate_transition(before,after,self.server.objects,self.server.db)
        offer=deepcopy(self.plan['chapters'][0]['offer']);offer['place_id']='native:GeneratedWorld_Cave'
        with self.assertRaises(ValueError):validate_offer(offer)


if __name__=='__main__':unittest.main()
