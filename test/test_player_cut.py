import ast,hashlib,json,pathlib,re,sqlite3,sys,tempfile,threading,time,types,unittest,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
pkg=types.ModuleType('cutfixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
from cutfixture import player_cut as m,shared_terrain as terrain
TREE=ast.parse((ROOT/'world/server.py').read_text())
NAMES=('_link_line','set_shared_terrain','_active_terrain')
NS=dict(__package__='cutfixture',re=re,hashlib=hashlib,sqlite3=sqlite3,MAX_QUEUE=100000,terrain_delta=lambda c,a,b:[dict(x=x,y=y,terrain=k) for (x,y),k in terrain.validate(c,b).items() if terrain.validate(c,a).get((x,y))!=k])
for name in NAMES:
 fn=next(n for n in ast.walk(TREE) if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-server','exec'),NS)
class Cut(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
  self.db.executescript('CREATE TABLE generated_cave(singleton INTEGER,template BLOB);CREATE TABLE generated_area_terrain(identity TEXT PRIMARY KEY,revision INTEGER,payload BLOB);CREATE TABLE events(seq INTEGER PRIMARY KEY,kind TEXT,body TEXT);')
  data=b'synthetic-exact-template';identity=hashlib.sha256(data).hexdigest();self.identity=identity
  self.db.execute('INSERT INTO generated_cave VALUES(1,?)',(data,));self.db.commit()
  rows=[b'#'*63]+[b'#'+b'.'*61+b'#' for _ in range(61)]+[b'#'*63]
  cave=types.SimpleNamespace(identity=identity,version=9,_rows=rows,cast=bytes(184),walkable=lambda x,y:0<x<62 and 0<y<62)
  def event(k,v):return self.db.execute('INSERT INTO events(kind,body) VALUES(?,?)',(k,json.dumps(v))).lastrowid
  self.s=types.SimpleNamespace(combined_regions=False,db=self.db,lock=threading.RLock(),archive_generated_areas=True,shared_cave=cave,wilds_map=(0,1),cave_map=(0,2),peers={},memory=types.SimpleNamespace(append=event,place=lambda i:'place:'+i),revision=0)
  for name in NAMES:setattr(self.s,name,types.MethodType(NS[name],self.s))
  self.s._active_walkable=lambda x,y:terrain.walkable(cave,self.s._active_terrain()[1],x,y)
  self.queued=[];self.s._queue=lambda p,line:self.queued.append(line);self.s._drop=lambda p:p.update(closing=True)
  p=dict(state=[0,1,10,10,1,1,0],state_time=time.monotonic(),in_generated_cave=True,cave_ack=identity,cave_terrain=True,cave_capable=True,cave_large_terrain=True,cave_geometry=True,out=bytearray())
  self.c=dict(id='private',sock='socket',presence=p);self.s.peers={'private':p};self.s.connections={'socket':self.c};self.s.link_channels={'private':self.c}
  self.errors=[];self.s._error=lambda c,e:self.errors.append(e)
 def request(self,cells='0b0a',snapshot=None,nonce=1):
  snapshot=snapshot or hashlib.sha256(self.s._active_terrain()[1]).hexdigest()
  return f'PG CUT {nonce} {self.identity} {snapshot} 0a0a {cells}'.encode()
 def test_actual_transaction_broadcast_restart_and_no_credit(self):
  self.s._link_line(self.c,self.request());self.assertTrue(self.queued[-1].startswith('PG COMMITTED 1 1'))
  self.assertTrue(any(str(x).startswith('CAVE TERRAINH ') for x in self.queued))
  self.assertEqual(terrain.validate(self.s.shared_cave,self.s._active_terrain()[1]),{(11,10):0})
  body=self.db.execute('SELECT body FROM events').fetchone()[0];self.assertNotIn('private',body)
  other=sqlite3.connect(':memory:');self.addCleanup(other.close);self.db.backup(other);self.s.db=other
  self.assertEqual(self.s._active_terrain()[0],1)
 def test_duplicate_stale_context_and_no_fabricated_replay(self):
  request=self.request();self.assertIn('COMMITTED',m.wire(self.s,self.c,request))
  self.assertIn('REJECTED',m.wire(self.s,self.c,request));self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
  self.assertIn('REJECTED',m.wire(self.s,self.c,self.request())) # already cut
 def test_exact_presence_and_authenticated_dispatch(self):
  for key,value in [('state_time',0),('in_generated_cave',False),('cave_ack','x'),('region_cave',True),('cave_transfer_pending',True)]:
   p=self.c['presence'];old=p.get(key);p[key]=value;self.assertIn('REJECTED',m.wire(self.s,self.c,self.request()));p[key]=old
  self.s.peers['private']={};self.s._link_line(self.c,self.request());self.assertEqual(self.errors,['PRESENCE']);self.assertEqual(self.queued,[])
 def test_bounds_and_native_surface(self):
  for cells in ['0a0a','0b0a0b0a','ffff','0101','0d0a','zzzz','']:
   self.assertIn('REJECTED',m.wire(self.s,self.c,self.request(cells)))
  self.assertEqual(self.s._active_terrain()[0],0)
 def test_transaction_failure_no_delivery_or_partial_change(self):
  self.db.execute("CREATE TRIGGER fail BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'synthetic'); END;")
  self.assertIn('REJECTED',m.wire(self.s,self.c,self.request()));self.assertEqual(self.s._active_terrain(),(0,b'\0'));self.assertEqual(self.queued,[])
 def test_incompatible_inside_peer_and_busy_queue(self):
  self.s.peers['legacy']=dict(cave_capable=True,in_generated_cave=True)
  self.assertIn('REJECTED',m.wire(self.s,self.c,self.request()));self.s.peers.pop('legacy')
  self.c['presence']['out']=bytearray(100000)
  self.assertIn('REJECTED',m.wire(self.s,self.c,self.request()));self.assertEqual(self.s._active_terrain()[0],0)
 def test_actual_native_module_on_off(self):
  source=(ROOT/'test/native_player_cut.c').read_text()
  native=ROOT/'src/world/player_cut.inc.c'
  if not native.exists():native=ROOT/'engines/expansion-native/src/world/player_cut.inc.c'
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);(d/'constants').mkdir()
   for f in ['pokemon.h','main.h','overworld.h','fieldmap.h','field_player_avatar.h','event_object_lock.h','script.h','task.h','constants/moves.h','constants/metatile_labels.h']:(d/f).write_text('')
   (d/'test.c').write_text(source.replace('NATIVE_INCLUDE',str(native)))
   for flag in [0,1]:
    subprocess.run(['cc','-std=c99','-fsanitize=undefined',f'-DEW_PERSISTENT_CUT={flag}','-I',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True)
 def test_exact_native_digest_and_authoritative_restoration(self):
  native=ROOT if (ROOT/'src/world/generated_map.c').exists() else ROOT/'engines/expansion-native'
  source=(native/'src/world/generated_map.c').read_text();helpers=source[source.rindex('bool8 GeneratedMap_CutSnapshot'):source.rindex('#endif')]
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);(d/'global.h').write_text('#include <stdint.h>\n#include <stddef.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint8_t bool8;\n#define TRUE 1\n#define FALSE 0\n')
   pre='#include "global.h"\n#include <string.h>\n#include <stdio.h>\n#include <assert.h>\n#include "platform/world_cave_wire.h"\n#define MAP_OFFSET 7\n#define GENERATED_MAP_READY 1\n#undef GENERATED_WILDS_EVENTS\n#define GENERATED_WILDS_EVENTS 1\n#undef GENERATED_WILDS_SHARED_TERRAIN\n#define GENERATED_WILDS_SHARED_TERRAIN 1\n#define EW_PERSISTENT_CUT 1\nstatic unsigned sLargeActive=1,sLargeShared=1,sLargeWilds=1,sEventActive=1,sSharedTerrainSize;\nstatic u8 sEventData[1466],sCastMetadata[184],sLargeTemplate[3969],sSharedTerrain[1539];\nstatic u16 sLargeTiles[3969],rendered;\nstatic bool8 GeneratedMap_IsInside(void){return TRUE;}\nstatic void MapGridSetMetatileEntryAt(unsigned x,unsigned y,u16 tile){assert(x==18&&y==17);rendered=tile;}\nstatic void CurrentMapDrawMetatileAt(unsigned x,unsigned y){}\n'
   end='\nint main(void){char id[65],hash[65];memset(sLargeTemplate,46,3969);assert(GeneratedMap_CutSnapshot(id,hash));puts(id);puts(hash);sLargeTiles[10*63+11]=0x3001;GeneratedMap_RestoreCutCell(id,11,10);assert(rendered==0x3001);sLargeTiles[10*63+11]=0x300d;GeneratedMap_RestoreCutCell(id,11,10);assert(rendered==0x300d);sLargeShared=0;assert(!GeneratedMap_CutSnapshot(id,hash));return 0;}\n'
   (d/'test.c').write_text(pre+helpers+end)
   subprocess.run(['cc','-std=c99','-fsanitize=undefined','-DPORTABLE','-I',str(d),'-I',str(native/'include'),str(d/'test.c'),str(native/'src/world/world_cave_wire.c'),'-o',str(d/'test')],check=True)
   actual=subprocess.check_output([str(d/'test')],text=True).splitlines()
   self.assertEqual(actual,[hashlib.sha256(b'EWGMAP09'+bytes(1466)+bytes(184)+b'.'*3969).hexdigest(),hashlib.sha256(b'\0').hexdigest()])
if __name__=='__main__':unittest.main()
