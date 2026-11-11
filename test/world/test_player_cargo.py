import json,time,unittest
from unittest.mock import patch
import test_prop_custody as fixture
from world import player_cargo as cargo
from world.guilds import GuildError

class PlayerCargoTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CustodyTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.peer=self.f.f.connect('Carrier',True)
  self.f.f.f.f.send(self.peer,'CAVE GET');self.f.f.f.f.send(self.peer,'CAVE ACK '+self.s.shared_cave.identity)
  self.peer.update(private_commands=True,campaign_run='save-a')
  self.position(72,69,1)
 def position(self,x,y,facing):
  self.peer.update(state=[*self.s.wilds_map,x,y,facing,0,1],state_time=time.monotonic())
 def test_take_drop_native_snapshot_persistence_and_npc_reuse(self):
  self.assertTrue(any(line.startswith('REGION_PROP ') for line in self.s._snapshot(self.peer).splitlines()))
  self.assertIn('Carrying',cargo.command(self.s,self.peer,['take'])[0]);self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.assertFalse(any(line.startswith('REGION_PROP ') for line in self.s._snapshot(self.peer).splitlines()))
  self.f.f.f.advance(1);self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.position(72,72,4);cargo.command(self.s,self.peer,['drop','fixture'])
  obj=next(o for o in self.s.objects if o['id']=='fixture');self.assertEqual((obj['x'],obj['y']),(73,72))
  self.f.f.f.advance(2);self.assertEqual(next(o for o in self.s.objects if o['id']=='fixture')['y'],72)
  self.position(73,71,1);cargo.command(self.s,self.peer,['take']);self.position(72,69,1);cargo.command(self.s,self.peer,['drop','fixture'])
  self.f.take();self.assertEqual(self.s.inspect()['actor_runtime']['carried_props'][0]['owner'],'harbor_guide')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_prop_custody').fetchone()[0],1)
 def test_save_and_identity_scope_restart(self):
  cargo.command(self.s,self.peer,['take']);self.peer['campaign_run']='save-b'
  with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['drop','fixture'])
  self.peer['campaign_run']='save-a';owner=cargo.identity(self.s,self.peer)
  self.s.close();self.f.f.f.f.f.server=self.f.f.f.f.f.open();self.s=self.f.f.f.f.f.server
  self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.s.peers['Carrier']=self.peer
  self.assertEqual(cargo.identity(self.s,self.peer),owner)
  self.assertIn('fixture',str(cargo.command(self.s,self.peer,[])))
  self.peer['id']='Other';self.s.peers['Other']=self.peer
  with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['drop','fixture'])
 def test_collision_and_wrong_map_leave_custody(self):
  cargo.command(self.s,self.peer,['take']);self.position(70,70,4)
  with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['drop','fixture']) # actor at71,70
  self.peer['cave_ack']='f'*64
  with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['drop','fixture'])
  self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  self.assertEqual(self.s.db.execute('SELECT version FROM world_prop_custody').fetchone()[0],1)
 def test_receipt_failure_rolls_back_all_state(self):
  with patch.object(self.s.memory,'append',side_effect=ValueError('injected failure')):
   with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['take'])
  self.assertIn('fixture',[o['id'] for o in self.s.objects]);self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_prop_custody').fetchone()[0],0)
  self.assertIsNone(cargo.identity(self.s,self.peer))
 def test_public_receipt_has_no_identity_or_lineage_and_commands_are_private(self):
  self.s.guild_chat.handle(self.peer,'/guild cargo take')
  self.assertNotIn('fixture',[o['id'] for o in self.s.objects])
  data=self.s.db.execute("SELECT data FROM events WHERE kind='world_memory' ORDER BY seq DESC LIMIT 1").fetchone()[0]
  self.assertNotIn('Carrier',data);self.assertNotIn('save-a',data)
  self.assertEqual(json.loads(data)['event'],'player_world_cargo_changed')
 def test_stale_and_busy_are_rejected(self):
  self.peer['state_time']=0
  with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['take'])
  self.position(72,69,1);self.peer['character_pending']={'id':'harbor_guide'}
  with self.assertRaises(GuildError):cargo.command(self.s,self.peer,['take'])

if __name__=='__main__':unittest.main()
