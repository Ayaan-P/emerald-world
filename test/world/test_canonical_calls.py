"""Real actor call requests, independent recipient disposition and durable quiet."""
import unittest,time,json
from copy import deepcopy
import test_canonical_cast as fixture
from world import canonical_cast as cast
class IncomingCallTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.action=self.f.action();self.action['id']='canon_wally';self.action['changes']['call']=dict(id='new_direction',text='The recent field news changed what I want to practice. Could we talk?')
  self.f.apply(self.action);self.a=self.f.peer();self.b=self.f.peer('Bob')
  for c,run in ((self.a,'a'*32),(self.b,'b'*32)):self.s.core_story.handle(c,['CORE',run,'SYNC','0','private'])
 def send(self,c,action,key,guard,run=None):return self.s.core_story.handle(c,['CORE',run or ('a'*32 if c is self.a else 'b'*32),action,key,guard])
 def test_private_delivery_decline_reconnect_other_player_and_restart(self):
  history=deepcopy(self.s.memory.history());inspect=deepcopy(self.s.inspect())
  first=self.send(self.a,'RING','1','private');self.assertEqual(first['caller'],'wally')
  self.assertEqual(self.send(self.a,'RING','1','private')['caller'],'-')
  self.send(self.a,'RACK',first['token'],'decline')
  self.assertEqual(self.send(self.a,'RING','1','private')['caller'],'-')
  again=self.send(self.a,'RING','1','manual');self.assertEqual(again,first)
  self.send(self.a,'RACK',again['token'],'answer')
  self.assertEqual(self.send(self.a,'RING','1','manual')['caller'],'-')
  other=self.send(self.b,'RING','1','private');self.assertNotEqual(other['token'],first['token'])
  with self.assertRaises(ValueError):self.send(self.b,'RACK',first['token'],'answer')
  self.assertEqual(self.s.memory.history(),history);self.assertEqual(self.s.inspect(),inspect)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s;self.f.f.server=self.s
  self.a=self.f.peer();self.send(self.a,'SYNC','0','private')
  self.assertEqual(self.send(self.a,'RING','1','private')['caller'],'-')
 def test_quiet_setting_cadence_new_requests_registration_and_actual_wire(self):
  self.send(self.a,'RSET','off','confirm');self.assertEqual(self.send(self.a,'RING','1','private')['caller'],'-')
  self.assertEqual(self.send(self.a,'RING','2','manual')['caller'],'-') # Not registered Wally.
  first=self.send(self.a,'RING','1','manual');self.assertEqual(first['caller'],'wally')
  self.send(self.a,'RACK',first['token'],'missed');self.send(self.a,'RSET','on','confirm')
  a=deepcopy(self.action);a['expected_version']=1;a['changes']['call']=dict(id='later_news',text='I reconsidered my plan after the public news.')
  self.f.apply(a)
  self.assertEqual(self.send(self.a,'RING','1','private')['caller'],'-')
  with self.s.db:self.s.db.execute('UPDATE canonical_calls SET created=created-601')
  self.a['out'].clear();self.s._line(self.a,('CORE '+'a'*32+' RING 1 private 77').encode())
  parts=self.a['out'].decode().strip().split();self.assertEqual(parts[:6],['CORE','REPLY','77','a'*32,'RING','1'])
  self.assertEqual(parts[7],'wally');self.assertEqual(bytes.fromhex(parts[9]).decode(),a['changes']['call']['text'])
 def test_busy_wrong_save_and_unsupported_actor_never_offer(self):
  self.a['state'][6]=0;self.assertEqual(self.send(self.a,'RING','1','private')['caller'],'-')
  self.a['state'][6]=1
  with self.assertRaises(ValueError):self.send(self.a,'RING','1','private',run='f'*32)
  bad=deepcopy(self.action);bad['id']='canon_briney'
  with self.assertRaises(ValueError):cast.compile_actions([bad],self.f.context())
  changed=deepcopy(self.action);changed['expected_version']=1;changed['changes']['call']['text']='Different message with reused identity.'
  with self.assertRaises(ValueError):self.f.apply(changed)
