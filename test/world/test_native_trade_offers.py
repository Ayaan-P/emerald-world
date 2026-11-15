import copy,sqlite3,time,unittest
import test_native_residents as fixture
from world import native_trade_offers as trade,actor_runtime
class Offers(unittest.TestCase):
 def setUp(self):
  self.f=fixture.ResidentTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.assertEqual(self.f.publish(self.f.definition())['status'],'succeeded')
  self.obj=next(o for o in self.s.objects if o['id']=='visitor')
  self.peer=self.f.f.f.connect('Buyer').sock.conn
  self.peer['state']=[self.obj['group'],self.obj['num'],self.obj['x']-1,self.obj['y'],1,7,1];self.peer['state_time']=time.monotonic()
  self.channel=dict(id='Buyer',presence=self.peer,out=bytearray(),sock=object());self.s.link_channels['Buyer']=self.channel;self.s.connections[self.channel['sock']]=self.channel
 def configure(self):
  state=copy.deepcopy(self.s.module_state);a=state['world_characters']['visitor'];a['version']+=1
  a['plan']=dict(id='offer',purpose='Offer a template, not my own companion.',steps=[dict(id='configure',tool='world.configure_native_trade',args=dict(requested='PIKACHU',offered='EEVEE'),after=[])])
  self.f.f.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
  self.assertIsNone(self.s.module_error);out=None
  for now in range(30,90,6):
   result=actor_runtime.tick(self.s,now=now)
   if result and result.get('actor')=='visitor':out=result
  self.assertIsNotNone(out);self.assertEqual(out['status'],'succeeded')
 def test_real_plan_offer_restart_and_no_trade_claim(self):
  self.configure();before=self.s.db.total_changes
  response=trade.handle(self.s,self.channel,b'NT GET 1 visitor');self.assertTrue(response.endswith(' 25 133\n'),response)
  self.assertEqual(self.s.db.total_changes,before)
  self.s._link_line(self.channel,b'NT GET 2 visitor');self.assertIn(b'NT OFFER 2',self.channel['out'])
  db=sqlite3.connect(':memory:');self.s.db.backup(db);old=self.s.db;self.s.db=db
  try:self.assertEqual(trade.catalog(self.s)['offers'][0]['offered'],133)
  finally:self.s.db=old;db.close()
  self.assertEqual(trade.handle(self.s,self.channel,b'NT COMPLETE 1 visitor'),'NT FAIL 0\n')
  events=self.s.memory.history()['events'];self.assertTrue(any(e.get('event')=='native_trade_template_changed' for e in events))
  self.assertFalse(any(e.get('event') in ('native_trade_completed','character_companion_received') for e in events))
 def test_spatial_session_and_busy_guards(self):
  with self.s.db:trade.configure(self.s,'visitor',{},dict(requested='PIKACHU',offered='EEVEE'))
  self.peer['state'][2]-=4;self.assertEqual(trade.handle(self.s,self.channel,b'NT GET 1 visitor'),'NT FAIL 1\n')
  self.peer['state'][2]+=4;self.peer['state_time']=0;self.assertEqual(trade.handle(self.s,self.channel,b'NT GET 2 visitor'),'NT FAIL 2\n')
  self.peer['state_time']=time.monotonic();self.peer['character_pending']=dict(id='visitor');self.assertEqual(trade.handle(self.s,self.channel,b'NT GET 3 visitor'),'NT FAIL 3\n')
  self.peer.pop('character_pending');self.s.link_channels.clear();self.assertEqual(trade.handle(self.s,self.channel,b'NT GET 4 visitor'),'NT FAIL 0\n')
 def test_validation_close_and_rollback(self):
  for args in [dict(requested='PIKACHU',offered='PIKACHU'),dict(requested='MEW',offered='EEVEE'),dict(requested=25,offered=133)]:
   with self.assertRaises(ValueError):trade.configure(self.s,'visitor',{},args)
  trade.setup(self.s.db)
  self.s.db.execute("CREATE TRIGGER reject_template BEFORE INSERT ON native_trade_offers BEGIN SELECT RAISE(ABORT,'no'); END")
  with self.assertRaises(sqlite3.IntegrityError):
   with self.s.db:trade.configure(self.s,'visitor',{},dict(requested='PIKACHU',offered='EEVEE'))
  self.assertFalse(trade.catalog(self.s)['offers'])
  self.s.db.execute('DROP TRIGGER reject_template')
  with self.s.db:
   trade.configure(self.s,'visitor',{},dict(requested='PIKACHU',offered='EEVEE'));trade.configure(self.s,'visitor',{},dict(requested='',offered=''))
  self.assertFalse(trade.catalog(self.s)['offers'])
