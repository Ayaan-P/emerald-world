"""Original Wally locations share one actor/private lineage, never story teams."""
from copy import deepcopy
import time,unittest
import test_canonical_cast as fixture
from world import canonical_cast as cast
from world.build_catalog import catalog_maps
from world.guilds import GuildError

class WallyContinuityTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  action=self.f.action();action['id']='canon_wally';action['changes']['dialogue']='I am thinking about what we can learn from the field teams.';self.f.apply(action)
  self.peer=self.f.peer();self.run='a'*32
 def place(self,name,peer=None):
  peer=peer or self.peer;key=next(k for k,v in catalog_maps().items() if v['name']==name)
  peer['state'][:2]=key;peer['state'][6]=1;peer['state_time']=time.monotonic()
 def request(self,key):return self.s.core_story.handle(self.peer,['CORE',self.run,'CAST',key,'safe'])
 def seen(self,key,digest):return self.s.core_story.handle(self.peer,['CORE',self.run,'SEEN',key,digest])
 def test_house_to_victory_road_retains_one_actor_without_public_progress_leak(self):
  public=deepcopy(self.s.memory.history());self.place('VerdanturfTown_WandasHouse')
  cast.guild_command(self.s,self.peer,['wally','remember','on'])
  first=self.request('wally');self.seen('wally',first['digest'])
  self.place('VictoryRoad_1F')
  with self.assertRaises(GuildError):cast.guild_command(self.s,self.peer,['wally','thoughts'])
  later=self.request('wally_vr');self.assertEqual(later['actor'],'canon_wally');self.assertIn('Good to see you again',later['briefing'])
  with self.assertRaises(ValueError):self.seen('wally',later['digest'])
  self.seen('wally_vr',later['digest'])
  self.assertTrue(cast.guild_command(self.s,self.peer,['wally','thoughts']))
  self.assertEqual(self.s.db.execute('SELECT actor,talks FROM canonical_encounters').fetchall(),[('canon_wally',2)])
  self.assertEqual(self.s.memory.history(),public);self.assertEqual(self.s.objects,[])
  self.place('LittlerootTown')
  with self.assertRaises(ValueError):self.request('wally_vr')
  with self.assertRaises(GuildError):cast.guild_command(self.s,self.peer,['wally','thoughts'])
 def test_other_connection_and_save_do_not_inherit_later_location_or_private_greeting(self):
  self.place('VictoryRoad_1F');cast.guild_command(self.s,self.peer,['wally','remember','on'])
  reply=self.request('wally_vr');self.seen('wally_vr',reply['digest'])
  bob=self.f.peer('Bob');self.place('VictoryRoad_1F',bob)
  with self.assertRaises(GuildError):cast.guild_command(self.s,bob,['wally','thoughts'])
  self.assertNotIn('Good to see you again',cast.response(self.s,bob,'b'*32,'wally_vr')['briefing'])
  self.run='c'*32;self.assertNotIn('Good to see you again',self.request('wally_vr')['briefing'])
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.peer=self.f.peer();self.run='a'*32;self.place('VictoryRoad_1F')
  self.assertIn('Good to see you again',self.request('wally_vr')['briefing'])
