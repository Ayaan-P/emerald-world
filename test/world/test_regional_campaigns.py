import json,sqlite3,unittest
from copy import deepcopy
import test_combined_regions as fixture
from world import battle_campaigns as campaigns,campaign_visits,regional_campaigns
from world.combined_regions import DIGEST
from world.guilds import GuildError
from world.campaign_board import rows

class RegionalCampaigns(unittest.TestCase):
 def setUp(self):
  self.f=fixture.WireHandlers();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.a,self.al=self.f.peer('Alice');self.b,self.bl=self.f.peer('Bob')
  self.a['campaign_run']='a'*32;self.b['campaign_run']='b'*32
  self.doc=dict(id='across_regions',title='Choose your shared journey',entry='pallet',nodes={
   'pallet':dict(visit=dict(label='Pallet arrival',point=[38,0,6,8],registry=DIGEST),next=['hoenn','kanto']),
   'hoenn':dict(visit=dict(label='Slateport return',point=[0,1,19,20]),next=[]),
   'kanto':dict(visit=dict(label='Pallet meeting',point=[38,0,7,8],registry=DIGEST),next=[])})
  with self.s.db:campaigns.publish(self.s,'author',{},dict(campaign=json.dumps(self.doc)))
 def arrive(self,p,x=6,y=8):
  self.f.state(p,p['seq']+1,38,0,x,y)
  self.assertFalse(p['closing']);self.assertNotIn(b'ERROR',p['out'])
 def test_shared_board_branches_and_independent_checkins(self):
  campaigns.command(self.s,self.a,['share','across_regions']);key=campaigns.active(self.s,self.a)[1]['shared']
  campaigns.command(self.s,self.b,['join',key]);campaigns.command(self.s,self.a,['begin'])
  self.assertTrue(any('PalletTown' in label for label,_ in rows(self.s,self.a)))
  self.arrive(self.a);campaigns.command(self.s,self.a,['check-in'])
  self.assertEqual(campaigns.active(self.s,self.a)[1]['status'],'waiting')
  self.arrive(self.b);campaigns.command(self.s,self.b,['check-in'])
  campaigns.command(self.s,self.a,['choose','hoenn'])
  for p in (self.a,self.b):
   self.f.state(p,p['seq']+1,0,1,19,20);campaigns.command(self.s,p,['check-in'])
  for p in (self.a,self.b):
   data=campaigns.active(self.s,p)[1];self.assertEqual(data['status'],'complete')
   self.assertEqual(data['history'][0]['registry'],DIGEST)
   self.assertEqual(data['history'][0]['basis'],'voluntary_fresh_client_presence')
 def test_registry_admission_stale_state_and_wrong_tile(self):
  campaigns.command(self.s,self.a,['start','across_regions']);self.arrive(self.a)
  self.al.pop('registry_digest')
  with self.assertRaises(GuildError):campaigns.command(self.s,self.a,['check-in'])
  self.al['registry_digest']=DIGEST;self.a['state_time']=0
  with self.assertRaises(GuildError):campaigns.command(self.s,self.a,['check-in'])
  self.arrive(self.a,7)
  with self.assertRaises(GuildError):campaigns.command(self.s,self.a,['check-in'])
  self.arrive(self.a);campaigns.command(self.s,self.a,['check-in'])
 def test_bounds_profile_and_immutable_document(self):
  for change in ('missing','wrong','bounds','default'):
   d=deepcopy(self.doc);d['id']='bad_'+change;v=d['nodes']['pallet']['visit']
   if change=='missing':v.pop('registry')
   if change=='wrong':v['registry']='0'*64
   if change=='bounds':v['point'][2]=24
   if change=='default':self.s.combined_regions=False
   with self.assertRaises(ValueError):campaigns.publish(self.s,'author',{},dict(campaign=json.dumps(d)))
   self.s.combined_regions=True
  d=deepcopy(self.doc);d['title']='Changed'
  with self.assertRaises(ValueError):campaigns.publish(self.s,'author',{},dict(campaign=json.dumps(d)))
 def test_restart_save_lineage_and_lost_profile(self):
  campaigns.command(self.s,self.a,['start','across_regions']);self.arrive(self.a);campaigns.command(self.s,self.a,['check-in'])
  self.a['campaign_run']='c'*32;self.assertIsNone(campaigns.active(self.s,self.a));self.a['campaign_run']='a'*32
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:
   campaigns.install(db);self.assertEqual(campaigns.active(self.s,self.a)[1]['status'],'choice')
   campaigns.command(self.s,self.a,['choose','kanto']);self.arrive(self.a,7)
   self.s.combined_regions=False
   with self.assertRaises(GuildError):campaigns.command(self.s,self.a,['check-in'])
  finally:self.s.db=old;db.close()
 def test_agent_discovery_is_bounded_not_reachability(self):
  page=regional_campaigns.inspect(self.s,'author',{},dict(region='kanto'))
  self.assertEqual(page['registry'],DIGEST);self.assertEqual(len(page['destinations']),16)
  self.assertEqual(page['next'],16);self.assertIn('not reachable',page['semantics'])
  self.assertTrue(all(m['group']>=35 for m in page['destinations']))
  self.s.combined_regions=False
  with self.assertRaises(ValueError):regional_campaigns.inspect(self.s,'author',{},dict(region='kanto'))
 def test_actual_kanto_guild_expedition_once_without_native_rewards(self):
  g=self.s.guilds
  g.command('Alice','create Travelers');g.command('Alice','invite Bob');g.command('Bob','accept Travelers')
  g.expedition('Alice',['start','PalletTown_Frlg','2'])
  self.arrive(self.a);self.assertEqual(self.s.db.execute('SELECT xp FROM guild_stats').fetchone()[0],0)
  self.arrive(self.b);self.assertEqual(self.s.db.execute('SELECT xp,expeditions FROM guild_stats').fetchone(),(10,1))
  self.arrive(self.a);self.arrive(self.b)
  self.assertEqual(self.s.db.execute('SELECT xp,expeditions FROM guild_stats').fetchone(),(10,1))
  self.assertEqual(self.s.db.execute("SELECT party_hash,bag_hash FROM identities WHERE id='Alice'").fetchone(),('a'*16,'b'*16))
