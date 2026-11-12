import ast,sys,importlib.util,pathlib,subprocess,tempfile,unittest,time,types
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_field_support.c').exists() else ROOT/'engines/expansion-native'
spec=importlib.util.spec_from_file_location('support',ROOT/'world/field_support.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Support(unittest.TestCase):
 def setUp(self):
  self.a={'id':'a','sock':'sa','presence':{'state':[0,16,1,1,0,0,1],'state_time':time.monotonic()}}
  self.b={'id':'b','sock':'sb','presence':{'state':[0,16,2,1,0,0,1],'state_time':time.monotonic()}}
  tag=types.SimpleNamespace(active=True,coop_wire=None,participants=('a','b'))
  self.s=types.SimpleNamespace(link_channels={'a':self.a,'b':self.b},connections={'sa','sb'},peers={'a':self.a['presence'],'b':self.b['presence']},link_protocol=types.SimpleNamespace(_tags={'t':tag},_tag_actor={'a':'t','b':'t'},sessions=types.SimpleNamespace(_locks={}),_encounters={}))
 def wire(self,c,p):return m.wire(self.s,c,p.encode())
 def offer(self):
  out=self.wire(self.a,'FS OFFER 1 b');self.assertEqual(len(out),2);return self.a['field_support']['token']
 def test_delivery_and_no_replay(self):
  t=self.offer();self.assertIn('READY',self.wire(self.b,f'FS ACCEPT {t}')[0][1]);self.assertIn('APPLY',self.wire(self.a,f'FS COMMIT {t}')[0][1]);self.assertIn('FAIL',self.wire(self.a,f'FS COMMIT {t}')[0][1]);self.assertIn(' 1\n',self.wire(self.b,f'FS ACK {t} 1')[0][1]);self.assertNotIn('field_support',self.a);self.assertIn('FAIL',self.wire(self.b,f'FS ACK {t} 1')[0][1])
 def test_roles_and_revocation(self):
  t=self.offer();self.assertIn('FAIL',self.wire(self.a,f'FS ACCEPT {t}')[0][1]);self.assertIn('FAIL',self.wire(self.b,f'FS COMMIT {t}')[0][1]);self.s.link_protocol._tags['t'].active=False;self.assertTrue(self.wire(self.b,f'FS ACCEPT {t}')[0][1].endswith(' 0\n'))
 def test_disconnect_after_commit_is_uncertain(self):
  t=self.offer();self.wire(self.b,f'FS ACCEPT {t}');self.wire(self.a,f'FS COMMIT {t}');self.s.connections.remove('sb');self.assertTrue(self.wire(self.a,f'FS CANCEL {t}')[0][1].endswith(' 2\n'))
 def test_expiry_and_stale_session(self):
  t=self.offer();self.a['field_support']['expires']=0;self.assertTrue(self.wire(self.b,f'FS ACCEPT {t}')[0][1].endswith(' 0\n'));self.a['field_support_next']=0;self.s.link_channels['a']=dict(self.a);self.assertIn('FAIL',self.wire(self.a,'FS OFFER 2 b')[-1][1])
 def test_distance_and_encounter(self):
  self.b['presence']['state'][2]=10;self.assertIn('FAIL',self.wire(self.a,'FS OFFER 1 b')[-1][1]);self.b['presence']['state'][2]=2;self.s.link_protocol._encounters['b']=object();self.assertIn('FAIL',self.wire(self.a,'FS OFFER 2 b')[-1][1])
 def test_actual_authenticated_dispatch(self):
  tree=ast.parse((ROOT/'world/server.py').read_text());method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_link_line')
  module=ast.Module(body=[method],type_ignores=[]);ns={'__package__':'support_fixture'}
  package=types.ModuleType('support_fixture');package.__path__=[str(ROOT/'world')];self.s.combined_regions=False;sys.modules['support_fixture']=package;sys.modules['support_fixture.field_support']=m
  exec(compile(module,'actual_server_dispatch','exec'),ns)
  out=[];self.s._queue=lambda c,line:out.append((c,line));self.s._error=lambda c,error:out.append((c,error))
  ns['_link_line'](self.s,self.a,b'FS OFFER 1 b');self.assertEqual(len(out),2)
  out.clear();old=dict(self.a);ns['_link_line'](self.s,old,b'FS OFFER 2 b');self.assertEqual(out,[])
 def test_native_actual_controller(self):
  with tempfile.TemporaryDirectory() as name:
   d=pathlib.Path(name);(d/'platform').mkdir();(d/'constants').mkdir()
   for h in ['global.h','main.h','pokemon.h','overworld.h','script.h','palette.h','field_player_avatar.h','sound.h','platform/world_bridge.h','platform/link_transport.h','platform/native_link.h','platform/generated_map.h','platform/world_field_ui.h','platform/world_field_support.h','constants/moves.h','constants/maps.h','constants/map_types.h']:(d/h).write_text('')
   (d/'test.c').write_text((ROOT/'test/native_support.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_field_support.c')))
   for enabled in (0,1):
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_FIELD_SUPPORT={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_stock_menu_and_default(self):
  p=(NATIVE/'src/party_menu.c').read_text();self.assertIn('if ((FieldSkills_Enabled() || WorldFieldUI_Enabled())',p)
  self.assertIn('EW_FIELD_SUPPORT ?= 0',(ROOT/'engines/expansion.mk').read_text())
  compile((ROOT/'scripts/build_expansion.py').read_text(),'builder','exec');compile((ROOT/'world/server.py').read_text(),'server','exec')
if __name__=='__main__':unittest.main()
