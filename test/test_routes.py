import importlib.util,pathlib,sqlite3,sys,tempfile,time,types,unittest,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_route_trainers.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('routes_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules['routes_fixture']=pkg;sys.modules['routes_fixture.build_catalog']=types.SimpleNamespace(catalog_maps=lambda:{(0,16):{'name':'Route101'},(0,17):{'name':'Route102'}})
from routes_fixture import route_trainers as r
class Routes(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=pathlib.Path(self.tmp.name)/'world.db';self.db=sqlite3.connect(self.path);self.addCleanup(self.db.close);self.db.execute('create table history(id integer primary key,data text)')
  def append(k,v):return self.db.execute('insert into history(data) values(?)',(repr((k,v)),)).lastrowid
  self.c={'id':'a','state':[0,16,1,1,4,0,1],'state_time':time.monotonic()};self.ch={'id':'a','presence':self.c};self.s=types.SimpleNamespace(db=self.db,memory=types.SimpleNamespace(append=append),peers={'a':self.c},link_channels={'a':self.ch})
 def configure(self,actor='actor',**extra):
  args=dict(route='Route101',mode='resting',minutes=60,reason='A quieter afternoon');args.update(extra)
  with self.db:return r.configure(self.s,actor,{},args)
 def test_persistent_authoring_and_actual_wire(self):
  self.configure();reply=r.wire(self.s,self.ch,b'TD GET 1');self.assertTrue(reply.startswith('TD OFFER 1 0 16 1 1 15 '));other=sqlite3.connect(self.path);self.assertEqual(other.execute('select mode from route_trainer_dispositions').fetchone()[0],'resting');other.close()
 def test_ownership_and_withdrawal(self):
  self.configure()
  with self.assertRaises(ValueError):self.configure(actor='other')
  self.configure(minutes=0);self.assertEqual(r.wire(self.s,self.ch,b'TD GET 2'),'TD NONE 2\n')
 def test_invalid_and_stale_session(self):
  with self.assertRaises(ValueError):self.configure(route='PalletTown')
  self.configure();self.s.link_channels['a']=dict(self.ch);self.assertEqual(r.wire(self.s,self.ch,b'TD GET 1'),'TD FAIL\n')
 def test_native_actual_controller(self):
  with tempfile.TemporaryDirectory() as name:
   d=pathlib.Path(name);(d/'platform').mkdir();(d/'constants').mkdir()
   for p in ['global.h','main.h','overworld.h','script.h','palette.h','platform/world_route_trainers.h','platform/native_link.h','platform/generated_map.h','platform/world_bridge.h','constants/maps.h','constants/map_types.h']:(d/p).write_text('')
   (d/'test.c').write_text((ROOT/'test/native_route.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_route_trainers.c')))
   for enabled in (0,1):
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_ROUTE_TRAINERS={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_stock_path_and_non_normal_trainers_unchanged(self):
  s=(NATIVE/'src/trainer_see.c').read_text();self.assertEqual(s.count('WorldRouteTrainers_Range('),1);self.assertIn('return CheckPathBetweenTrainerAndPlayer(trainerObj, approachDistance, trainerObj->facingDirection);',s);self.assertIn('sDirectionalApproachDistanceFuncs[i](trainerObj, trainerObj->trainerRange_berryTreeId, x, y)',s)
  for text in ['WorldRouteTrainers_Pump();','WorldRouteTrainers_Reset();','WorldRouteTrainers_Line(n,t);','int LinkTransport_RouteTrainersSend'] :self.assertIn(text,(NATIVE/'src/world/link_transport.c').read_text())
if __name__=='__main__':unittest.main()
