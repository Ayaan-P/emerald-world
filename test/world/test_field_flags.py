import copy
import json
import unittest
import test_field_relays
from world.field_flags import ARENA


class FlagTests(unittest.TestCase):
    setUp=test_field_relays.FieldRelayTests.setUp
    connect=test_field_relays.FieldRelayTests.connect
    chat=test_field_relays.FieldRelayTests.chat
    state=test_field_relays.FieldRelayTests.state
    # Reuse the actual authority/CHAT/STATE fixture, not relay gameplay tests.
    def duel(self):
        self.chat(self.a,'/guild flag start '+ARENA['id'])
        r=self.s.flags.current('Alice');self.chat(self.b,'/guild flag join '+r['id'])
        for i,c in enumerate((self.a,self.b)):self.state(c,ARENA['bases'][i])
        self.chat(self.a,'/guild flag ready');self.chat(self.b,'/guild flag ready')
        self.now+=2
        for i,c in enumerate((self.a,self.b)):self.state(c,ARENA['bases'][i])
        self.now+=1;self.s.flags.tick();self.assertEqual(r['phase'],'playing')
        return r

    def test_capture_loop_and_private_persistent_result(self):
        r=self.duel();self.state(self.b,[0,0,23,13])
        for _ in range(3):
            self.state(self.a,ARENA['bases'][1]);self.assertTrue(r['carrying'][0])
            self.state(self.a,ARENA['bases'][0])
        self.assertIsNone(self.s.flags.current('Alice'))
        self.assertEqual(r['scores'],[3,0]);self.assertEqual(self.c['chat_history'],[])
        self.assertTrue(any('Alice 3' in x for x in self.chat(self.a,'/guild flag records')))
        self.assertTrue(any('No completed' in x for x in self.chat(self.c,'/guild flag records')))
        self.s.close();from test_shared_generated_cave import MemoryAuthority
        self.s=MemoryAuthority(self.root/'sock',self.root/'world')
        self.assertEqual(self.s.db.execute('SELECT scores FROM flag_results').fetchone()[0],'[3,0]')
        self.assertEqual(self.s.flags.runs,{})

    def test_tag_requires_return_home_and_cooldown(self):
        r=self.duel();self.state(self.b,[0,0,23,13]);self.state(self.a,ARENA['bases'][1])
        self.state(self.b,[0,0,22,13])
        self.assertEqual(r['carrying'],[False,False]);self.assertFalse(r['armed'][0])
        self.state(self.a,ARENA['bases'][1]);self.assertFalse(r['carrying'][0])
        self.state(self.a,ARENA['bases'][0]);self.assertFalse(r['armed'][0])
        self.now+=3;self.state(self.a,ARENA['bases'][0]);self.assertTrue(r['armed'][0])

    def test_stolen_home_flag_blocks_capture_and_busy_carrier_returns_flag(self):
        r=self.duel();self.state(self.b,[0,0,23,13]);self.state(self.a,ARENA['bases'][1])
        self.state(self.b,ARENA['bases'][0]);self.assertEqual(r['carrying'],[True,True])
        # Alice cannot score while her own flag is stolen. Avoid tagging Bob.
        self.state(self.b,[0,0,18,13]);self.state(self.a,ARENA['bases'][0]);self.assertEqual(r['scores'],[0,0])
        self.b['state'][6]=0;self.s.flags.tick()
        self.assertFalse(r['carrying'][1]);self.assertEqual(r['scores'],[1,0])

    def test_cancel_timeout_and_failed_result(self):
        r=self.duel();self.b['closing']=True;self.s.flags.tick();self.assertEqual(self.s.flags.runs,{})
        self.b['closing']=False;r=self.duel()
        self.s.db.execute("CREATE TRIGGER fail_flag BEFORE INSERT ON flag_results BEGIN SELECT RAISE(ABORT,'fixture'); END")
        self.now+=180
        for c in (self.a,self.b):c['state_time']=self.now
        self.s.flags.tick();self.assertEqual(self.s.flags.runs,{})
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM flag_results').fetchone()[0],0)

    def test_bases_reuse_source_verified_relay_ground(self):
        self.assertEqual(ARENA['bases'],[leg['start'] for leg in test_field_relays.COURSE['legs']])

    def test_no_overlapping_activity_and_immutable_arena(self):
        self.duel();self.chat(self.a,'/guild relay start petalburg_relay1')
        self.assertIsNone(self.s.relays._current('Alice'))
        bad=copy.deepcopy(ARENA);bad['title']='Changed'
        with self.assertRaises(ValueError):self.s.flags.publish(bad)
        bad=copy.deepcopy(ARENA);bad['id']='bad';bad['bases'][1]=bad['bases'][0]
        with self.assertRaises(ValueError):self.s.flags.publish(bad)

