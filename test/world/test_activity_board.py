import unittest
import test_field_relays
from world.field_story_bundle import CURATED


class ActivityBoardTests(unittest.TestCase):
    setUp=test_field_relays.FieldRelayTests.setUp
    connect=test_field_relays.FieldRelayTests.connect
    chat=test_field_relays.FieldRelayTests.chat
    state=test_field_relays.FieldRelayTests.state

    def test_catalog_and_all_three_opt_in_join_paths(self):
        self.s.mysteries.publish(CURATED['mystery'])
        listing=self.chat(self.a,'/guild play list')
        for kind in ('mystery','relay','flag'):self.assertTrue(any(kind+' ' in x for x in listing))
        self.assertFalse(any('SUNRISE' in x or 'weather vane' in x for x in listing))
        for kind,key in [('mystery','signal_v2'),('relay','petalburg_relay1'),('flag','petalburg_flags1')]:
            self.chat(self.a,f'/guild play start {kind} {key}')
            self.assertTrue(any('No shared' in x for x in self.chat(self.b,'/guild play open')))
            self.chat(self.a,f'/guild play share {kind}')
            self.assertTrue(any('Alice' in x for x in self.chat(self.b,'/guild play open')))
            joined=self.chat(self.b,'/guild play join Alice')
            self.assertFalse(any('unavailable' in x for x in joined))
            self.assertIsNotNone(self.s.activities.current('Bob',kind))
            self.assertNotIn('Alice',self.s.activities.adverts)
            status=self.chat(self.b,'/guild play status')
            self.assertTrue(any(kind.upper() in x for x in status))
            self.s.activities.dispatch(self.a,kind,['leave'])

    def test_adverts_are_explicit_guild_scoped_and_hide_does_not_cancel(self):
        self.chat(self.c,'/guild leave')
        self.chat(self.c,'/guild create Outsiders')
        self.chat(self.a,'/guild play start relay petalburg_relay1')
        self.chat(self.a,'/guild play share relay')
        self.assertTrue(any('No shared' in x for x in self.chat(self.c,'/guild play open')))
        self.assertTrue(any('unavailable' in x for x in self.chat(self.c,'/guild play join Alice')))
        self.chat(self.a,'/guild play hide')
        self.assertIsNotNone(self.s.relays._current('Alice'))
        self.assertTrue(any('No shared' in x for x in self.chat(self.b,'/guild play open')))
        self.assertEqual(self.b['chat_history'],[]) # polling replies only; no unsolicited board broadcast

    def test_stale_host_and_reconnect_cannot_keep_invitation_visible(self):
        self.chat(self.a,'/guild play start flag petalburg_flags1')
        self.chat(self.a,'/guild play share flag')
        self.s.peers['Alice']=dict(self.a)
        self.assertTrue(any('No shared' in x for x in self.chat(self.b,'/guild play open')))
        self.assertEqual(self.s.activities.adverts,{})

    def test_legacy_and_bad_page_never_leak_invitation(self):
        self.a['private_commands']=False
        self.assertTrue(any('matched RC12' in x for x in self.chat(self.a,'/guild play list')))
        self.a['private_commands']=True
        for page in ('0','-1','999999','x'):
            self.assertTrue(any('PAGE' in x for x in self.chat(self.a,'/guild play list '+page)))
