"""Real broker/session tests; no native rendering or save claims."""
import unittest
from world.link_protocol import LinkProtocol

class Choice(unittest.TestCase):
 def setUp(self):
  self.p=LinkProtocol(clock=lambda:0,id_factory=lambda:123)
  self.pos={'alice':[1,4,5,5,4,7,1],'bob':[1,4,6,5,3,7,1]}
  self.call('alice','T OFFER bob');self.call('bob','T ACCEPT 123')
 def call(self,who,line):return self.p.process(who,line.encode(),self.pos)
 def hold(self,who='alice',token=1):return self.call(who,f'L CHOICE HOLD 123 {token}')
 def team(self,who='alice',token=1):return self.call(who,f'L CHOICE TEAM 123 {token}')
 def test_choice_sends_no_offer_and_tag_survives_solo(self):
  self.assertEqual(self.hold(),[('alice','L HELD 123 1\n')]);self.assertFalse(self.p._wire)
  self.assertIn(('bob','L ERROR BUSY\n'),self.call('bob','L OFFER 4 alice'))
  self.assertEqual(self.call('alice','L CHOICE RELEASE 123 1'),[('alice','L RELEASED 123 1\n')])
  self.assertTrue(self.p._tags[123].active)
 def test_team_and_cancel_are_ordered(self):
  self.hold();r=self.team();self.assertIn(('alice','L ADMIT 124 4 0\n'),r)
  r=self.hold();self.assertEqual(r[-1],('alice','L HELD 123 1\n'))
  self.assertIn(('bob','L ABORT 124\n'),r);self.assertFalse(self.p._wire)
  self.assertIn(('bob','L ERROR BUSY\n'),self.call('bob','L OFFER 4 alice'))
 def test_crossing_existing_offer_aborts_before_hold_ack(self):
  self.call('bob','L OFFER 4 alice');r=self.hold()
  self.assertIn(('bob','L ABORT 124\n'),r);self.assertEqual(r[-1],('alice','L HELD 123 1\n'))
 def test_simultaneous_encounters_never_borrow_callbacks(self):
  for first,second in [('alice','bob'),('bob','alice')]:
   with self.subTest(first=first):
    self.setUp();self.hold(first);self.hold(second)
    self.assertIn((first,'L ERROR BUSY\n'),self.team(first))
    self.assertIn((second,'L ERROR BUSY\n'),self.team(second));self.assertFalse(self.p._wire)
 def test_crossing_team_then_local_capture(self):
  self.hold();self.team();r=self.hold('bob')
  self.assertIn(('alice','L ABORT 124\n'),r);self.assertFalse(self.p._wire)
 def test_wrong_token_cannot_release_and_disconnect_drops_holds(self):
  self.hold();self.call('alice','L CHOICE RELEASE 123 2');self.assertIn('alice',self.p._encounters)
  self.p.disconnect('alice');self.assertFalse(self.p._encounters);self.assertFalse(self.p._tags)
 def test_stale_tag_cannot_hold_new_pair(self):
  self.hold();self.call('alice','T END 123');self.assertFalse(self.p._encounters)
  self.call('alice','T OFFER bob');self.call('bob','T ACCEPT 124')
  self.assertEqual(self.hold(),[('alice','L ERROR DENIED\n')]);self.assertFalse(self.p._encounters)
 def test_release_live_session_rejected_and_no_progress_mutations(self):
  self.hold();self.team();self.call('alice','L CHOICE RELEASE 123 1')
  self.assertIn('alice',self.p._encounters)
  self.assertTrue(self.p._tags[123].active)
 def test_ack_delivery_is_not_a_wire_session(self):
  self.hold();self.assertTrue(self.p.delivery_current('alice','L HELD 123 1\n'))

class ServerGate(unittest.TestCase):
 def test_team_reuses_connected_peer_and_region_checks(self):
  import selectors,socket,tempfile
  from world.server import WorldServer
  root=tempfile.TemporaryDirectory(prefix='encounter-authority-')
  self.addCleanup(root.cleanup)
  h=WorldServer(root.name+'/socket',root.name+'/state')
  self.addCleanup(h.close)
  h.selector=selectors.DefaultSelector()
  h.link_protocol=LinkProtocol(clock=lambda:0,id_factory=lambda:123)
  pos={'alice':[1,4,5,5,4,7,1],'bob':[1,4,6,5,3,7,1]}
  for who,line in [('alice',b'T OFFER bob'),('bob',b'T ACCEPT 123'),('alice',b'L CHOICE HOLD 123 1')]:h.link_protocol.process(who,line,pos)
  channels={}
  for who in pos:
   sock,other=socket.socketpair();self.addCleanup(other.close)
   peer=dict(id=who,state=pos[who],closing=False)
   c=dict(id=who,sock=sock,presence=peer,closing=False,out=bytearray(),link=True)
   h.selector.register(sock,selectors.EVENT_READ,c)
   h.connections[sock]=c;h.peers[who]=peer;channels[who]=c
  a,b=channels['alice'],channels['bob']
  h.link_channels={'alice':a}
  h._link_line(a,b'L CHOICE TEAM 123 1')
  self.assertEqual(bytes(a['out']),b'L ERROR UNAVAILABLE\n');self.assertFalse(h.link_protocol._wire)
  a['out'].clear();h.link_channels['bob']=b;b['presence']['in_generated_cave']=True
  h._link_line(a,b'L CHOICE TEAM 123 1')
  self.assertEqual(bytes(a['out']),b'L ERROR UNAVAILABLE\n');self.assertFalse(h.link_protocol._wire)
  a['out'].clear();b['presence'].pop('in_generated_cave')
  h._link_line(a,b'L CHOICE TEAM 123 1')
  self.assertIn(b'L ADMIT',bytes(a['out']));self.assertIn(b'L ADMIT',bytes(b['out']))

if __name__=='__main__':unittest.main()
