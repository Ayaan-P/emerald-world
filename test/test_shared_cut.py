from pathlib import Path
import sys,unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from world.link_protocol import LinkProtocol
from world.shared_cut import handle
class Cut(unittest.TestCase):
 def setUp(self):
  self.p=LinkProtocol(clock=lambda:0,id_factory=lambda:7)
  self.presence={'a':[0,17,35,22,1,0,1],'b':[0,17,36,22,1,0,1]}
  self.p.process('a',b'T OFFER b',self.presence);self.p.process('b',b'T ACCEPT 7',self.presence)
  self.s=SimpleNamespace(link_protocol=self.p,_link_presence=lambda:self.presence)
 def cmd(self,actor,line):return handle(self.s,{'id':actor},line.encode())
 def join(self):
  self.assertEqual(len(self.cmd('a','CT JOIN 7 1 0 17')),1)
  self.assertEqual(len(self.cmd('b','CT JOIN 7 9 0 17')),1)
 def test_bilateral_opt_in_and_actual_recipient_visit(self):
  self.cmd('a','CT JOIN 7 1 0 17')
  self.assertEqual(len(self.cmd('a','CT CUT 7 1 1 0 17 3 35 22')),1)
  self.cmd('b','CT JOIN 7 9 0 17')
  out=self.cmd('a','CT CUT 7 1 2 0 17 3 35 22')
  self.assertEqual(out,[('a','CT ACK 7 1 2\n'),('b','CT APPLY 7 9 0 17 3 35 22\n')])
  self.assertEqual(len(self.cmd('a','CT CUT 7 1 2 0 17 4 35 22')),1)
 def test_revocation_disconnect_and_unready_have_no_replay(self):
  self.join();self.cmd('b','CT OFF 7 9');self.assertEqual(len(self.cmd('a','CT CUT 7 1 1 0 17 3 35 22')),1)
  self.cmd('b','CT JOIN 7 10 0 17');self.presence['b'][6]=0
  self.assertEqual(len(self.cmd('a','CT CUT 7 1 2 0 17 3 35 22')),1)
  self.presence['b'][6]=1;self.assertEqual(len(self.cmd('a','CT CUT 7 1 2 0 17 3 35 22')),1)
  self.p.disconnect('b');self.assertEqual(self.cmd('a','CT CUT 7 1 3 0 17 3 35 22'),[])
 def test_map_epoch_range_and_bad_fields(self):
  self.join()
  for line in ['CT CUT 8 1 1 0 17 3 35 22','CT CUT 7 2 1 0 17 3 35 22','CT CUT 7 1 1 0 18 3 35 22','CT CUT 7 1 1 0 17 3 100 100','CT CUT 7 1 1 0 17 0 35 22','CT CUT 7 1 0 0 17 3 35 22','CT CUT 7 -1 1 0 17 3 35 22']:
   self.assertEqual(self.cmd('a',line),[])
  self.cmd('a','CT JOIN 7 3 0 17');self.assertEqual(self.cmd('a','CT JOIN 7 1 0 17'),[])
  self.assertEqual(self.cmd('a','CT JOIN 7 3 0 18'),[])
  self.presence['b'][2]=80;self.assertEqual(len(self.cmd('a','CT CUT 7 3 5 0 17 3 35 22')),1)
 def test_stale_revocation_cannot_disable_new_visit(self):
  self.join();self.cmd('b','CT JOIN 7 10 0 17')
  self.cmd('b','CT OFF 7 9')
  self.assertEqual(self.cmd('a','CT CUT 7 1 1 0 17 3 35 22'),
                   [('a','CT ACK 7 1 1\n'),('b','CT APPLY 7 10 0 17 3 35 22\n')])
 def test_no_source_ready_no_completion_ack(self):
  self.join();self.presence['a'][6]=0
  self.assertEqual(self.cmd('a','CT CUT 7 1 1 0 17 3 35 22'),[])
  self.presence['a'][6]=1;self.assertEqual(len(self.cmd('a','CT CUT 7 1 1 0 17 3 35 22')),2)
if __name__=='__main__':unittest.main()
