"""Canonical relationship continuity follows exact private native acknowledgments."""
import unittest
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast
from world.canonical_memory import acknowledge
from world.canonical_reflection import claim,finish,snapshot

class PerspectiveTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.peer=self.f.prepare_private_reflection();self.s=self.f.s
 def request(self,note='Rydel will offer options rather than assume a racing partner.'):
  preview=cast.guild_command(self.s,self.peer,['rydel','reflect'])
  self.assertTrue(any('retained for this save' in line for line in preview))
  cast.guild_command(self.s,self.peer,['rydel','reflect','confirm',self.peer['cast_reflection_preview']['nonce']])
  job=claim(self.s)['request'];self.assertIsNotNone(job)
  self.assertTrue(finish(self.s,job['id'],job['lease'],dict(reply='We can consider the options together.',interpretation=note))['ok'])
  return job
 def count(self):return self.s.db.execute('SELECT count(*) FROM canonical_perspectives').fetchone()[0]
 def test_acknowledged_perspective_survives_and_informs_next_consented_reply(self):
  history=deepcopy(self.s.memory.history());inspection=deepcopy(self.s.inspect())
  job=self.request();self.assertIsNone(job['context']['prior_character_perspective']);self.assertEqual(self.count(),0)
  response=cast.response(self.s,self.peer,'a'*32,'rydel');self.assertEqual(self.count(),0)
  acknowledge(self.s,self.peer,'a'*32,'canon_rydel',response['digest']);self.assertEqual(self.count(),1)
  self.assertEqual(self.s.memory.history(),history);self.assertEqual(self.s.inspect(),inspection)
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.peer=self.f.peer();cast.response(self.s,self.peer,'a'*32,'rydel')
  self.assertIn('offer options',snapshot(self.s,'Alice','canon_rydel','a'*32)[2]['prior_character_perspective'])
  job=self.request('Rydel still leaves the choice open and is ready to discuss a different plan.')
  self.assertIn('offer options',job['context']['prior_character_perspective'])
  response=cast.response(self.s,self.peer,'a'*32,'rydel');acknowledge(self.s,self.peer,'a'*32,'canon_rydel',response['digest'])
  self.assertEqual(self.count(),1)
  self.assertIn('different plan',snapshot(self.s,'Alice','canon_rydel','a'*32)[2]['prior_character_perspective'])
  self.assertTrue(any('different plan' in line for line in cast.guild_command(self.s,self.peer,['rydel','memory'])))
 def test_two_saves_other_player_and_forget_are_isolated(self):
  self.request();response=cast.response(self.s,self.peer,'a'*32,'rydel');acknowledge(self.s,self.peer,'a'*32,'canon_rydel',response['digest'])
  response=cast.response(self.s,self.peer,'b'*32,'rydel');acknowledge(self.s,self.peer,'b'*32,'canon_rydel',response['digest'])
  self.assertIsNone(snapshot(self.s,'Alice','canon_rydel','b'*32)[2]['prior_character_perspective'])
  self.assertFalse(any('offer options' in line for line in cast.guild_command(self.s,self.peer,['rydel','memory'])))
  bob=self.f.peer('Bob');cast.guild_command(self.s,bob,['rydel','remember','on'])
  response=cast.response(self.s,bob,'a'*32,'rydel');acknowledge(self.s,bob,'a'*32,'canon_rydel',response['digest'])
  self.assertIsNone(snapshot(self.s,'Bob','canon_rydel','a'*32)[2]['prior_character_perspective'])
  cast.guild_command(self.s,self.peer,['rydel','forget']);self.assertEqual(self.count(),0)
 def test_unseen_withdrawn_or_replaced_reply_cannot_become_memory(self):
  self.request();response=cast.response(self.s,self.peer,'a'*32,'rydel')
  # A replacement request invalidates the old generated reply even if the
  # previously issued display acknowledgment arrives later.
  self.request('Rydel is considering another way to explain the choices.')
  acknowledge(self.s,self.peer,'a'*32,'canon_rydel',response['digest']);self.assertEqual(self.count(),0)
  self.request();response=cast.response(self.s,self.peer,'a'*32,'rydel')
  cast.guild_command(self.s,self.peer,['rydel','remember','off'])
  acknowledge(self.s,self.peer,'a'*32,'canon_rydel',response['digest']);self.assertEqual(self.count(),0)
