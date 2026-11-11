import pathlib,sys,types,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from world.shared_contests import handle
from world.link_protocol import LinkProtocol,_Tag
from world.link_sessions import RegionPresence
class Transport(unittest.TestCase):
 def setup(self):
  self.p=LinkProtocol();tag=_Tag(8,'a','b',999999999,active=True)
  self.p._tags[8]=tag;self.p._tag_actor={'a':8,'b':8}
  self.pres=RegionPresence({'a':(13,4,5,5,1,1,0),'b':(13,4,7,5,1,1,0)},{'a':'hoenn','b':'hoenn'})
  self.channels={w:{'id':w} for w in ('a','b')}
  self.s=types.SimpleNamespace(link_protocol=self.p,link_channels=self.channels,_link_presence=lambda:self.pres)
 def call(self,w,line):return handle(self.s,self.channels[w],line.encode())
 def test_full_counter_native_admission_and_result_gate(self):
  self.setup();self.assertEqual(self.call('a','CN JOIN 1 1 2 8'),[])
  prepared=self.call('b','CN JOIN 1 1 2 8');self.assertEqual(len(prepared),2)
  ticket=int(prepared[0][1].split()[3]);self.assertEqual(self.call('a',f'CN READY {ticket} 1 1 8'),[])
  admitted=self.call('b',f'CN READY {ticket} 1 1 8');self.assertEqual(len(admitted),4)
  wire=int(admitted[0][1].split()[3]);self.assertEqual(self.p._wire[wire].mode,5)
  # Genuine native session OPENs, not a separate simulated contest.
  zero='0'*32
  a=self.p.process('a',f'L EVENT 1 {wire} 5 0 1 0 26114 {zero}'.encode(),self.pres)
  b=self.p.process('b',f'L EVENT 1 {wire} 5 1 1 0 26114 {zero}'.encode(),self.pres)
  self.assertFalse(any('ERROR' in x[1] for x in a+b));self.assertTrue(any('L COMMIT 1' in x[1] for x in b))
  fingerprint='a'*80
  self.assertEqual(self.call('a',f'CN RESULT {wire} 2 0213 {fingerprint}'),[])
  result=self.call('b',f'CN RESULT {wire} 2 0213 {fingerprint}')
  self.assertEqual(len(result),2);self.assertIn('AGREED',result[0][1])
  self.call('a',f'CN SAVED {wire} 1');self.call('b',f'CN SAVED {wire} 0')
  self.assertEqual(self.s._contest_sessions['results'][wire].saved,{'a'})
 def test_different_scopes_never_admit(self):
  self.setup();self.pres.scopes['b']='other-world'
  self.call('a','CN JOIN 1 1 2 8');prepared=self.call('b','CN JOIN 1 1 2 8');ticket=int(prepared[0][1].split()[3])
  self.call('a',f'CN READY {ticket} 1 1 8');self.call('b',f'CN READY {ticket} 1 1 8');self.assertFalse(self.p._wire)
 def test_generic_offer_cannot_bypass_counter(self):
  self.setup();r=self.p.process('a',b'L OFFER 5 b',self.pres);self.assertTrue(any('ERROR' in x[1] for x in r));self.assertFalse(self.p._wire)
if __name__=='__main__':unittest.main()
