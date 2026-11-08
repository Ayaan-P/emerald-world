"""CAVE17 exact-population revisions gate generated offers and actual arrivals."""
import unittest
from unittest.mock import patch
import test_character_place_offers as fixtures
from world.route_encounters import encode
from world.generated_goals import destination_available,observed_place
from world.server import WorldServer


def encounters(level=10):
    return dict(rate=12,wildlife=[dict(species='ZUBAT',level=level)]*12)

class WildlifePlaceOfferTests(fixtures.CharacterPlaceOfferTests):
    def setUp(self):
        original=WorldServer._replace_cave
        def replace(server,blob,**kw):
            return original(server,encode(blob,encounters()) if blob[:8]==b'EWGMAP0A' else blob,**kw)
        with patch.object(WorldServer,'_replace_cave',replace):super().setUp()
        self.assertEqual(self.server.shared_cave.version,17)

    def peer(self,name,capable=True,xl=True):
        token=self.server.create_identity(name)['token'];self.server.peers.pop(name,None)
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        role='SOCIALTRAVELCHATRALLY'+('CAVE17' if xl else '')+'CHAR1CHARQUEST1'+('PLACEQUEST1' if capable else '')
        self.assertIn('WELCOME',self.send(conn,f'HELLO 1 {name} {token} {role}'))
        self.state(conn,0,9,8,8);self.f.connections[name]=conn;return conn

    def enter(self,conn):
        self.assertIn('XLWILDLIFE',self.send(conn,'CAVE GET'))
        self.assertIn('CAVE OK',self.send(conn,'CAVE ACK '+self.revision))
        self.state(conn,*self.server.wilds_map,70,70)

    def test_cave16_only_cannot_see_accept_or_credit_wildlife_destination(self):
        token=self.server.create_identity('Legacy')['token']
        conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
        self.send(conn,f'HELLO 1 Legacy {token} SOCIALCAVE16CHAR1CHARQUEST1PLACEQUEST1')
        self.state(conn,0,9,8,8)
        self.assertEqual(self.send(conn,'CAVE GET'),'CAVE NONE\n')
        self.assertFalse(destination_available(self.server,conn,self.place,self.revision))
        self.assertNotIn('CHARACTER_PLACE_OFFER',self.server._snapshot(conn))
        # Even forged helper inputs cannot make CAVE16 satisfy CAVE17 admission.
        conn['cave_ack']=self.revision;conn['state']=[*self.server.wilds_map,70,70,4,7,1]
        self.assertIsNone(observed_place(self.server,conn))

    def test_table_only_change_invalidates_old_offer_identity(self):
        original=self.server.shared_cave.identity
        self.server._replace_cave(encode(self.blob,encounters(11)))
        self.assertNotEqual(self.server.shared_cave.identity,original)
        self.assertFalse(destination_available(self.server,self.alice,self.place,original))
        self.assertNotIn('CHARACTER_PLACE_OFFER',self.server._snapshot(self.alice))

if __name__=='__main__':unittest.main()
