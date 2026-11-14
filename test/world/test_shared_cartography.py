import sqlite3,time,unittest
import test_player_cargo as fixture
from world import shared_cartography as chart
from world.guilds import GuildError
class Cartography(unittest.TestCase):
 def setUp(self):
  self.f=fixture.PlayerCargoTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=self.f.peer;self.p['in_generated_cave']=True
  self.cave=self.s._connection_cave(self.p);self.origin=tuple(self.p['state'][2:4]);x,y=self.origin
  self.next=next((a,b) for a,b in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)] if self.cave.walkable(a,b))
 def move(self,point):self.p['state'][2:4]=point;self.p['state_time']=time.monotonic();chart.observe(self.s,self.p)
 def test_private_then_shared_does_not_backfill(self):
  chart.command(self.s,self.p,['private']);self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,False),{self.origin});self.assertFalse(chart.tiles(self.s,self.p,self.cave.identity,True))
  self.move(self.next);chart.command(self.s,self.p,['share','yes'])
  self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,True),{self.next})
  self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,False),{self.origin,self.next})
  chart.command(self.s,self.p,['stop']);self.move(self.origin);self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,True),{self.next})
 def test_render_and_route_only_reported_cells(self):
  chart.command(self.s,self.p,['private']);self.move(self.next)
  lines=chart.command(self.s,self.p,['show']);self.assertTrue(any('@' in line and '?' in line for line in lines[2:-1]));self.assertEqual(len(lines[2:-1]),9)
  self.assertIn('1 steps',chart.command(self.s,self.p,['route',*map(str,self.origin)])[0])
  self.assertIn('No connected',chart.command(self.s,self.p,['route','shared',*map(str,self.origin)])[0])
  self.assertIsNone(chart.route({(1,1),(3,1)},(1,1),(3,1)))
 def test_save_switch_and_revision_isolation(self):
  chart.command(self.s,self.p,['share','yes']);self.p['campaign_run']='save-b';self.move(self.next)
  self.assertNotIn('chart_mode',self.p);self.assertFalse(chart.tiles(self.s,self.p,self.cave.identity,False));self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,True),{self.origin})
  self.assertFalse(chart.tiles(self.s,self.p,'f'*64,True))
  self.p['cave_ack']='f'*64
  with self.assertRaises(GuildError):chart.command(self.s,self.p,['private'])
 def test_restart_and_no_automatic_consent(self):
  chart.command(self.s,self.p,['share','yes']);db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,False),{self.origin});self.p.pop('chart_mode');self.move(self.next);self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,True),{self.origin})
   columns=[r[1] for r in db.execute('PRAGMA table_info(shared_chart_tiles)')];self.assertEqual(columns,['revision','x','y'])
  finally:self.s.db=old;db.close()
 def test_chat_and_stale_safety(self):
  self.assertTrue(self.s.guild_chat.handle(self.p,'/guild chart private'));self.assertEqual(self.p['chart_mode'],'private')
  self.p['state_time']=0
  with self.assertRaises(GuildError):chart.command(self.s,self.p,['show'])
  self.p['state_time']=time.monotonic();self.p['state'][6]=0
  before=chart.tiles(self.s,self.p,self.cave.identity,False);chart.observe(self.s,self.p);self.assertEqual(before,chart.tiles(self.s,self.p,self.cave.identity,False))
 def test_two_players_combine_only_consented_tiles(self):
  chart.command(self.s,self.p,['private'])
  other=self.f.f.f.connect('Explorer',True)
  other.update(private_commands=True,campaign_run='second-save',in_generated_cave=True,cave_ack=self.cave.identity,state=list(self.p['state']),state_time=time.monotonic())
  other['state'][2:4]=self.next
  chart.command(self.s,other,['share','yes'])
  self.assertFalse(chart.tiles(self.s,other,self.cave.identity,False)&{self.origin})
  self.assertEqual(chart.tiles(self.s,self.p,self.cave.identity,True),{self.next})
  chart.command(self.s,self.p,['share','yes'])
  self.assertIn('1 steps',chart.command(self.s,self.p,['route','shared',*map(str,self.next)])[0])
  self.assertEqual(chart.tiles(self.s,other,self.cave.identity,False),{self.next})
