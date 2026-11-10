import unittest
from unittest.mock import patch
import test_actor_methods as fixture
from world import method_exchange as exchange, actor_methods as methods,actor_runtime as runtime

class ExchangeTests(fixture.MethodTests):
 def lesson(self):
  self.source(x=75,y=70);record=self.retain()
  args=dict(lesson='route_lesson',recipient='second',method='explore',digest=record['digest'])
  with self.s.db:result=exchange.offer(self.s,'harbor_guide',{},args)
  return result,args
 def test_recipient_accepts_then_actually_moves(self):
  offer,args=self.lesson()
  self.assertFalse(self.s.db.execute("SELECT 1 FROM actor_methods WHERE actor='second'").fetchone())
  self.apply(dict(id='learn',purpose='Learn a demonstrated method.',steps=[dict(id='accept',tool='world.respond_method',args=dict(lesson=offer['lesson'],decision='accept',name='learned_route'),after=[])]),'second')
  self.assertEqual(runtime.tick(self.s,now=60)['status'],'succeeded')
  record=next(r for r in methods.catalog(self.s) if r['actor']=='second')
  self.assertEqual(record['teacher']['actor'],'harbor_guide')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],1)
  p=self.invoke(record['digest'],77,73);p['steps'][0]['args']['method']='learned_route'
  self.apply(p,'second');self.assertEqual(runtime.tick(self.s,now=66)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=72)['status'],'pending');self.f.advance(30,True)
  for n in range(31,65):self.f.advance(n)
  self.assertEqual(runtime.tick(self.s,now=110)['status'],'succeeded');self.assertEqual(runtime.tick(self.s,now=116)['status'],'succeeded')
  obj=next(o for o in self.s.objects if o['id']=='second');self.assertEqual((obj['x'],obj['y']),(77,73))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_journey_receipts').fetchone()[0],2)
  self.assertIn('teacher: harbor_guide',' '.join(methods.command(self.s,None,['second'])))
 def test_decline_withdraw_expiry_and_wrong_actor(self):
  offer,args=self.lesson();reply=dict(lesson=offer['lesson'],decision='accept',name='route')
  with self.assertRaises(ValueError):exchange.respond(self.s,'harbor_guide',{},reply)
  with patch('world.method_exchange.time.time',return_value=10**12):
   with self.assertRaises(ValueError):exchange.respond(self.s,'second',{},reply)
  exchange.respond(self.s,'second',{},dict(reply,decision='decline'))
  self.assertEqual(exchange.respond(self.s,'second',{},reply)['status'],'declined')
  self.assertFalse(self.s.db.execute("SELECT 1 FROM actor_methods WHERE actor='second'").fetchone())
  args['lesson']='another';offer=exchange.offer(self.s,'harbor_guide',{},args)
  exchange.respond(self.s,'harbor_guide',{},dict(lesson=offer['lesson'],decision='withdraw',name=''))
  self.assertEqual(exchange.catalog(self.s)[0]['status'],'withdrawn')
 def test_restart_idempotence_and_no_reattribution(self):
  offer,args=self.lesson();self.s.db.commit()
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
  self.f.s=self.s;self.f.f.server=self.s;self.f.f.candidate=self.s.candidate
  self.assertEqual(exchange.offer(self.s,'harbor_guide',{},args)['status'],'offered')
  reply=dict(lesson=offer['lesson'],decision='accept',name='route')
  with self.s.db:exchange.respond(self.s,'second',{},reply)
  record=next(r for r in methods.catalog(self.s) if r['actor']=='second')
  with self.assertRaises(ValueError):exchange.offer(self.s,'second',{},dict(lesson='relay',recipient='harbor_guide',method='route',digest=record['digest']))
  before=len(self.s.memory.history()['events']);self.assertEqual(exchange.respond(self.s,'second',{},reply)['status'],'accepted')
  self.assertEqual(len(self.s.memory.history()['events']),before)
 def test_stale_meeting_and_name_conflict(self):
  offer,args=self.lesson();reply=dict(lesson=offer['lesson'],decision='accept',name='route')
  obj=next(o for o in self.s.objects if o['id']=='second');old=obj['x'];obj['x']=90
  with self.assertRaises(ValueError):exchange.respond(self.s,'second',{},reply)
  obj['x']=old;self.s.db.execute("INSERT INTO actor_methods VALUES('second','route','different','{}')")
  with self.assertRaises(ValueError):exchange.respond(self.s,'second',{},reply)
  self.assertEqual(exchange.catalog(self.s)[0]['status'],'offered')

 def test_failed_receipt_rolls_back_adoption(self):
  import sqlite3
  offer,args=self.lesson();self.s.db.commit()
  self.s.db.execute("CREATE TRIGGER fail_lesson BEFORE UPDATE ON method_lessons BEGIN SELECT RAISE(ABORT,'injected'); END")
  self.s.db.commit()
  with self.assertRaises(sqlite3.IntegrityError):
   with self.s.db:exchange.respond(self.s,'second',{},dict(lesson=offer['lesson'],decision='accept',name='route'))
  self.assertFalse(self.s.db.execute("SELECT 1 FROM actor_methods WHERE actor='second'").fetchone())
  self.assertEqual(exchange.catalog(self.s)[0]['status'],'offered')

if __name__=='__main__':unittest.main()
