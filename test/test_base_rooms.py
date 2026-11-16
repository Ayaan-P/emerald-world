import ast,re,hashlib,pathlib,sqlite3,sys,time,types,unittest,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_neighborhood.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('rooms_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
from rooms_fixture import base_rooms as r
from rooms_fixture import base_neighborhood as directory
class Presence(dict):
 def __init__(self,states,scopes):super().__init__(states);self.scopes=scopes
sys.modules['rooms_fixture.link_sessions']=types.SimpleNamespace(RegionPresence=Presence)
sys.modules['rooms_fixture.combined_regions']=types.SimpleNamespace(admitted=lambda *a:True,pending=lambda *a:False)
sys.modules['rooms_fixture.characters']=types.SimpleNamespace(records=lambda *a:{})
for mod in ['rental_pools','shared_outbreaks','actor_bulletins','actor_weather']:sys.modules['rooms_fixture.'+mod]=types.SimpleNamespace(line=lambda *a:None)
for mod in ['contest_guests','shared_fishing','battle_watch']:sys.modules['rooms_fixture.'+mod]=types.SimpleNamespace(lines=lambda *a:[])
def actual_method(name):
 tree=ast.parse((ROOT/'world/server.py').read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
 ns={'__package__':'rooms_fixture','time':time,'MAX_PEERS':8,'MAX_TRAVEL_PEERS':64,'TRAVEL_FRESH_SECONDS':3,'ID':re.compile('[a-z]+'),'bounded':lambda v,a,b:int(v),'MeetingUnavailable':ValueError}
 exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_server','exec'),ns);return ns[name]
class Rooms(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close);directory.setup(self.db)
  self.raw=bytearray(154);self.raw[0]=1;self.payload=self.raw.hex();self.publish('owner',self.payload)
  self.s=types.SimpleNamespace(db=self.db,peers={},link_channels={},cave_map=(99,1),wilds_map=(99,2),revision=0,tiles=[],objects=[],module_state={},rally=types.SimpleNamespace(snapshot=lambda c:[]),_schedule_presence=lambda t:None,_connection_cave=lambda c:None)
  for name in ['_region_scope','_link_presence','_snapshot']:setattr(self.s,name,types.MethodType(actual_method(name),self.s))
  for name in ['alice','bob']:
   peer={'id':name,'state':[25,0,2,2,1,0,1],'state_time':time.monotonic(),'closing':False,'travel':True}
   self.s.peers[name]=peer;self.s.link_channels[name]={'id':name,'presence':peer,'sock':name}
  self.s.connections={'alice':True,'bob':True}
 def publish(self,owner,payload):
  self.db.execute('INSERT OR REPLACE INTO base_neighborhood VALUES(?,?,?,?,?)',(owner,owner,'lineage',payload,hashlib.sha256(bytes.fromhex(payload)).hexdigest()[:16]));self.db.commit()
 def join(self,name='alice',seq=1,payload=None):return r.handle(self.s,self.s.link_channels[name],f'B ROOM {seq} {r.digest(payload or self.payload)}'.encode())
 def test_private_default_then_real_snapshot_and_admission(self):
  self.assertNotIn('PEER bob',self.s._snapshot(self.s.peers['alice']));self.assertEqual(dict(self.s._link_presence()),{})
  self.assertEqual(self.join(),'B ROOM 1 1\n');self.assertEqual(self.join('bob'),'B ROOM 1 1\n')
  self.assertIn('PEER bob',self.s._snapshot(self.s.peers['alice']));presence=self.s._link_presence();self.assertEqual(presence.scopes['alice'],presence.scopes['bob'])
  self.assertNotIn('FRIEND bob',self.s._snapshot(self.s.peers['alice']))
 def test_same_map_different_layout_never_co_locates(self):
  raw=bytearray(self.raw);raw[14]=1;payload=raw.hex();self.publish('other',payload)
  self.join();self.join('bob',payload=payload)
  self.assertNotIn('PEER bob',self.s._snapshot(self.s.peers['alice']));self.assertNotEqual(*self.s._link_presence().scopes.values())
 def test_party_only_republication_keeps_room_but_layout_removes_it(self):
  self.join();raw=bytearray(self.raw);raw[50]=3;self.publish('owner',raw.hex());self.assertIsNotNone(r.scope(self.s,self.s.peers['alice']))
  raw[14]=1;self.publish('owner',raw.hex());self.assertIsNone(r.scope(self.s,self.s.peers['alice']))
 def test_expiration_leave_disconnect_and_native_map_revalidation(self):
  self.join();p=self.s.peers['alice'];p['base_room']['at']-=4;self.assertIsNone(r.scope(self.s,p))
  self.join(seq=2);p['state'][1]=6;self.assertIsNone(r.scope(self.s,p));self.assertEqual(self.join(seq=3),'B ROOM 3 0\n')
  p['state'][1]=0;self.join(seq=4);del self.s.link_channels['alice'];self.assertIsNone(r.scope(self.s,p))
 def test_stale_channel_sequence_and_ambiguous_clones(self):
  old=dict(self.s.link_channels['alice']);self.assertEqual(r.handle(self.s,old,('B ROOM 1 '+r.digest(self.payload)).encode()),'B ROOM 1 0\n')
  self.join();self.assertEqual(self.join(),'B ROOM 1 0\n');self.publish('copy',self.payload);self.assertIsNone(r.scope(self.s,self.s.peers['alice']))
 def test_remove_and_normal_route_behavior(self):
  self.join();self.join('bob');self.db.execute('DELETE FROM base_neighborhood');self.assertNotIn('PEER bob',self.s._snapshot(self.s.peers['alice']))
  for p in self.s.peers.values():p['state'][:2]=[0,16]
  self.assertIn('PEER bob',self.s._snapshot(self.s.peers['alice']));self.assertIn('FRIEND bob',self.s._snapshot(self.s.peers['alice']))
 def test_native_map_order_and_reject_invalid_locations(self):
  for group in range(24):self.assertEqual(r.room_map(group*10+1),(25,(group%4)*6+group//4))
  for invalid in [0,4,10,240,255]:self.assertIsNone(r.room_map(invalid))
 def test_actual_transport_dispatch(self):
  out=[];self.s._queue=lambda c,line:out.append(line)
  actual_method('_link_line')(self.s,self.s.link_channels['alice'],('B ROOM 1 '+r.digest(self.payload)).encode());self.assertEqual(out,['B ROOM 1 1\n'])
 def test_native_protocol_enabled_and_disabled(self):
  with tempfile.TemporaryDirectory() as t:
   d=pathlib.Path(t);(d/'platform').mkdir();(d/'platform/world_neighborhood.h').write_text((NATIVE/'include/platform/world_neighborhood.h').read_text())
   (d/'test.c').write_text((ROOT/'test/native_room.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_neighborhood.c')))
   for enabled in [0,1]:
    subprocess.run(['cc','-std=c99','-DPORTABLE',f'-DEW_SHARED_BASE_ROOMS={enabled}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_idle_expiration_schedules_removal(self):
  self.join();calls=[];self.s._schedule_presence=lambda t:calls.append(t)
  self.s.peers['alice']['base_room']['at']-=4;r.expire(self.s,time.monotonic());self.assertEqual(len(calls),1);self.assertNotIn('base_room',self.s.peers['alice'])
 def test_actual_native_room_digest_excludes_private_party(self):
  source=(NATIVE/'src/world/world_base_share.c').read_text();wire=(NATIVE/'src/world/world_cave_wire.c').read_text()
  def func(s,name):
   a=s.index(name);a=s.rfind('\n',0,a)+1;b=s.index('\n}',a)+2;return s[a:b]
  # Use exact native Encode/room validation and SHA implementation, not a Python reimplementation.
  helper=wire[wire.index('static const u32 k'):wire.index('static void Digest')]+func(wire,'void WorldCaveWire_BytesDigest')
  code=(ROOT/'test/native_digest.c').read_text().replace('ACTUAL_HELPERS',helper+'\n'+next(line for line in source.splitlines() if line.startswith('static void Put'))+'\n'+func(source,'static void Encode')+'\n'+func(source,'bool8 WorldBase_RoomDigest'))
  with tempfile.TemporaryDirectory() as t:
   d=pathlib.Path(t);(d/'test.c').write_text(code);subprocess.run(['cc','-std=c99','-fsanitize=undefined',str(d/'test.c'),'-o',str(d/'test')],check=True)
   lines=subprocess.check_output([str(d/'test')],text=True).splitlines()
  raw=bytearray(46);raw[0]=1;raw[2]=2
  self.assertEqual(lines[0],hashlib.sha256(raw).hexdigest());self.assertEqual(lines[0],lines[1]);self.assertNotEqual(lines[1],lines[2])
 def test_actual_adjacent_meeting_is_scoped_and_truthful(self):
  a=self.s.peers['alice'];b=self.s.peers['bob'];a.update(social=True,seq=0);b['social']=True;b['state'][3]=3
  events=[];self.s._event=lambda kind,data:events.append((kind,data));self.s._broadcast=lambda:None
  meet=actual_method('_meet')
  with self.assertRaises(ValueError):meet(self.s,a,['MEET','1','bob'])
  self.join();self.join('bob');meet(self.s,a,['MEET','1','bob'])
  self.assertEqual(len(events),1);self.assertEqual(events[0][1]['base_room'],r.scope(self.s,a));self.assertEqual(events[0][1]['signal'],'explore')
if __name__=='__main__':unittest.main()
