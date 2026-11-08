"""Two real authority regions and the reference client, with in-memory wire I/O."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_shared_generated_cave import MemoryAuthority, BLOB
from world.client import RegionClient
from world.link_sessions import LinkError


class WireSocket:
    def __init__(self,server):
        self.server=server
        self.conn=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=self)
    def settimeout(self,_): pass
    def connect(self,_): pass
    def makefile(self,_): return self
    def close(self): pass
    def sendall(self,data):
        for line in data.splitlines(): self.server._line(self.conn,line)
    def readline(self,limit=65536):
        out=self.conn['out'];end=out.find(b'\n')+1
        if not end: raise AssertionError('authority did not produce a response')
        row=bytes(out[:min(end,limit)]);del out[:len(row)];return row


class RegionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.server=self.open()
        self.a=self.server._replace_cave(BLOB,label='Harbor')
        modified=bytearray(BLOB);modified[8+2*31+2]=ord('#')
        self.b=self.server._replace_cave(bytes(modified),label='Forest')
        self.ra=self.admin(dict(command='open_region',revision=self.a))
        self.rb=self.admin(dict(command='open_region',revision=self.b))
        self.assertTrue(self.ra['ok']);self.assertTrue(self.rb['ok'])
        self.clients={};self.identities={}
    def open(self):
        return MemoryAuthority(self.root/'s',self.root/'world',persist_generated_cave=True,archive_generated_areas=True)
    def tearDown(self):self.server.close();self.tmp.cleanup()
    def admin(self,request):
        conn=dict(out=bytearray(),closing=False)
        self.server._admin_line(conn,json.dumps(request).encode());return json.loads(conn['out'])
    def connect(self,name):
        identity=self.server.create_identity(name);self.identities[name]=identity;sock=WireSocket(self.server)
        with patch('world.client.socket.socket',return_value=sock):
            client=RegionClient('socket',name,identity['token'])
        self.clients[name]=client
        client.send_state(1,0,9,8,8,1,7,1,'a'*16,'b'*16)
        return client
    def enter(self,client,x=1,y=1):
        peer=client.sock.conn
        client.send_state(peer['seq']+1,*self.server.cave_map,x,y,1,7,1,'a'*16,'b'*16)
        self.assertFalse(peer['closing'])
    def outside(self,client):
        client.send_state(client.sock.conn['seq']+1,0,9,8,8,1,7,1,'a'*16,'b'*16)

    def test_reference_clients_occupy_two_places_without_global_replacement(self):
        alice,bob,carol=[self.connect(n) for n in ('Alice','Bob','Carol')]
        self.assertEqual(alice.select_region(self.ra['place_id'])['template'],BLOB)
        bob.select_region(self.rb['place_id']);carol.select_region(self.ra['place_id'])
        for client in (alice,bob,carol):self.enter(client)
        self.assertEqual(self.server.shared_cave.identity,self.b)
        snapshot=self.server._snapshot(alice.sock.conn)
        self.assertIn('PEER Carol ',snapshot);self.assertNotIn('PEER Bob ',snapshot)
        self.assertNotIn('PEER Alice ',self.server._snapshot(bob.sock.conn))
        presence=self.server._link_presence()
        self.server.link_protocol.sessions._near(presence,'Alice','Carol',coop=True)
        with self.assertRaisesRegex(LinkError,'different_region'):
            self.server.link_protocol.sessions._near(presence,'Alice','Bob',coop=True)
        # Default replacement cannot reset pinned occupants in another region.
        changed=bytearray(BLOB);changed[8+3*31+3]=ord('#')
        self.server._replace_cave(bytes(changed))
        self.assertEqual(alice.sock.conn['cave_ack'],self.a)
        self.assertEqual(bob.sock.conn['cave_ack'],self.b)
        self.enter(alice,2,2)  # Walkable in harbor, blocked in forest.
        self.assertEqual(alice.sock.conn['state'][2:4],[2,2])
        # Selecting from inside is refused without losing source admission.
        with self.assertRaisesRegex(ValueError,'refused'):alice.select_region(self.rb['place_id'])
        self.assertEqual(alice.sock.conn['cave_ack'],self.a)
        self.outside(alice)
        alice.select_region(self.rb['place_id']);self.enter(alice)
        self.assertIn('PEER Bob ',self.server._snapshot(alice.sock.conn))
        self.assertNotIn('PEER Carol ',self.server._snapshot(alice.sock.conn))

    def test_real_link_dispatch_separates_regions_and_selection_cannot_carry_sessions(self):
        alice,bob,carol=[self.connect(n) for n in ('Alice','Bob','Carol')]
        for client,region in ((alice,self.ra),(bob,self.rb),(carol,self.ra)):
            client.select_region(region['place_id']);self.enter(client)
        links={}
        for name in self.clients:
            wire=WireSocket(self.server)
            self.server.connections[wire]=wire.conn
            wire.sendall(('HELLO 1 '+name+' '+self.identities[name]['token']+' LINK\n').encode())
            self.assertIn(b'WELCOME',wire.conn['out']);wire.conn['out'].clear();links[name]=wire
        links['Alice'].sendall(b'L OFFER 4 Bob\n')
        self.assertEqual(links['Alice'].conn['out'],b'L ERROR UNAVAILABLE\n')
        links['Alice'].conn['out'].clear()
        links['Alice'].sendall(b'T OFFER Carol\n')
        offered=bytes(links['Carol'].conn['out']).decode().split()
        self.assertEqual(offered[:2],['T','OFFER'])
        links['Carol'].conn['out'].clear()
        links['Carol'].sendall(('T ACCEPT '+offered[2]+'\n').encode())
        self.assertIn(b'T ACTIVE',links['Alice'].conn['out'])
        links['Alice'].conn['out'].clear();links['Carol'].conn['out'].clear()
        links['Alice'].sendall(b'L OFFER 4 Carol\n')
        self.assertIn(b'L ADMIT',links['Alice'].conn['out'])
        self.assertIn(b'L ADMIT',links['Carol'].conn['out'])
        self.outside(alice)
        with self.assertRaisesRegex(ValueError,'refused'):
            alice.select_region(self.rb['place_id'])
        self.assertEqual(alice.sock.conn['region_place'],self.ra['place_id'])
        generated=self.server.inspect()['players']
        self.assertEqual(next(p for p in generated if p['id']=='Bob')['generated_place']['place_id'],self.rb['place_id'])

    def test_region_collision_uses_selected_revision_and_old_clients_keep_default(self):
        alice=self.connect('Alice');alice.select_region(self.rb['place_id'])
        alice.send_state(2,*self.server.cave_map,2,2,1,7,1,'a'*16,'b'*16)
        self.assertTrue(alice.sock.conn['closing'])
        identity=self.server.create_identity('Legacy');legacy=WireSocket(self.server)
        legacy.sendall(('HELLO 1 Legacy '+identity['token']+' SOCIALCAVE\n').encode())
        self.assertNotIn(b'REGION',legacy.conn['out']);legacy.conn['out'].clear()
        legacy.sendall(b'CAVE GET\n');self.assertIn(('CAVE BEGIN '+self.b).encode(),legacy.conn['out'])
        legacy.conn['out'].clear();legacy.sendall(('REGION SELECT '+self.ra['place_id']+'\n').encode())
        self.assertEqual(legacy.conn['out'],b'REGION REFUSED\n')

    def test_mutable_formats_are_not_opened_and_default_edits_do_not_touch_regions(self):
        import test_shared_terrain_world
        alice=self.connect('Alice');alice.select_region(self.ra['place_id']);self.enter(alice)
        event_area=self.server._replace_cave(test_shared_terrain_world.SharedTerrainWorld().blob())
        self.assertFalse(self.admin(dict(command='open_region',revision=event_area))['ok'])
        result=self.server.set_shared_geometry(event_area,[dict(x=2,y=2,terrain='tall_grass')])
        self.assertTrue(result['changed'])
        self.assertEqual(alice.sock.conn['cave_ack'],self.a)
        self.enter(alice,2,2)
        self.assertEqual(alice.sock.conn['state'][2:4],[2,2])

    def test_region_pins_survive_restart_and_source_history_is_not_a_visit(self):
        events=self.server.memory.history()['events']
        self.assertEqual([e['event'] for e in events[-2:]],['region_opened','region_opened'])
        self.server.close();self.server=self.open()
        alice=self.connect('Alice');alice.select_region(self.ra['place_id']);self.enter(alice)
        self.assertEqual(self.server.memory.history()['events'],events)
        self.assertFalse(self.admin(dict(command='open_region',revision='f'*64))['ok'])
        # Reopening is idempotent and cannot manufacture another opening event.
        self.assertFalse(self.admin(dict(command='open_region',revision=self.a))['changed'])


if __name__=='__main__':unittest.main()
