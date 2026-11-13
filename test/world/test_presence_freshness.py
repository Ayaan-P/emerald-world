"""Actual authority/link protocol with deterministic clock and mocked transport."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from world.server import WorldServer

class Clock:
    now=100.0
    def __call__(self): return self.now

class Server(WorldServer):
    def _queue(self,conn,text): conn['out'].extend(text.encode())

class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock(); self.patcher=patch('world.server.time.monotonic',self.clock);self.patcher.start()
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.s=Server(root/'socket',root/'state')
        self.peers={};self.links={}
        for i,name in enumerate(('alice','bob')):
            self.s.create_identity(name)
            p={'id':name,'seq':-1,'social':True,'chat':False,'travel':False,'field':True,'state':[0,1,10+i,12,4,7,1], 'state_time':self.clock.now,'closing':False,'out':bytearray(),'sock':object()}
            link={'id':name,'presence':p,'admin':False,'closing':False,'out':bytearray(),'sock':object()}
            self.peers[name]=p;self.links[name]=link
            self.s.peers[name]=p;self.s.link_channels[name]=link;self.s.connections[link['sock']]=link
    def tearDown(self):
        self.s.connections.clear();self.s.close();self.tmp.cleanup();self.patcher.stop()
    def link(self,name,line): self.s._link_line(self.links[name],line.encode())
    def clear(self):
        for c in self.links.values(): c['out'].clear()
    def test_expired_presence_does_not_render_as_a_ghost(self):
        self.assertIn('PEER bob ',self.s._snapshot(self.peers['alice']))
        self.clock.now+=4;self.peers['alice']['state_time']=self.clock.now
        self.assertNotIn('PEER bob ',self.s._snapshot(self.peers['alice']))
        self.peers['bob']['state_time']=self.clock.now
        self.assertIn('PEER bob ',self.s._snapshot(self.peers['alice']))

    def test_stale_travel_occupant_remains_in_roster_with_zero_lifetime(self):
        self.peers['alice']['travel']=True
        self.clock.now+=4;self.peers['alice']['state_time']=self.clock.now
        snapshot=self.s._snapshot(self.peers['alice'])
        self.assertIn('TRAVEL 1\nFRIEND bob 0 1 11 12 4 7 1 0\n',snapshot)
        self.assertNotIn('PEER bob ',snapshot)

    def test_expired_trainer_cannot_receive_field_meeting(self):
        self.clock.now+=4;self.peers['alice']['state_time']=self.clock.now
        self.s._line(self.peers['alice'],b'MEET 1 bob')
        self.assertNotIn('meeting',self.peers['bob'])

    def test_busy_fresh_field_trainer_renders_but_cannot_meet(self):
        self.peers['bob']['state'][6] = 0
        self.assertIn('PEER bob 0 1 11 12 4 7 0', self.s._snapshot(self.peers['alice']))
        self.s._line(self.peers['alice'], b'MEET 1 bob')
        self.assertNotIn('meeting', self.peers['bob'])
        self.clock.now += 4
        self.assertNotIn('PEER bob ', self.s._snapshot(self.peers['alice']))

    def test_expired_initiator_cannot_send_meeting(self):
        self.clock.now += 4
        self.peers['bob']['state_time'] = self.clock.now
        self.s._line(self.peers['alice'], b'MEET 1 bob')
        self.assertNotIn('meeting', self.peers['bob'])

    def test_missing_or_future_timestamp_does_not_render(self):
        for timestamp in (None, self.clock.now + 1):
            with self.subTest(timestamp=timestamp):
                self.peers['bob']['state_time'] = timestamp
                self.assertNotIn('PEER bob ', self.s._snapshot(self.peers['alice']))

    def test_presence_expires_at_three_seconds(self):
        self.clock.now += 3
        self.assertNotIn('bob', self.s._link_presence())
        self.assertNotIn('PEER bob ', self.s._snapshot(self.peers['alice']))

    def test_combined_registry_unadmitted_target_is_not_visible_or_invitable(self):
        from world.combined_regions import DIGEST
        self.s.combined_regions = True
        self.links['alice']['registry_digest'] = DIGEST
        self.assertNotIn('PEER bob ', self.s._snapshot(self.peers['alice']))
        self.s._line(self.peers['alice'], b'MEET 1 bob')
        self.assertNotIn('meeting', self.peers['bob'])
        self.link('alice', 'L OFFER 1 bob')
        self.assertIn(b'L ERROR', self.links['alice']['out'])
        self.links['bob']['registry_digest'] = DIGEST
        self.assertIn('PEER bob ', self.s._snapshot(self.peers['alice']))
        self.s._line(self.peers['alice'], b'MEET 2 bob')
        self.assertIn('meeting', self.peers['bob'])

    def test_active_trade_is_not_aborted_when_field_state_expires(self):
        self.link('alice', 'L OFFER 3 bob')
        sid = self.links['bob']['out'].decode().split()[2]
        self.clear()
        self.link('bob', 'L ACCEPT ' + sid)
        self.clear()
        self.clock.now += 4
        self.s._poll_presence(self.clock.now)
        zero = '0' * 32
        self.link('alice', f'L EVENT 1 {sid} 3 0 1 0 4369 {zero}')
        self.link('bob', f'L EVENT 1 {sid} 3 1 1 0 4369 {zero}')
        self.assertIn(b'L COMMIT', self.links['alice']['out'])
        self.assertIn(b'L COMMIT', self.links['bob']['out'])

    def test_cave_scopes_survive_freshness_filtering(self):
        from world.shared_cave import SharedCave
        from world.link_sessions import LinkError
        rows = ['#' * 31] + ['#' + '.' * 29 + '#'] * 29 + ['#' * 31]
        cave = SharedCave(b'EWGMAP01' + ''.join(rows).encode('ascii'))
        changed = list(rows)
        changed[2] = '##' + '.' * 28 + '#'
        other = SharedCave(b'EWGMAP01' + ''.join(changed).encode('ascii'))
        for peer in self.peers.values():
            peer['state'][:2] = list(self.s.cave_map)
            peer['region_cave'] = cave
            peer['cave_ack'] = cave.identity
        self.assertIn('PEER bob ', self.s._snapshot(self.peers['alice']))
        self.s.link_protocol.sessions._near(self.s._link_presence(), 'alice', 'bob', coop=True)
        self.peers['bob'].update(region_cave=other, cave_ack=other.identity)
        presence = self.s._link_presence()
        self.assertEqual(presence.scopes['bob'], other.identity)
        with self.assertRaisesRegex(LinkError, 'different_region'):
            self.s.link_protocol.sessions._near(presence, 'alice', 'bob', coop=True)
        self.assertNotIn('PEER bob ', self.s._snapshot(self.peers['alice']))
        self.peers['bob']['cave_ack'] = cave.identity
        self.assertNotIn('bob', self.s._link_presence())
        self.clock.now += 4
        self.assertFalse(self.s._link_presence())

    def test_stale_player_cannot_be_invited(self):
        self.clock.now+=4
        self.peers['alice']['state_time']=self.clock.now
        self.link('alice','L OFFER 1 bob')
        self.assertNotIn(b'L OFFER ',self.links['bob']['out'])
        self.assertIn(b'L ERROR',self.links['alice']['out'])
    def test_expired_position_cannot_accept_offer(self):
        self.link('alice','L OFFER 1 bob')
        offer=self.links['bob']['out'].decode().split();self.assertEqual(offer[:2],['L','OFFER']);sid=offer[2]
        self.clear();self.clock.now+=4;self.peers['bob']['state_time']=self.clock.now
        self.link('bob','L ACCEPT '+sid)
        self.assertNotIn(b'L ADMIT',self.links['bob']['out'])
        self.assertIn(b'L ERROR',self.links['bob']['out'])
    def test_tag_consent_fails_if_other_position_expired(self):
        self.link('alice','T OFFER bob');sid=self.links['bob']['out'].decode().split()[2]
        self.clear();self.clock.now+=4;self.peers['bob']['state_time']=self.clock.now
        self.link('bob','T ACCEPT '+sid)
        self.assertNotIn(b'T ACTIVE',self.links['bob']['out'])
        self.assertIn(b'T ERROR',self.links['bob']['out'])

    def test_missing_timestamp_fails_closed(self):
        del self.peers['bob']['state_time']
        self.link('alice','T OFFER bob')
        self.assertNotIn(b'T OFFER',self.links['bob']['out'])
        self.assertIn(b'T ERROR',self.links['alice']['out'])

    def test_fresh_players_can_offer_and_accept(self):
        self.link('alice','L OFFER 1 bob');sid=self.links['bob']['out'].decode().split()[2]
        self.clear();self.link('bob','L ACCEPT '+sid)
        self.assertIn(b'L ADMIT',self.links['alice']['out']);self.assertIn(b'L ADMIT',self.links['bob']['out'])
    def test_expired_active_tag_loses_range_without_new_state(self):
        self.link('alice','T OFFER bob');sid=self.links['bob']['out'].decode().split()[2]
        self.clear();self.link('bob','T ACCEPT '+sid);self.clear()
        self.clock.now+=4
        self.s._poll_presence(self.clock.now)
        self.assertIn(f'T RANGE {sid} 0'.encode(),self.links['alice']['out'])
        self.assertIn(f'T RANGE {sid} 0'.encode(),self.links['bob']['out'])
        self.clear()
        for peer in self.peers.values(): peer['state_time']=self.clock.now
        self.s._poll_presence(self.clock.now)
        self.assertIn(f'T RANGE {sid} 1'.encode(),self.links['alice']['out'])

    def test_idle_authority_loop_releases_expired_tag_range(self):
        self.link('alice','T OFFER bob');sid=self.links['bob']['out'].decode().split()[2]
        self.clear();self.link('bob','T ACCEPT '+sid);self.clear()
        clock,stop=self.clock,self.s.stopping
        class IdleSelector:
            def select(self,timeout):
                clock.now+=4;stop.set();return []
        self.s.selector=IdleSelector()
        try:self.s._loop()
        finally:self.s.selector=None
        self.assertIn(f'T RANGE {sid} 0'.encode(),self.links['alice']['out'])
        self.assertIn(f'T RANGE {sid} 0'.encode(),self.links['bob']['out'])

    def test_active_link_is_not_aborted_when_field_state_expires(self):
        self.link('alice','L OFFER 1 bob');sid=self.links['bob']['out'].decode().split()[2]
        self.clear();self.link('bob','L ACCEPT '+sid);self.clear()
        self.clock.now += 4
        self.s._poll_presence(self.clock.now)
        zero='0'*32
        self.link('alice',f'L EVENT 1 {sid} 1 0 1 0 8755 {zero}')
        self.link('bob',f'L EVENT 1 {sid} 1 1 1 0 8755 {zero}')
        self.assertIn(b'L COMMIT',self.links['alice']['out'])
        self.assertIn(b'L COMMIT',self.links['bob']['out'])

if __name__=='__main__': unittest.main()
