"""Actual decisions -> authorized private worker -> original native reply path."""
import copy,json,unittest
from unittest.mock import patch
import test_canonical_dialogues as fixture
from world import canonical_cast as cast,canonical_rapport as rapport
from world.canonical_reflection import claim,finish
from world.canonical_memory import acknowledge
from world.private_cast_worker import watch

class RapportTests(unittest.TestCase):
 def setUp(self):
  self.d=fixture.SharedDialogueTests();self.d.setUp();self.addCleanup(self.d.doCleanups)
  self.s=self.d.s;self.a=self.d.a;self.b=self.d.b
  self.d.remember(self.a,'a'*32);self.d.remember(self.b,'b'*32)
 def follow(self,p):
  lines=self.d.command(p,'reflect','follow')
  self.assertTrue(any('OpenAI' in x for x in lines[-6:]));self.assertTrue(all(len(x)<=113 for x in lines))
  self.d.command(p,'reflect','confirm',p['cast_reflection_preview']['nonce'])
 def admin(self,body):
  conn=dict(sock=object(),out=bytearray(),closing=False)
  self.s._admin_line(conn,json.dumps(body).encode());return json.loads(conn['out'])
 def model(self,text):
  context=json.loads(text[text.index('{'):]);self.assertIsNone(context['explicit_choice'])
  if not context['shared_decisions']:return dict(reply='I will leave the next choice open.',interpretation='Rydel is ready to consider a future explicit choice.')
  fact=context['shared_decisions'][0]
  if fact['own_answer']=='Travelling together':return dict(reply='You suggested travelling together. We can discuss that.',interpretation='Rydel considers the suggestion of shared travel without assuming the speaker agreed.')
  return dict(reply='You chose independent journeys. I will keep that in mind.',interpretation='Rydel considers the chosen independent journey without assuming a lasting preference.')
 def worker(self,n=1):return watch('unused','gpt-6-luna',max_jobs=n,idle_seconds=1,request=self.admin,author=self.model)
 def shown(self,p,run):
  response=cast.response(self.s,p,run,'rydel');acknowledge(self.s,p,run,'canon_rydel',response['digest']);return response['briefing']
 def choose(self):
  identifier=self.d.open();self.d.command(self.a,'listen',identifier);self.d.command(self.a,'advise',identifier,'together')
  self.d.command(self.b,'choose',identifier,'independent')
 def bump(self):
  old=cast.records(self.s.module_state)['canon_rydel'];a=self.d.f.action(old['version'])
  a['changes']['council']=copy.deepcopy(old['council']);self.d.f.apply(a)
 def test_two_players_grow_private_perspectives_after_real_decisions_without_reconfirming(self):
  before=copy.deepcopy(self.s.memory.history());inspection=copy.deepcopy(self.s.inspect())
  self.follow(self.a);self.follow(self.b)
  self.assertEqual(self.worker(2)['processed'],2)
  self.shown(self.a,'a'*32);self.shown(self.b,'b'*32)
  self.assertEqual(before,self.s.memory.history());self.assertEqual(inspection,self.s.inspect())
  self.assertIsNone(claim(self.s)['request']) # Seeing replies is not a generation loop.
  self.choose();public=copy.deepcopy(self.s.memory.history());inspection=copy.deepcopy(self.s.inspect())
  self.assertEqual(self.worker(2)['processed'],2)
  self.assertIn('suggested travelling',self.shown(self.a,'a'*32))
  self.assertIn('chose independent',self.shown(self.b,'b'*32))
  self.assertEqual(public,self.s.memory.history());self.assertEqual(inspection,self.s.inspect())
  rows=self.s.db.execute('SELECT trainer,interpretation FROM canonical_perspectives ORDER BY trainer').fetchall()
  self.assertIn('suggestion',rows[0][1]);self.assertIn('chosen independent',rows[1][1])
  self.assertIsNone(claim(self.s)['request'])
 def test_scope_survives_restart_but_other_save_and_revocation_do_not_inherit(self):
  self.follow(self.a);self.worker();self.shown(self.a,'a'*32)
  self.shown(self.a,'c'*32)
  self.assertIsNone(rapport.grant(self.s,'Alice','canon_rydel','c'*32))
  self.choose();self.assertIsNone(claim(self.s)['request']) # Alice acted on ungranted C, Bob never opted in.
  self.s.close();self.d.f.f.case.server=self.d.f.f.case.open();self.s=self.d.f.f.case.server
  self.d.s=self.s;self.d.f.s=self.s
  self.assertIsNotNone(rapport.grant(self.s,'Alice','canon_rydel','a'*32))
  self.a=self.d.f.peer();self.d.a=self.a;self.shown(self.a,'a'*32)
  self.d.command(self.a,'reflect','stop');self.assertIsNone(rapport.grant(self.s,'Alice','canon_rydel','a'*32))
  self.follow(self.a);job=claim(self.s)['request'];self.assertIsNotNone(job)
  self.d.command(self.a,'remember','off')
  with self.assertRaises(ValueError):finish(self.s,job['id'],job['lease'],dict(reply='Late reply.',interpretation='Late interpretation.'))
  self.assertIsNone(rapport.grant(self.s,'Alice','canon_rydel','a'*32))
 def test_daily_bound_no_passive_retry_and_new_decision_can_supersede_running_work(self):
  self.follow(self.a);job=claim(self.s)['request']
  self.choose() # Real new facts while the initial model call is running.
  self.assertFalse(finish(self.s,job['id'],job['lease'],dict(reply='Old reply.',interpretation='Old interpretation.'))['ok'])
  self.assertEqual(self.worker()['processed'],1)
  for _ in range(4):
   self.bump();self.choose()
   if self.s.db.execute("SELECT 1 FROM canonical_reflections WHERE status='pending'").fetchone():self.worker()
  consent=rapport.grant(self.s,'Alice','canon_rydel','a'*32)
  self.assertEqual(consent[3],4)
  self.assertIsNone(claim(self.s)['request'])
  with patch('world.canonical_rapport.time.strftime',return_value='2099-01-01'):
   with self.s.db:self.assertFalse(rapport.enqueue(self.s,'Alice','canon_rydel','a'*32))
  self.d.command(self.a,'forget')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_rapport').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_rapport_jobs').fetchone()[0],0)
 def test_preview_grants_nothing_and_host_watch_has_explicit_bound(self):
  self.d.command(self.a,'reflect','follow');self.assertIsNone(claim(self.s)['request'])
  now=[0]
  result=watch('unused','gpt-6-luna',max_jobs=2,idle_seconds=3,poll=1,request=self.admin,author=self.model,clock=lambda:now[0],sleep=lambda n:now.__setitem__(0,now[0]+n))
  self.assertEqual(result,dict(ok=True,status='idle_timeout',processed=0))
  self.follow(self.a)
  calls=[]
  def fail(text):calls.append(1);raise RuntimeError('provider failed')
  with self.assertRaises(RuntimeError):watch('unused','gpt-6-luna',request=self.admin,author=fail)
  self.assertEqual(len(calls),1)
  self.assertIsNone(claim(self.s)['request']) # Never replays an interrupted API call.
 def test_two_save_jobs_and_migration_preserve_exact_scope(self):
  self.follow(self.a)
  self.shown(self.a,'c'*32);self.follow(self.a)
  rows=self.s.db.execute('SELECT run,status FROM canonical_reflections ORDER BY run').fetchall()
  self.assertEqual(rows,[('a'*32,'pending'),('c'*32,'pending')])
  self.assertEqual(self.worker(2)['processed'],2)
  self.shown(self.a,'a'*32);self.shown(self.a,'c'*32)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM canonical_perspectives').fetchone()[0],2)
  self.d.command(self.a,'reflect','stop')
  self.assertIsNotNone(rapport.grant(self.s,'Alice','canon_rydel','a'*32))
  self.assertIsNone(rapport.grant(self.s,'Alice','canon_rydel','c'*32))
  import sqlite3
  db=sqlite3.connect(':memory:')
  self.addCleanup(db.close)
  db.execute('CREATE TABLE canonical_reflections(id TEXT PRIMARY KEY,trainer TEXT,actor TEXT,run TEXT,fingerprint TEXT,context TEXT,status TEXT,created REAL,lease TEXT,reply TEXT,interpretation TEXT,version INTEGER,UNIQUE(trainer,actor))')
  row=('request','Alice','canon_rydel','a'*32,'digest','{}','ready',1.,'lease','Reply','Perspective',1)
  db.execute('INSERT INTO canonical_reflections VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',row)
  rapport.install(db);rapport.install(db)
  self.assertEqual(db.execute('SELECT * FROM canonical_reflections').fetchone(),row)
  db.execute('INSERT INTO canonical_reflections VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('other',*row[1:3],'c'*32,*row[4:]))
  self.assertEqual(db.execute('SELECT count(*) FROM canonical_reflections').fetchone()[0],2)
