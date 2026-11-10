"""Release boundaries exercised through actual authority admission and dispatch."""
import unittest
import test_region_characters as fixture

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
