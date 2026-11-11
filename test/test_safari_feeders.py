import ast,os,hashlib,json,pathlib,re,sqlite3,sys,tempfile,time,types,unittest,subprocess,struct
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_safari_feeders.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('feeder_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
from feeder_fixture import safari_feeders as f
class Feeders(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.db=sqlite3.connect(pathlib.Path(self.temp.name)/'world.db');self.addCleanup(self.db.close)
  self.db.execute('CREATE TABLE history(seq INTEGER PRIMARY KEY,event TEXT,data TEXT)')
  self.peer={'id':'alice','state':[26,3,24,31,2,0,1],'state_time':time.monotonic()};self.conn={'id':'alice','presence':self.peer,'sock':1};self.s=types.SimpleNamespace(db=self.db,peers={'alice':self.peer},link_channels={'alice':self.conn},connections={1:True},link_protocol=types.SimpleNamespace(sessions=types.SimpleNamespace(_locks={}),_encounters={}),revision=0)
  def append(event,data):return self.db.execute('INSERT INTO history(event,data) VALUES(?,?)',(event,json.dumps(data))).lastrowid
  self.s.memory=types.SimpleNamespace(append=append)
 def send(self,s):return f.handle(self.s,self.conn,s.encode())
 def test_real_deposit_persists_and_later_visitors_get_native_flavors(self):
  self.assertEqual(self.send('SF PUT 1 7 0114000000000a'),'SF STORED 1\n');other=sqlite3.connect(pathlib.Path(self.temp.name)/'world.db');self.assertEqual(other.execute('SELECT block FROM safari_feeder_scents').fetchone()[0],'0114000000000a');other.close()
  event,data=self.db.execute('SELECT event,data FROM history').fetchone();self.assertEqual(event,'safari_feeder_deposit_shared');self.assertNotIn('player',json.loads(data));self.assertEqual(json.loads(data)['flavors'],[20,0,0,0,0])
  self.assertTrue(self.send('SF GET 2 7').startswith('SF SCENT 2 7 0114000000000a '));self.assertEqual(len(f.catalog(self.s)['active']),1)
 def test_replay_cannot_extend_or_duplicate_history(self):
  self.send('SF PUT 1 7 0114000000000a');old=self.db.execute('SELECT expires FROM safari_feeder_scents').fetchone()[0];self.assertEqual(self.send('SF PUT 1 7 0114000000000a'),'SF FAIL 1\n');self.assertEqual(self.db.execute('SELECT expires FROM safari_feeder_scents').fetchone()[0],old);self.assertEqual(self.db.execute('SELECT count(*) FROM history').fetchone()[0],1)
 def test_current_channel_facing_distance_and_session(self):
  self.peer['state'][4]=1;self.assertEqual(self.send('SF PUT 1 7 0114000000000a'),'SF FAIL 1\n');self.peer['state'][4]=2;self.s.link_protocol.sessions._locks['alice']=1;self.assertEqual(self.send('SF PUT 2 7 0114000000000a'),'SF FAIL 2\n');self.s.link_protocol.sessions._locks.clear();self.s.link_channels['alice']=dict(self.conn);self.assertEqual(self.send('SF PUT 3 7 0114000000000a'),'SF FAIL 3\n')
 def test_expiry_and_replacement_are_real_not_new_population_counts(self):
  self.send('SF PUT 1 7 0114000000000a');self.send('SF PUT 2 7 0200140000000a');self.assertIn('0200140000000a',self.send('SF GET 3 7'));self.assertEqual(self.db.execute('SELECT count(*) FROM safari_feeder_scents').fetchone()[0],1)
  self.db.execute('UPDATE safari_feeder_scents SET expires=0');self.assertEqual(self.send('SF GET 4 7'),'SF NONE 4\n');self.assertEqual(f.catalog(self.s)['active'],[])
 def test_bad_packets_and_non_feeder_maps(self):
  for i,p in enumerate(['00'+'00'*6,'0f'+'00'*6,'aa','01'+'ff'*7]):self.assertTrue(self.send(f'SF PUT {i+1} 7 {p}').startswith('SF FAIL'))
  self.peer['state'][0]=0;self.assertEqual(self.send('SF PUT 9 7 0114000000000a'),'SF FAIL 9\n')
 def test_actual_transport_dispatch(self):
  sys.modules['feeder_fixture.combined_regions']=types.SimpleNamespace(pending=lambda *a:False)
  tree=ast.parse((ROOT/'world/server.py').read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_link_line');ns={'__package__':'feeder_fixture'};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_dispatch','exec'),ns);out=[];self.s._queue=lambda c,s:out.append(s)
  ns['_link_line'](self.s,self.conn,b'SF PUT 1 7 0114000000000a');self.assertEqual(out,['SF STORED 1\n'])
 def test_native_lifecycle_on_off(self):
  with tempfile.TemporaryDirectory() as temp:
   d=pathlib.Path(temp);(d/'platform').mkdir()
   for p in ['global.h','main.h','overworld.h','script.h','palette.h','safari_zone.h','fieldmap.h','metatile_behavior.h','platform/world_bridge.h','platform/native_link.h']:(d/p).write_text('')
   for p in ['world_safari_feeders.h','safari_feeder_sites.h']:(d/'platform'/p).write_text((NATIVE/'include/platform'/p).read_text())
   (d/'test.c').write_text((ROOT/'test/native_scent.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_safari_feeders.c')))
   for enabled in [0,1]:
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_SHARED_SAFARI_FEEDERS={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_hooks_no_new_debit_and_existing_history_executor(self):
  native=(NATIVE/'src/pokeblock.c').read_text();start=native.index('static void PokeblockAction_UseOnPokeblockFeeder(u8 taskId)\n{');end=native.index('\n}',start);body=native[start:end];self.assertLess(body.index('TryClearPokeblock'),body.index('WorldSafariFeeders_Committed'))
  self.assertIn("'safari_feeder_deposit_shared'",(ROOT/'world/history_world_rules.py').read_text());self.assertIn('safari_feeders=safari_feeder_catalog(server)',(ROOT/'world/actor_runtime.py').read_text())
 def test_verified_real_feeder_catalog(self):
  root=pathlib.Path(os.environ.get('EW_NATIVE_SOURCE_ROOT',NATIVE));catalog=json.loads((ROOT/'world/safari_feeders.json').read_text())
  if not (root/'data/layouts/layouts.json').exists():self.skipTest('Initialize exact native submodule, or provide verified source root')
  for path,expected in catalog['sources'].items():
   data=(root/path).read_bytes();self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),expected,path)
  raw=(root/'include/constants/metatile_behaviors.h').read_text();clean=re.sub(r'/\*.*?\*/|//[^\n]*','',raw,flags=re.S);behavior=re.findall(r'\bMB_[A-Z0-9_]+\b',clean).index('MB_POKEBLOCK_FEEDER')
  a=(root/'data/tilesets/primary/general/metatile_attributes.bin').read_bytes()+(root/'data/tilesets/secondary/lilycove/metatile_attributes.bin').read_bytes();attrs=struct.unpack('<'+'H'*(len(a)//2),a)
  for e in catalog['entries']:
   cells=struct.unpack('<1600H',(root/f"data/layouts/{e['map']}/map.bin").read_bytes());self.assertEqual(attrs[cells[e['y']*40+e['x']]&1023]&255,behavior)
  self.assertEqual(len(catalog['entries']),11)
 def test_actual_native_nature_consequence_and_private_precedence(self):
  block=(NATIVE/'src/pokeblock.c').read_text();wild=(NATIVE/'src/wild_encounter.c').read_text();safari=(NATIVE/'src/safari_zone.c').read_text()
  def func(source,signature):
   start=source.index(signature+'\n{');end=source.index('\n}',start)+2;return source[start:end]
  table=block[block.index('const s8 gPokeblockFlavorCompatibilityTable'):block.index('\n};',block.index('const s8 gPokeblockFlavorCompatibilityTable'))+3]
  body=table+'\n'+func(block,'s16 GetPokeblockData(const struct Pokeblock *pokeblock, u8 field)')+'\n'+func(block,'s16 PokeblockGetGain(u8 nature, const struct Pokeblock *pokeblock)')+'\n'+func(safari,'struct Pokeblock *SafariZoneGetActivePokeblock(void)')+'\n'+func(wild,'static u8 PickWildMonNature(enum Species species)')
  self.run_c((ROOT/'test/native_nature.c').read_text().replace('ACTUAL_FUNCTIONS',body))
 def test_actual_native_debit_activation_callback(self):
  block=(NATIVE/'src/pokeblock.c').read_text();safari=(NATIVE/'src/safari_zone.c').read_text()
  def func(source,signature):
   start=source.index(signature+'\n{');end=source.index('\n}',start)+2;return source[start:end]
  body=func(safari,'void SafariZoneActivatePokeblockFeeder(u8 pkblId)')+'\n'+func(block,'static void PokeblockAction_UseOnPokeblockFeeder(u8 taskId)')
  self.run_c((ROOT/'test/native_deposit.c').read_text().replace('ACTUAL_FUNCTIONS',body))
 def run_c(self,code):
  with tempfile.TemporaryDirectory() as temp:
   d=pathlib.Path(temp);(d/'test.c').write_text(code);subprocess.run(['cc','-std=c99','-DPORTABLE','-fsanitize=undefined',str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_deposit_history_drives_existing_rule_executor_without_fabrication(self):
  from feeder_fixture import history_world_rules as rules
  self.s.job=self.s.deployment=None;calls=[]
  cap=types.SimpleNamespace(kinds=('canonical','world'),poll=None,arguments={'value':'int'},execute=lambda server,actor,row,args:(calls.append((actor,args)) or {'fixture_effect':True}))
  sys.modules['feeder_fixture.actor_runtime']=types.SimpleNamespace(CAPABILITIES={'world.configure_outbreak':cap},actor_records=lambda server:{'observer':{'canonical':True,'status':'active'}})
  def history(after=0,limit=64):
   rows=self.db.execute('SELECT seq,event,data FROM history WHERE seq>? ORDER BY seq LIMIT ?',(after,limit)).fetchall();head=self.db.execute('SELECT coalesce(max(seq),0) FROM history').fetchone()[0]
   return {'events':[dict(seq=q,event=e,**json.loads(d)) for q,e,d in rows],'cursor':rows[-1][0] if rows else after,'through':head}
  self.s.memory.history=history
  rule=dict(event='safari_feeder_deposit_shared',where={'site':7},tool='world.configure_outbreak',args={'value':1},cooldown=60,per_hour=1)
  with self.db:rules.publish(self.s,'observer',None,{'id':'response','rule':json.dumps(rule)})
  self.send('SF PUT 1 7 0114000000000a');result=rules.tick(self.s,now=time.time());self.assertEqual(result['status'],'succeeded');self.assertEqual(calls,[('observer',{'value':1})]);self.assertEqual(self.db.execute('SELECT count(*) FROM history_world_rule_runs').fetchone()[0],1)
  rules.tick(self.s,now=time.time()+70);self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
