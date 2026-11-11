import pathlib,sys,unittest,types
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from world.shared_strength import handle,encode
from world.strength_transaction import INITIAL
class Transport(unittest.TestCase):
 def test_authenticated_roundtrip(self):
  tag=types.SimpleNamespace(id=3,active=True,participants=('a','b'))
  p=types.SimpleNamespace(_tags={3:tag},_tag_actor={'a':3,'b':3})
  presence={'a':(24,14,9,15,0,0,1),'b':(24,14,11,16,0,0,1)}
  s=types.SimpleNamespace(link_protocol=p,_link_presence=lambda:presence)
  def h(w,line):return handle(s,{'id':w},line.encode())
  self.assertEqual(h('a','ST JOIN 3 1 '+encode(INITIAL)),[])
  self.assertEqual(len(h('b','ST JOIN 3 2 '+encode(INITIAL))),2)
  self.assertEqual(h('x','ST PROPOSE 3 1 0 2 10 15 11 15'),[])
  self.assertEqual(len(h('a','ST PROPOSE 3 1 0 2 10 15 11 15')),2)
  presence['a']=(*presence['a'][:6],0);presence['b']=(*presence['b'][:6],0)
  self.assertEqual(h('a','ST READY 3 1 1 '+encode(INITIAL)),[])
  self.assertEqual(len(h('b','ST READY 3 2 1 '+encode(INITIAL))),2)
  after=((2,11,15),*INITIAL[1:])
  self.assertEqual(h('a','ST APPLIED 3 1 1 '+encode(after)),[])
  result=h('b','ST APPLIED 3 2 1 '+encode(after))
  self.assertEqual(len(result),2);self.assertIn('COMPLETED',result[0][1])
  self.assertEqual(h('a','ST APPLIED 3 1 1 '+encode(after)),[])
  tag.active=False
  self.assertEqual(len(h('a','ST JOIN 3 3 '+encode(INITIAL))),2)
if __name__=='__main__':unittest.main()
