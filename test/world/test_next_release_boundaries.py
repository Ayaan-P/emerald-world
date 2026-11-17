"""Release boundaries exercised through actual authority admission and dispatch."""
import unittest
import test_region_characters as fixture

from world import canonical_cast, actor_agreements

class CanonicalReceiptEvidenceTests(unittest.TestCase):
    def test_public_story_receipt_can_ground_only_its_author_decision(self):
        event=dict(event='public_story_choice_committed',publication='explicit_public_story_choice',author='canon_rydel')
        row=dict(version=2,places=['native:Route102'])
        self.assertTrue(canonical_cast.reaction_activity(event,'canon_rydel',row))
        self.assertTrue(canonical_cast.decision_evidence(event,'canon_rydel',row))
        self.assertFalse(canonical_cast.decision_evidence(event,'canon_steven',row))
        self.assertFalse(canonical_cast.decision_evidence(dict(event,publication='private'),'canon_rydel',row))

    def test_agreement_receipt_can_ground_only_participant_decisions(self):
        event=dict(event='actor_agreement_proposed',basis=actor_agreements.BASIS,participants=['canon_rydel','canon_steven'])
        row=dict(version=2,places=['native:Route102'])
        self.assertTrue(canonical_cast.reaction_activity(event,'canon_rydel',row))
        self.assertTrue(canonical_cast.decision_evidence(event,'canon_rydel',row))
        self.assertFalse(canonical_cast.decision_evidence(event,'canon_wally',row))
        self.assertFalse(canonical_cast.decision_evidence(dict(event,basis='untrusted'),'canon_rydel',row))

class NextReleaseBoundaryTests(unittest.TestCase):
    def test_spectating_is_unavailable_even_when_a_peer_advertises_it(self):
        f=fixture.RegionCharacterTests();f.setUp();self.addCleanup(f.doCleanups)
        server=f.server
        token=server.create_identity('BoundaryTest')['token']
        peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        role='SOCIALCHAR1CHARPK1OUTBREAK1CONTEST1RENTALS1WORLDTV1CHARFORM1FISHING1WATCH1'
        self.assertIn('WELCOME',f.send(peer,f'HELLO 1 BoundaryTest {token} {role}'))
        self.assertFalse(peer.get('battle_watch_capable'))
        response=f.send(peer,'WATCH SHARE 1')
        self.assertNotIn('WATCH_PERMISSION 1',response)
        self.assertFalse(peer.get('watch_sharing'))
        self.assertNotIn('WATCH_VIEW',server._snapshot(peer))
