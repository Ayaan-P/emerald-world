import ast,importlib.util,json,pathlib,sqlite3,sys,tempfile,time,types,unittest,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
pkg=types.ModuleType('strategyfixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
catalog=types.ModuleType('strategyfixture.build_catalog');catalog.catalog_maps=lambda:{(0,2):{'name':'Route102'}};sys.modules[catalog.__name__]=catalog
from strategyfixture import rematch_strategies as m
class Strategies(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close);self.events=[]
  def append(k,v):self.events.append((k,v));return len(self.events)
  self.s=types.SimpleNamespace(db=self.db,memory=types.SimpleNamespace(append=append),revision=0)
  self.c={'id':'private-trainer','presence':{'state':[0,2,4,6,1,1,0],'state_time':time.monotonic()}}
  self.args=dict(trainer='calvin',expected_revision=0,types=['grass','fire'],status_moves=1)
 def configure(self):return m.configure(self.s,'coach',{},self.args)
 def test_persistence_revision_and_ownership(self):
  self.configure();self.assertEqual(m.catalog(self.s)['strategies'][0]['types'],['grass','fire'])
  with self.assertRaises(ValueError):self.configure()
  self.args['expected_revision']=1
  with self.assertRaises(ValueError):m.configure(self.s,'other',{},self.args)
  self.configure();self.assertEqual(m.catalog(self.s)['strategies'][0]['revision'],2)
 def test_native_callback_report_is_once_and_identity_free(self):
  self.configure();p=m.wire(self.s,self.c,b'RS GET 1 calvin').split();self.assertEqual(p[:3],['RS','PLAN','1']);ticket=p[3]
  self.args.update(expected_revision=1,types=['water']);self.configure()
  self.assertEqual(m.wire(self.s,self.c,f'RS DONE {ticket} 1'.encode()),'RS RECORDED\n')
  self.assertEqual(m.wire(self.s,self.c,f'RS DONE {ticket} 1'.encode()),'RS NO\n')
  result=m.catalog(self.s)['results'];self.assertEqual(result,[dict(trainer='calvin',revision=1,native_outcome=1,count=1)])
  self.assertNotIn('private-trainer',json.dumps(self.events));self.assertNotIn('ticket',json.dumps(self.events))
 def test_wrong_connection_context_expiry_and_outcome(self):
  self.configure();p=m.wire(self.s,self.c,b'RS GET 7 calvin').split();ticket=p[3]
  self.assertEqual(m.wire(self.s,dict(presence=self.c['presence']),f'RS DONE {ticket} 1'.encode()),'RS NO\n')
  self.assertEqual(m.wire(self.s,self.c,f'RS DONE {ticket} 4'.encode()),'RS NO\n')
  self.c['rematch_strategy_pending']['expires']=0
  self.assertEqual(m.wire(self.s,self.c,f'RS DONE {ticket} 1'.encode()),'RS NO\n')
  self.c['presence']['state_time']=0;self.assertEqual(m.wire(self.s,self.c,b'RS GET 8 calvin'),'RS NONE 8\n')
  self.assertEqual(m.catalog(self.s)['results'],[])
 def test_withdrawal_preserves_already_offered_version(self):
  self.configure();ticket=m.wire(self.s,self.c,b'RS GET 1 calvin').split()[3]
  self.args.update(expected_revision=1,active=False);self.configure()
  self.assertEqual(m.wire(self.s,self.c,b'RS GET 2 calvin'),'RS NONE 2\n')
  self.assertEqual(m.wire(self.s,self.c,f'RS DONE {ticket} 2'.encode()),'RS RECORDED\n')
  self.assertEqual(m.catalog(self.s)['results'][0]['revision'],1)
 def test_bounds(self):
  for change in [dict(types=['grass','grass']),dict(types=['mystery']),dict(status_moves=True),dict(status_moves=3),dict(trainer='roxanne'),dict(expected_revision=True)]:
   with self.subTest(change=change),self.assertRaises(ValueError):m.configure(self.s,'coach',{},dict(self.args,**change))
 def test_restart_and_unknown_schema(self):
  self.configure();other=sqlite3.connect(':memory:');self.addCleanup(other.close);self.db.commit();self.db.backup(other)
  self.s.db=other
  self.assertEqual(m.catalog(self.s)['strategies'][0]['revision'],1)
  self.assertTrue(m.wire(self.s,self.c,b'RS GET 3 calvin').startswith('RS PLAN 3 '))
  other.execute('UPDATE rematch_strategies SET body=?',(json.dumps(dict(schema=2,types=['grass'],status_moves=1)),))
  self.assertEqual(m.wire(self.s,self.c,b'RS GET 4 calvin'),'RS NONE 4\n')
 def test_native_actual_include_on_off(self):
  native=ROOT/'src/world/rematch_strategy.inc.c'
  if not native.exists():native=ROOT/'engines/expansion-native/src/world/rematch_strategy.inc.c'
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);(d/'constants').mkdir();(d/'move.h').write_text('');(d/'field_message_box.h').write_text('');(d/'constants/characters.h').write_text('')
   source=(ROOT/'test/native_strategy.c').read_text().replace('../src/world/rematch_strategy.inc.c',str(native))
   (d/'test.c').write_text(source)
   for mode in [0,1]:
    subprocess.run(['cc','-std=c99','-fsanitize=undefined',f'-DEW_REMATCH_STRATEGIES={mode}','-I',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True)
 def test_actual_authenticated_server_dispatch(self):
  tree=ast.parse((ROOT/'world/server.py').read_text())
  fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_link_line')
  ns={'__package__':'strategyfixture'};exec(compile(ast.Module(body=[fn],type_ignores=[]),'dispatch','exec'),ns)
  self.configure();peer=self.c['presence'];self.c['sock']='socket'
  queued=[];errors=[]
  self.s.link_channels={'private-trainer':self.c};self.s.connections={'socket':self.c};self.s.peers={'private-trainer':peer}
  self.s._queue=lambda c,line:queued.append(line);self.s._error=lambda c,line:errors.append(line)
  ns['_link_line'](self.s,self.c,b'RS GET 1 calvin');self.assertTrue(queued[-1].startswith('RS PLAN 1 '))
  self.s.peers['private-trainer']={};ns['_link_line'](self.s,self.c,b'RS GET 2 calvin');self.assertEqual(errors,['PRESENCE']);self.assertEqual(len(queued),1)
  self.s.link_channels={};ns['_link_line'](self.s,self.c,b'RS GET 3 calvin');self.assertEqual(len(queued),1)
 def test_source_hooks(self):
  native=ROOT if (ROOT/'src/battle_setup.c').exists() else ROOT/'engines/expansion-native'
  b=(native/'src/battle_setup.c').read_text();self.assertIn('Strategy_Finish();',b);self.assertIn('if (!Strategy_Begin())Strategy_Original();',b);self.assertIn('Strategy_Apply();',b)
  self.assertIn('WorldRematchStrategy_Line(n,t)',(native/'src/world/link_transport.c').read_text())
  self.assertIn("self._queue(conn,strategy_wire(self,conn,raw))",(ROOT/'world/server.py').read_text())
  self.assertIn("EW_REMATCH_STRATEGIES ?= 0",(ROOT/'engines/expansion.mk').read_text())
  self.assertIn("if args.experimental_rematch_strategies and not args.development:",(ROOT/'scripts/build_expansion.py').read_text())
  self.assertIn("rematch_strategies=strategy_catalog(server)",(ROOT/'world/actor_runtime.py').read_text())
  self.assertIn("CAPABILITIES['world.rematch_strategy']",(ROOT/'world/actor_runtime.py').read_text())
if __name__=='__main__':unittest.main()
