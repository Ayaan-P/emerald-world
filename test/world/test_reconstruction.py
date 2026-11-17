import json,unittest
from pathlib import Path
import test_actor_environment as fixture
from world import actor_runtime as runtime,shared_terrain,reconstruction
class Reconstruction(unittest.TestCase):
 def setUp(self):
  self.f=fixture.EnvironmentTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
 def plan(self,actor='canon_rydel'):
  self.f.f.apply(dict(id='rebuild',purpose='Plan actual public terrain reconstruction.',steps=[dict(id='inspect',tool='world.inspect_environment',args=dict(x=10,y=10,width=4,height=4),after=[]),dict(id='build',tool='world.reconstruct_environment',args=dict(observation=dict(result='inspect',key='tool_receipt'),tiles=json.dumps([dict(x=11,y=11,terrain='water'),dict(x=12,y=11,terrain='tall_grass')])),after=['inspect'])]),actor=actor,version=1 if actor=='canon_wally' else 0)
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending')
  return reconstruction.catalog(self.s)[0]['id']
 def test_occupied_pending_restart_actual_commit_and_receipt_recovery(self):
  identity=self.plan();before=self.s._active_terrain()
  p=self.s.peers['Alice'];p['cave_capable']=True;p['in_generated_cave']=True
  self.assertIsNone(runtime.tick(self.s,now=22));self.assertEqual(self.s._active_terrain(),before)
  self.assertIn('pending',reconstruction.command(self.s,p,[])[1])
  # Restart leaves an actual persisted pending plan; no synthetic participant claim.
  db=self.s.db.execute('PRAGMA database_list').fetchone()[2]
  from test_shared_generated_cave import MemoryAuthority
  self.s.close();self.s=MemoryAuthority('/tmp/reconstruction-not-listening',Path(db).parent,persist_generated_cave=True,archive_generated_areas=True);self.addCleanup(self.s.close)
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'succeeded')
  self.assertFalse(self.s._active_walkable(11,11));self.assertEqual(shared_terrain.validate(self.s.shared_cave,self.s._active_terrain()[1]),{(11,11):2,(12,11):1})
  revision=self.s._active_terrain()[0];self.assertEqual(reconstruction.catalog(self.s)[0]['status'],'committed')
  # Simulate lost plan-receipt write after terrain+job committed: poll returns durable result, no second edit.
  result=reconstruction.poll(self.s,'canon_rydel',{},dict(reconstruction=identity))
  self.assertEqual(result['outcome'],'deferred_terrain_committed');self.assertEqual(self.s._active_terrain()[0],revision)
  self.assertIsNone(runtime.tick(self.s,now=40))
 def test_intervening_change_conflicts_not_rebased(self):
  self.plan('canon_wally');self.s.set_shared_geometry(self.s.shared_cave.identity,[dict(x=14,y=14,terrain='grass')])
  result=runtime.tick(self.s,now=22);self.assertEqual(result['status'],'succeeded')
  self.assertEqual(reconstruction.catalog(self.s)[0]['status'],'conflict')
  self.assertEqual(shared_terrain.validate(self.s.shared_cave,self.s._active_terrain()[1]),{(14,14):0})
  receipt=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE step='build'").fetchone()[0]);self.assertEqual(receipt['outcome'],'reconstruction_conflict');self.assertFalse(receipt['changed'])
 def test_cancel_ownership_and_host_admin(self):
  identity=self.plan()
  with self.assertRaises(ValueError):reconstruction.cancel(self.s,'canon_wally',{},dict(id=identity))
  conn=dict(out=bytearray(),closing=False,sock=object(),id=None,admin=True);self.s.connections[conn['sock']]=conn
  self.s._admin_line(conn,json.dumps(dict(command='reconstruction',cancel=identity)).encode());self.assertTrue(json.loads(conn['out'])['ok'])
  self.s.connections.pop(conn['sock']);self.assertEqual(runtime.tick(self.s,now=22)['status'],'blocked');self.assertEqual(self.s._active_terrain()[0],0)
 def test_no_commit_when_peer_state_still_inside(self):
  self.plan();p=self.s.peers['Alice'];p['cave_capable']=True;p['in_generated_cave']=False;p['state'][:2]=list(self.s.wilds_map)
  self.assertIsNone(runtime.tick(self.s,now=22));self.assertEqual(self.s._active_terrain()[0],0)
 def test_public_command_and_no_player_cancellation(self):
  self.plan();p=self.s.peers['Alice'];self.assertTrue(self.s.guild_chat.handle(p,'/guild reconstruction'))
  from world.guilds import GuildError
  with self.assertRaises(GuildError):reconstruction.command(self.s,p,['cancel','anything'])
 def test_returning_client_receives_real_geometry_payload(self):
  self.plan();self.assertEqual(runtime.tick(self.s,now=22)['status'],'succeeded')
  token=self.s.create_identity('Returner')['token'];c=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.s._line(c,('HELLO 1 Returner '+token+' SOCIALTRAVELCHATRALLYCAVE9G').encode());c['out'].clear();self.s._line(c,b'CAVE GET')
  self.assertIn(b'CAVE TERRAIN ',c['out']);self.assertIn(b'020b0b020c0b01',c['out'])
