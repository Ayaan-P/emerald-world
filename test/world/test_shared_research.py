import sqlite3,tempfile,time,types,unittest
from unittest import mock
from world import shared_research as r
class Research(unittest.TestCase):
 def presence(self,run):
  return dict(campaign_run=run,state=[1,4,5,5,0,0,1],state_time=time.monotonic())
 def server(self,path=':memory:'):
  s=types.SimpleNamespace(db=sqlite3.connect(path),revision=0,events=[])
  def append(kind,data):s.events.append((kind,data));return len(s.events)
  s.memory=types.SimpleNamespace(append=append);s.link_protocol=types.SimpleNamespace(busy=lambda who:False)
  return s
 def test_atomic_aggregate_restart_and_retries(self):
  with tempfile.TemporaryDirectory() as d:
   s=self.server(d+'/state');a=dict(id='private_alice',presence=self.presence('private_save'))
   self.assertEqual(r.handle(s,a,b'D REPORT 1 13'),'D ACK 1\n')
   self.assertEqual(r.handle(s,a,b'D REPORT 1 13'),'D ACK 1\n');self.assertEqual(len(s.events),1)
   b=dict(id='bob',presence=self.presence('different'))
   r.handle(s,b,b'D REPORT 1 e0');self.assertEqual([(e['dex'],e['seen'],e['caught']) for e in r.catalog(s)['entries']],[(1,True,True),(2,True,True),(3,True,True)])
   self.assertNotIn('private_',str(s.events));s.db.close();s=self.server(d+'/state');self.assertEqual(len(r.catalog(s)['entries']),3)
   self.assertTrue(any('BULBASAUR' in x for x in r.command(s,{},['1'])))
 def test_research_gap_lists_are_public_bounded_and_update_after_publication(self):
  s=self.server(); alice=dict(id='private_alice',presence=self.presence('private_save'))
  with unittest.mock.patch.object(r,'names',return_value={1:'BULBASAUR',2:'IVYSAUR',3:'VENUSAUR',5:'CHARMELEON'}):
   self.assertEqual(r.handle(s,alice,b'D REPORT 1 3'),'D ACK 1\n')
   unreported=r.command(s,{},['unreported']);uncaught=r.command(s,{},['uncaught'])
   self.assertTrue(any('#3 VENUSAUR' in x for x in unreported))
   self.assertFalse(any('#1 BULBASAUR' in x for x in unreported))
   self.assertTrue(any('#2 IVYSAUR: not reported' in x for x in unreported))
   self.assertFalse(any('#1 BULBASAUR' in x for x in uncaught))
   self.assertTrue(any('Voluntary reports' in x for x in unreported))
   self.assertNotIn('private_',str(unreported))
   self.assertTrue(any('No entries' in x for x in r.command(s,{},['unreported','255'])))
   from world.guilds import GuildError
   with self.assertRaises(GuildError):r.command(s,{},['unreported','-1'])
   self.assertEqual(r.handle(s,alice,b'D REPORT 1 01'),'D ACK 1\n')
   self.assertTrue(any('#3 VENUSAUR: seen reported' in x for x in r.command(s,{},['uncaught'])))
   self.assertFalse(any('#3 VENUSAUR' in x for x in r.command(s,{},['unreported'])))
 def test_rejects_bad_frames_and_no_save(self):
  s=self.server();c=dict(id='a',presence=dict(campaign_run='b'))
  for frame in (b'D REPORT 2 1',b'D REPORT 1 1g',b'D REPORT 1 ',b'D REPORT 1 '+b'1'*514,b'D REPORT 1 1 2'):
   self.assertEqual(r.handle(s,c,frame),'D ERROR 1\n')
  self.assertEqual(r.catalog(s)['entries'],[]);c['presence'].clear();self.assertEqual(r.handle(s,c,b'D REPORT 1 3'),'D ERROR 1\n')
 def test_no_flags_does_not_create_event(self):
  s=self.server();self.assertEqual(r.handle(s,dict(id='a',presence=self.presence('s')),b'D REPORT 1 000'),'D ACK 1\n');self.assertEqual(s.events,[])
