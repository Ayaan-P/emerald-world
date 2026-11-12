import ast,json,pathlib,sqlite3,sys,tempfile,time,types,unittest,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_dewford_trends.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('trend_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
from trend_fixture import dewford_trends as f
class Trends(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.db=sqlite3.connect(pathlib.Path(self.temp.name)/'world.db');self.addCleanup(self.db.close);self.db.execute('CREATE TABLE history(seq INTEGER PRIMARY KEY,event TEXT,data TEXT)')
  self.peer={'id':'alice','state':[0,11,1,7,2,0,1],'state_time':time.monotonic()};self.conn={'id':'alice','presence':self.peer,'sock':1};self.s=types.SimpleNamespace(db=self.db,peers={'alice':self.peer},link_channels={'alice':self.conn},connections={1:True},link_protocol=types.SimpleNamespace(sessions=types.SimpleNamespace(_locks={}),_encounters={}),revision=0)
  self.s.memory=types.SimpleNamespace(append=lambda event,data:self.db.execute('INSERT INTO history(event,data) VALUES(?,?)',(event,json.dumps(data))).lastrowid)
 def send(self,s):return f.handle(self.s,self.conn,s.encode())
 def test_persistent_actual_pattern_no_identity_or_fake_catch(self):
  self.assertEqual(self.send('DT PUT 1 512 513 42'),'DT STORED 1 1\n');other=sqlite3.connect(pathlib.Path(self.temp.name)/'world.db');self.assertEqual(other.execute('SELECT word0,word1,seed FROM dewford_public_trend').fetchone(),(512,513,42));other.close();self.peer['state']=[0,34,4,5,1,0,1];self.assertEqual(self.send('DT GET 2'),'DT TREND 2 512 513 42 1\n');data=json.loads(self.db.execute('SELECT data FROM history').fetchone()[0]);self.assertNotIn('player',data);self.assertEqual(f.catalog(self.s)['current']['seed'],42)
 def test_replay_duplicate_and_replacement(self):
  self.send('DT PUT 1 512 513 42');self.assertEqual(self.send('DT PUT 1 512 513 42'),'DT FAIL 1\n');self.assertEqual(self.send('DT PUT 2 512 513 42'),'DT STORED 2 1\n');self.assertEqual(self.db.execute('SELECT count(*) FROM history').fetchone()[0],1);self.send('DT PUT 3 514 515 99');self.assertEqual(f.catalog(self.s)['current']['seed'],99)
 def test_auth_current_presence_and_real_site(self):
  self.peer['state'][4]=1;self.assertEqual(self.send('DT PUT 1 512 513 42'),'DT FAIL 1\n');self.peer['state'][4]=2;self.s.link_protocol.sessions._locks['alice']=1;self.assertEqual(self.send('DT PUT 2 512 513 42'),'DT FAIL 2\n');self.s.link_protocol.sessions._locks.clear();self.s.link_channels['alice']=dict(self.conn);self.assertEqual(self.send('DT GET 3'),'DT FAIL 3\n')
 def test_malformed_and_stale(self):
  for i,fields in enumerate(['512 513 65536','65535 513 1','-1 513 1','0 0','512 513 3 4']):self.assertTrue(self.send(f'DT PUT {i+1} {fields}').startswith('DT FAIL'))
  self.peer['state_time']-=10;self.assertEqual(self.send('DT GET 9'),'DT FAIL 9\n')
 def test_actual_dispatch(self):
  sys.modules['trend_fixture.combined_regions']=types.SimpleNamespace(pending=lambda *a:False);node=next(n for n in ast.walk(ast.parse((ROOT/'world/server.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_link_line');ns={'__package__':'trend_fixture'};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_dispatch','exec'),ns);out=[];self.s._queue=lambda c,s:out.append(s);ns['_link_line'](self.s,self.conn,b'DT PUT 1 512 513 42');self.assertEqual(out,['DT STORED 1 1\n'])
 def test_native_core_enabled_disabled(self):
  with tempfile.TemporaryDirectory() as temp:
   d=pathlib.Path(temp);(d/'platform').mkdir()
   for p in ['global.h','main.h','overworld.h','script.h','palette.h','easy_chat.h','event_data.h','platform/world_bridge.h','platform/native_link.h']:(d/p).write_text('')
   (d/'platform/world_dewford_trends.h').write_text((NATIVE/'include/platform/world_dewford_trends.h').read_text());(d/'test.c').write_text((ROOT/'test/native_trend.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_dewford_trends.c')))
   for on in [0,1]:
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_SHARED_DEWFORD_TRENDS={on}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_transport_reset_and_scope(self):
  source=(NATIVE/'src/world/link_transport.c').read_text();self.assertIn('WorldDewfordTrends_Reset();',source[source.index('static void Disconnect'):]);self.assertIn('WorldDewfordTrends_Pump();',source);self.assertIn('WorldDewfordTrends_Line(n,t)',source)
  self.assertIn("'dewford_trend_shared'",(ROOT/'world/history_world_rules.py').read_text());self.assertIn('dewford_trend=dewford_catalog(server)',(ROOT/'world/actor_runtime.py').read_text());self.assertIn('export NATIVE_EXTRA_CPPFLAGS += -DEW_SHARED_DEWFORD_TRENDS=',(ROOT/'engines/expansion.mk').read_text())
 def run_c(self,code):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);(p/'test.c').write_text(code);subprocess.run(['cc','-std=c99','-DPORTABLE','-fsanitize=undefined',str(p/'test.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
 def test_actual_native_acceptance_branches(self):
  source=(NATIVE/'src/dewford_trend.c').read_text();start=source.index('bool8 TrySetTrendyPhrase(u16 *phrase)\n{');body=source[start:source.index('\n}',start)+2];self.run_c((ROOT/'test/native_acceptance.c').read_text().replace('ACTUAL_FUNCTION',body))
 def test_actual_feebas_algorithm_and_odds(self):
  source=(NATIVE/'src/wild_encounter.c').read_text();start=source.index('bool8 CheckFeebasAtCoords(s16 x, s16 y)\n{');body=source[start:source.index('\n}',start)+2];self.run_c((ROOT/'test/native_feebas.c').read_text().replace('ACTUAL_FUNCTION',body))
 def test_actual_history_scheduler_can_react_once(self):
  from trend_fixture import history_world_rules as rules
  self.s.job=self.s.deployment=None;calls=[]
  cap=types.SimpleNamespace(kinds=('canonical','world'),poll=None,arguments={'value':'int'},execute=lambda server,actor,row,args:(calls.append((actor,args)) or {'isolated_executor':True}))
  sys.modules['trend_fixture.actor_runtime']=types.SimpleNamespace(CAPABILITIES={'world.configure_outbreak':cap},actor_records=lambda server:{'observer':{'canonical':True,'status':'active'}})
  def history(after=0,limit=64):
   rows=self.db.execute('SELECT seq,event,data FROM history WHERE seq>? ORDER BY seq LIMIT ?',(after,limit)).fetchall();head=self.db.execute('SELECT coalesce(max(seq),0) FROM history').fetchone()[0]
   return {'events':[dict(seq=q,event=e,**json.loads(d)) for q,e,d in rows],'cursor':rows[-1][0] if rows else after,'through':head}
  self.s.memory.history=history
  rule=dict(event='dewford_trend_shared',where={'seed':42},tool='world.configure_outbreak',args={'value':1},cooldown=60,per_hour=1)
  with self.db:rules.publish(self.s,'observer',None,{'id':'response','rule':json.dumps(rule)})
  self.send('DT PUT 1 512 513 42');self.assertEqual(rules.tick(self.s,now=time.time())['status'],'succeeded');self.assertEqual(calls,[('observer',{'value':1})]);rules.tick(self.s,now=time.time()+70);self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
