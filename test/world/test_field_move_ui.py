import unittest,socket
import test_overworld_moves
from world.field_move_ui import handle
from world import actor_objects
class UI(unittest.TestCase):
 def setUp(self):
  self.f=test_overworld_moves.MoveEffects();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=self.f.peer
  left,right=socket.socketpair();self.addCleanup(right.close);self.addCleanup(left.close)
  self.c=dict(id=self.p['id'],presence=self.p,sock=left,out=bytearray(),link=True)
  self.s.connections[left]=self.c;self.s.link_channels[self.p['id']]=self.c
 def get(self):
  result=handle(self.s,self.c,b'FM GET 1 52').split();self.assertEqual(result[:3],['FM','OFFER','1']);return result[3]
 def test_offer_selection_ack_only_after_admission_and_replay(self):
  token=self.get();self.assertIsNone(self.s.deployment)
  result=handle(self.s,self.c,('FM USE 1 '+token+' turn').encode());self.assertEqual(result,'FM WAIT 1\n')
  self.assertEqual(self.s.objects[-1]['text'],'First face.');self.assertEqual(handle(self.s,self.c,('FM USE 1 '+token+' turn').encode()),'FM FAIL 1\n')
  self.f.admit(1);self.assertEqual(self.s.objects[-1]['text'],'Second face.')
  self.assertIn(b'FM DONE 1 1\n',self.c['out'])
 def test_failed_admission_and_stale_facing(self):
  token=self.get();self.p['state'][4]=2
  self.assertEqual(handle(self.s,self.c,('FM USE 1 '+token+' turn').encode()),'FM FAIL 1\n');self.assertIsNone(self.s.deployment)
  self.p['state'][4]=1;token=self.get();handle(self.s,self.c,('FM USE 1 '+token+' turn').encode());self.s.deployment=None;actor_objects.poll_player(self.s)
  self.assertIn(b'FM DONE 1 0\n',self.c['out']);self.assertEqual(self.s.objects[-1]['text'],'First face.')
 def test_wrong_move_sequence_and_wire(self):
  self.assertEqual(handle(self.s,self.c,b'FM GET 1 55'),'FM FAIL 1\n')
  token=self.get();self.assertEqual(handle(self.s,self.c,('FM USE 2 '+token+' turn').encode()),'FM FAIL 2\n')
  self.s._line(self.c,b'FM GET 3 52');self.assertIn(b'FM OFFER 3 ',self.c['out'])
