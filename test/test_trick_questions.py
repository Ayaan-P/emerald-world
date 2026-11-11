import ast,copy,hashlib,re,json,pathlib,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
pkg=types.ModuleType('trickfixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
bc=types.ModuleType('trickfixture.build_catalog');bc.catalog_maps=lambda:{(29,7):dict(name='Route110_TrickHousePuzzle5')};sys.modules[bc.__name__]=bc
from trickfixture import trick_questions as m
class Trick(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close);self.events=[]
  def append(k,v):self.events.append((k,v));return len(self.events)
  self.s=types.SimpleNamespace(db=self.db,memory=types.SimpleNamespace(append=append),revision=0)
  self.c=dict(id='private',presence=dict(state=[29,7,0,0],state_time=time.monotonic()))
  self.args=dict(expected_revision=0,title='A new quiz',active=True,questions=[dict(question='Which answer?',choices=['First','Second','Third'],answer=1) for _ in range(5)])
 def put(self):return m.configure(self.s,'master',{},self.args)
 def test_pack_wire_and_no_player_reports(self):
  self.put();lines=m.wire(self.s,self.c,b'TQ GET 4').splitlines();self.assertEqual(len(lines),7)
  self.assertEqual(lines[0].split()[:4],['TQ','BEGIN','4','1']);self.assertTrue(all(len(x)<512 for x in lines));self.assertEqual(lines[-1],'TQ END 4 1')
  self.assertEqual(m.wire(self.s,self.c,b'TQ DONE 4'),'TQ NONE 0\n');self.assertEqual(len(self.events),1);self.assertNotIn('private',json.dumps(self.events))
 def test_bounds_ownership_revision_withdrawal(self):
  for change in [dict(title='x\ncontrol'),dict(expected_revision=True),dict(questions=[]),dict(active=1)]:
   with self.assertRaises(ValueError):m.configure(self.s,'master',{},dict(self.args,**change))
  self.put();self.args['expected_revision']=1
  with self.assertRaises(ValueError):m.configure(self.s,'other',{},self.args)
  self.args['active']=False;self.put();self.assertEqual(m.wire(self.s,self.c,b'TQ GET 1'),'TQ NONE 1\n')
 def test_stale_wrong_map_rate_and_restart(self):
  self.put();self.db.commit();other=sqlite3.connect(':memory:');self.addCleanup(other.close);self.db.backup(other);self.s.db=other
  self.assertEqual(m.catalog(self.s)['pack']['revision'],1)
  self.c['presence']['state_time']=0;self.assertEqual(m.wire(self.s,self.c,b'TQ GET 1'),'TQ NONE 1\n')
  self.c['presence']['state_time']=time.monotonic();self.c['presence']['state'][0]=0;self.assertEqual(m.wire(self.s,self.c,b'TQ GET 2'),'TQ NONE 2\n')
  self.c['presence']['state'][0]=29;self.assertIn('TQ BEGIN',m.wire(self.s,self.c,b'TQ GET 3'));self.assertEqual(m.wire(self.s,self.c,b'TQ GET 4'),'TQ NONE 4\n')
 def test_actual_authenticated_dispatch(self):
  tree=ast.parse((ROOT/'world/server.py').read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_link_line');ns={'__package__':'trickfixture'};exec(compile(ast.Module(body=[fn],type_ignores=[]),'dispatch','exec'),ns)
  self.put();self.c['sock']='s';queued=[];errors=[];self.s.link_channels={'private':self.c};self.s.connections={'s':self.c};self.s.peers={'private':self.c['presence']};self.s._queue=lambda c,l:queued.append(l);self.s._error=lambda c,l:errors.append(l)
  ns['_link_line'](self.s,self.c,b'TQ GET 1');self.assertIn('TQ BEGIN',queued[-1]);self.s.peers['private']={};ns['_link_line'](self.s,self.c,b'TQ GET 2');self.assertEqual(errors,['PRESENCE']);self.assertEqual(len(queued),1)
 def test_native_source_on_off(self):
  native=ROOT/'src/world/world_trick_quiz.c'
  if not native.exists():native=ROOT/'engines/expansion-native/src/world/world_trick_quiz.c'
  with tempfile.TemporaryDirectory() as path:
   d=pathlib.Path(path);(d/'constants').mkdir();(d/'platform').mkdir()
   for name in ['global.h','main.h','event_data.h','script_menu.h','string_util.h','malloc.h','constants/maps.h','constants/vars.h','constants/characters.h']:(d/name).write_text('')
   (d/'platform/world_trick_quiz.h').write_text('')
   (d/'test.c').write_text((ROOT/'test/native_trick_quiz.c').read_text().replace('ACTUAL_SOURCE',str(native)))
   for mode in (0,1):
    subprocess.run(['cc','-std=c99','-fsanitize=undefined',f'-DEW_TRICK_QUIZ={mode}','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
   (d/'stress.c').write_text((ROOT/'test/native_trick_stress.c').read_text().replace('COMPONENT_SOURCE',str(d/'test.c')))
   subprocess.run(['cc','-std=c99','-fsanitize=undefined','-DEW_TRICK_QUIZ=1','-iquote',str(d),str(d/'stress.c'),'-o',str(d/'stress')],check=True);subprocess.run([str(d/'stress')],check=True)
 def test_original_script_preserved(self):
  native=ROOT if (ROOT/'src/world/world_trick_quiz.c').exists() else ROOT/'engines/expansion-native'
  s=(native/'data/maps/Route110_TrickHousePuzzle5/scripts.inc').read_text()
  s=s.split('\n@ Optional authored gates.')[0]
  s=s.replace('\tcallnative WorldTrickQuiz_Enter\n','')
  s=re.sub(r'\tcallnative WorldTrickQuiz_Prepare\n.*?\trandom 3', '\\trandom 3',s,flags=re.S)
  raw=s.encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'c59dad2e571961f4b2a9fe917ae97b77f2fbd8ea')
 def test_scripts_and_build_connections(self):
  native=ROOT if (ROOT/'src/world/world_trick_quiz.c').exists() else ROOT/'engines/expansion-native'
  s=(native/'data/maps/Route110_TrickHousePuzzle5/scripts.inc').read_text()
  self.assertEqual(s.count('callnative WorldTrickQuiz_Prepare'),5);self.assertEqual(s.count('random 3'),5)
  self.assertIn('warp MAP_ROUTE110_TRICK_HOUSE_PUZZLE5, 0, 21',s);self.assertIn('callnative WorldTrickQuiz_Enter',s)
  self.assertIn('WorldTrickQuiz_Line(n,t)',(native/'src/world/link_transport.c').read_text());self.assertIn('WorldTrickQuiz_Update();',(native/'src/world/link_transport.c').read_text())
  self.assertIn('EW_TRICK_QUIZ ?= 0',(ROOT/'engines/expansion.mk').read_text());self.assertIn('if args.experimental_trick_quiz and not args.development:',(ROOT/'scripts/build_expansion.py').read_text())
  self.assertIn('world.trick_questions',(ROOT/'world/actor_runtime.py').read_text())
if __name__=='__main__':unittest.main()
