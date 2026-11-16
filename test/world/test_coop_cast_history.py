"""Focused production-function checks; no linked engine or controller playtest."""
from pathlib import Path
import ast,importlib.util,json,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=Path(__file__).resolve().parents[2]
def function(text,name):
 start=text.index(name+'(');start=text.rfind('\n',0,start)+1
 opening=text.index('{',start);depth=0
 for end in range(opening,len(text)):
  depth+=(text[end]=='{')-(text[end]=='}')
  if depth==0:return text[start:end+1]
class Authority(unittest.TestCase):
 def setUp(self):
  package=types.ModuleType('cast_fixture');package.__path__=[]
  maps=types.ModuleType('cast_fixture.build_catalog');maps.catalog_maps=lambda:{(1,2):dict(name='RusturfTunnel')}
  sys.modules['cast_fixture']=package;sys.modules['cast_fixture.build_catalog']=maps
  spec=importlib.util.spec_from_file_location('cast_fixture.trainer_experiences',ROOT/'world/trainer_experiences.py')
  self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m);sys.modules[spec.name]=self.m
  self.key='t123456789abcdef0';self.m.catalog=lambda:{self.key:dict(name='GRUNT',symbol='TRAINER_GRUNT_RUSTURF_TUNNEL')}
  events=[]
  class Memory:
   def append(self,kind,data):events.append(dict(event=kind,**data));return len(events)
  self.events=events;self.s=types.SimpleNamespace(db=sqlite3.connect(':memory:'),memory=Memory(),revision=0)
  self.addCleanup(self.s.db.close)
  self.conn=dict(id='private-player',core_active_run='a'*32,state=[1,2,0,0,0,0,1],state_time=time.monotonic())
 def share(self,**kw):return self.m.handle(self.s,self.conn,'a'*32,self.key,'1:1:2:1',**kw)
 def test_opt_in_one_result_idempotence_and_private_participants(self):
  self.assertEqual(self.m.participation(self.s,self.conn,'a'*32,'get','private')['battle_mode'],'OFF')
  self.assertEqual(self.events,[])
  with self.assertRaises(ValueError):self.share(cooperative=True,automatic=True)
  one=self.share(cooperative=True);self.assertEqual(self.share(cooperative=True),one);self.assertEqual(len(self.events),1)
  event=self.events[0];self.assertTrue(self.m.relevant(event,['native:RusturfTunnel']))
  self.assertEqual(event['source'],'explicitly_shared_native_coop_participation')
  self.assertIn('not a unique battle count',event['limits'])
  wire=json.dumps(event);self.assertNotIn('private-player',wire);self.assertNotIn('a'*32,wire)
  self.assertNotIn('participants',event);self.assertNotIn('party',event)
  with self.assertRaises(ValueError):self.share() # same serial cannot be relabelled as a single battle
  self.assertEqual(self.s.db.execute("SELECT name FROM sqlite_master WHERE name='core_story_progress'").fetchall(),[])
 def test_stale_and_cross_save_rejected(self):
  self.conn['core_active_run']='b'*32
  with self.assertRaises(ValueError):self.share(cooperative=True)
  self.conn['core_active_run']='a'*32;self.conn['state_time']-=4
  with self.assertRaises(ValueError):self.share(cooperative=True)
  self.assertEqual(self.events,[])
 def test_exact_core_dispatch_requires_negotiated_current_connection(self):
  tree=ast.parse((ROOT/'world/core_story.py').read_text())
  method=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='handle')
  namespace={'__package__':'cast_fixture','re':__import__('re')}
  exec(compile(ast.Module(body=[method],type_ignores=[]),'<exact CoreStory.handle>','exec'),namespace)
  self.s.peers={self.conn['id']:self.conn};self.conn['core_story_capable']=True
  obj=types.SimpleNamespace(s=self.s)
  result=namespace['handle'](obj,self.conn,['CORE','a'*32,'CBATTLE',self.key,'1:1:2:1'])
  self.assertEqual(result['evidence'],1)
  self.conn['core_story_capable']=False
  with self.assertRaises(ValueError):namespace['handle'](obj,self.conn,['CORE','a'*32,'CBATTLE',self.key,'1:1:2:2'])
  self.assertEqual(len(self.events),1)
 def test_single_battle_unchanged_and_invalid_provenance_rejected(self):
  self.share();event=self.events[0];self.assertEqual(event['summary'],'A trainer defeated GRUNT in RusturfTunnel.')
  self.assertTrue(self.m.relevant(event,['native:RusturfTunnel']))
  event['source']='explicitly_shared_native_coop_participation'
  self.assertFalse(self.m.relevant(event,['native:RusturfTunnel']))
if __name__=='__main__':unittest.main()
