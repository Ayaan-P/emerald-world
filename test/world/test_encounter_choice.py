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
  import ast
  from pathlib import Path
  tree=ast.parse((next(p for p in Path(__file__).resolve().parents if (p/'world/link_protocol.py').is_file())/'world/server.py').read_text())
  method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_link_line')
  scope={};exec(compile(ast.Module(body=[method],type_ignores=[]),'server_slice','exec'),scope)
  class Host:
   _link_line=scope['_link_line']
   def _queue(self,c,l):self.messages.append(l)
   def _error(self,c,l):self.messages.append(l)
   def _deliver_links(self,l):self.messages.extend(l)
   def _link_presence(self):return self.pos
   def _region_scope(self,p):return p.get('scope')
  h=Host();h.link_protocol=LinkProtocol(clock=lambda:0,id_factory=lambda:123)
  h.pos={'alice':[1,4,5,5,4,7,1],'bob':[1,4,6,5,3,7,1]}
  for who,line in [('alice',b'T OFFER bob'),('bob',b'T ACCEPT 123'),('alice',b'L CHOICE HOLD 123 1')]:h.link_protocol.process(who,line,h.pos)
  a={'id':'alice','sock':1,'presence':{}};b={'id':'bob','sock':2,'presence':{}}
  h.connections={1:a,2:b};h.link_channels={'alice':a};h.peers={'alice':a['presence'],'bob':b['presence']};h.messages=[]
  h._link_line(a,b'L CHOICE TEAM 123 1');self.assertEqual(h.messages,['L ERROR UNAVAILABLE\n']);self.assertFalse(h.link_protocol._wire)
  h.link_channels['bob']=b;h.messages=[];b['presence']['in_generated_cave']=True;b['presence']['scope']='other'
  h._link_line(a,b'L CHOICE TEAM 123 1');self.assertEqual(h.messages,['L ERROR UNAVAILABLE\n'])
  b['presence'].clear();h.messages=[];h._link_line(a,b'L CHOICE TEAM 123 1');self.assertTrue(any('ADMIT' in row[1] for row in h.messages))

if __name__=='__main__':unittest.main()
