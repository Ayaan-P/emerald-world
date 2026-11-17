import json,sqlite3,types,unittest,struct
from world import player_tournaments as t
from world.link_protocol import LinkProtocol
from world.guilds import GuildError
class Tournaments(unittest.TestCase):
 def make(self,db=None):
  s=types.SimpleNamespace(db=db or sqlite3.connect(':memory:'),peers={},link_channels={},events=[],watch=[])
  s.memory=types.SimpleNamespace(append=lambda k,v:s.events.append((k,v)))
  s.link_protocol=LinkProtocol(clock=lambda:0,id_factory=lambda:123)
  s.positions={}
  def deliver(messages):
   for who,line in messages:
    w=t.observe(s,who,line)
    if w:s.watch.append((who,w))
  s.deliver=deliver
  s._link_line=lambda c,raw:deliver(s.link_protocol.process(c['id'],raw,s.positions))
  for i,name in enumerate(('alice','bob','carol','dave')):
   s.peers[name]=dict(campaign_run='save_'+name);s.link_channels[name]=dict(id=name);s.positions[name]=[1,4,5+i,5,4,7,1]
  return s
 def join(self,s,n=2):
  t.publish(s,'organizer',{},dict(id='cup',title='Open cup',size=n))
  for who in list(s.peers)[:n]:t.command(s,dict(id=who),['join','cup','yes'])
 def paired(self,s,a='alice',b='bob'):
  t.command(s,dict(id=a),['fight','cup']);m=t.match(t.get(s,'cup'),a);wire=m['wire'];self.assertIsNotNone(wire)
  s._link_line(dict(id=b),f'L ACCEPT {wire}'.encode());self.assertIn((a,f'U WATCH {wire}\n'),s.watch)
  for who,slot in ((a,0),(b,1)):
   s._link_line(dict(id=who),f'L EVENT 1 {wire} 1 {slot} 1 0 8755 {"0"*32}'.encode())
  for who,slot in ((a,0),(b,1)):
   s._link_line(dict(id=who),f'L EVENT 4 {wire} 1 {slot} 1 0 8755 {"0"*32}'.encode())
  s._link_line(dict(id=a),f'L EVENT 3 {wire} 1 0 1 1 8755 {"0"*32}'.encode())
  return wire
 def report(self,s,who,wire,outcome):return t.result(s,dict(id=who,presence=s.peers[who]),f'U RESULT {wire} {outcome}'.encode())
 def test_real_coordinator_and_concordant_result(self):
  s=self.make();self.join(s);wire=self.paired(s)
  self.assertEqual(self.report(s,'alice',wire,1),f'U ACK {wire}\n');self.assertNotEqual(t.get(s,'cup')['status'],'complete')
  self.report(s,'bob',wire,2);self.assertEqual(t.get(s,'cup')['champion'],'alice')
  self.report(s,'alice',wire,1);self.assertEqual(len([e for e in s.events if e[0]=='player_tournament_match_reported']),1)
  self.assertEqual(self.report(s,'alice',wire,2),f'U ERROR {wire}\n')
 def test_disconnect_never_wins_and_disagreement_requires_both(self):
  s=self.make();self.join(s);wire=self.paired(s)
  s.deliver(s.link_protocol.disconnect('bob'));self.assertEqual(t.match(t.get(s,'cup'),'alice')['status'],'interrupted')
  self.report(s,'alice',wire,1);self.report(s,'bob',wire,1);self.assertEqual(t.match(t.get(s,'cup'),'alice')['status'],'disputed')
  t.command(s,dict(id='alice'),['retry','cup','yes']);self.assertEqual(t.match(t.get(s,'cup'),'alice')['status'],'disputed')
  t.command(s,dict(id='bob'),['retry','cup','yes']);self.assertEqual(t.match(t.get(s,'cup'),'alice')['status'],'ready')
 def test_restart_rejects_late_completion_and_save_switch(self):
  s=self.make();self.join(s);wire=self.paired(s);self.report(s,'alice',wire,1)
  db=sqlite3.connect(':memory:');s.db.backup(db);s=self.make(db);t.catalog(s)
  self.assertEqual(t.match(t.get(s,'cup'),'alice')['status'],'recovered');self.assertEqual(self.report(s,'bob',wire,2),f'U ERROR {wire}\n')
  s.peers['alice']['campaign_run']='other_save'
  with self.assertRaises(GuildError):t.command(s,dict(id='alice'),['retry','cup','yes'])
 def test_join_disclosure_and_no_result_before_handshake(self):
  s=self.make();t.publish(s,'a',{},dict(id='cup',title='Cup',size=2))
  self.assertIn('ALL world',t.command(s,dict(id='alice'),['join','cup'])[0]);self.assertEqual(t.get(s,'cup')['entrants'],[])
  for who in ('alice','bob'):t.command(s,dict(id=who),['join','cup','yes'])
  t.command(s,dict(id='alice'),['fight','cup']);s._link_line(dict(id='bob'),b'L ACCEPT 123')
  self.assertEqual(self.report(s,'alice','123',1),'U ERROR 123\n')

 def test_four_players_and_withdrawal(self):
  s=self.make();self.join(s,4)
  for a,b in [('alice','bob'),('carol','dave')]:
   wire=self.paired(s,a,b);self.report(s,a,wire,1);self.report(s,b,wire,2);s.deliver(s.link_protocol.disconnect(a))
  self.assertEqual(t.get(s,'cup')['round'],2);self.assertEqual(t.match(t.get(s,'cup'),'alice')['players'],['alice','carol'])
  s.positions['carol']=[1,4,6,5,3,7,1]
  wire=self.paired(s,'alice','carol');t.command(s,dict(id='carol'),['leave','cup'])
  self.assertEqual(t.get(s,'cup')['status'],'cancelled');self.assertEqual(self.report(s,'alice',wire,1),f'U ERROR {wire}\n')

 def test_organizer_can_release_unused_capacity(self):
  s=self.make();t.publish(s,'organizer',{},dict(id='empty',title='Empty',size=2))
  with self.assertRaises(ValueError):t.cancel(s,'other',{},dict(id='empty'))
  t.cancel(s,'organizer',{},dict(id='empty'));self.assertEqual(t.get(s,'empty')['status'],'cancelled')
