import json,pathlib,sqlite3,sys,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
pkg=types.ModuleType('route_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules['route_fixture']=pkg
from route_fixture import rydel_routes as board, shared_races, canonical_cast
class Memory:
 world_id='world'
 def __init__(self,db):self.db=db;db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,data TEXT)')
 def append(self,kind,row):return self.db.execute('INSERT INTO events(data) VALUES(?)',(json.dumps(dict(row,event=kind)),)).lastrowid
class Routes(unittest.TestCase):
 def setUp(self):
  self.clock=100.;self.db=sqlite3.connect(':memory:');self.messages=[]
  self.c=dict(id='Alice',core_active_run='a'*32,private_commands=True,state=[10,0,1,1,0,0,1],state_time=time.monotonic(),seq=1)
  self.d=dict(id='Bob',core_active_run='b'*32,private_commands=True,state=[10,0,1,1,0,0,1],state_time=time.monotonic(),seq=1)
  def place(c,name):
   if c['state'][:2]!=[10,0] or time.monotonic()-c['state_time']>3:raise ValueError('wrong place')
  guild=types.SimpleNamespace(_require=lambda n:(1,'friends'),_member=lambda n:(1,'friends'))
  self.s=types.SimpleNamespace(db=self.db,memory=Memory(self.db),revision=0,peers={'Alice':self.c,'Bob':self.d},
    core_story=types.SimpleNamespace(_place=place),link_protocol=types.SimpleNamespace(busy=lambda n:False),guilds=guild,
    cave_map=(255,1),wilds_map=(255,2),relays=types.SimpleNamespace(_fresh=lambda c,n:bool(c['state'][6]),_current=lambda n:False,_location=lambda p:str(p)),
    flags=types.SimpleNamespace(current=lambda n:False),mysteries=types.SimpleNamespace(_current=lambda n:False),
    guild_chat=types.SimpleNamespace(message=lambda *args:self.messages.append(args[-1])))
  self.s.races=shared_races.SharedRaces(self.s,lambda *p:dict(name='Route110'),clock=lambda:self.clock)
  self.course=dict(id='cycling_route',title='Rydel free ride',starts=[[0,1,1,1],[0,1,2,1]],checkpoints=[[0,1,3,1],[0,1,4,1]],laps=1,limit=60,mounted=False)
  self.s.races.publish(self.course);self.db.commit()
 def view(self,c=None):
  c=c or self.c;return board.panel(self.s,c,c['core_active_run'],'rydel','view')
 def pick(self,p,i,c=None):
  c=c or self.c;return board.panel(self.s,c,c['core_active_run'],'rydel',f"pick:{p['session']}:{p['version']}:{i}")
 def test_real_race_entry_finish_and_voluntary_history(self):
  p=self.pick(self.pick(self.view(),1),1);self.assertIn('No teleport',p['question'])
  p=self.pick(p,1);self.assertIn('lobby opened',p['question'])
  r=self.s.races.current('Alice');self.assertEqual(r['phase'],'lobby');self.assertFalse(r['ready'])
  q=self.pick(self.view(self.d),2,self.d);self.pick(q,1,self.d)
  for i,c in enumerate((self.c,self.d)):
   c['state'][:4]=self.course['starts'][i];c['state_time']=self.clock
   self.s.races.command(c,['ready'])
  self.clock+=3;self.s.races.tick()
  for target in self.course['checkpoints']:
   self.clock+=1
   for c in (self.c,self.d):c['state'][:4]=target;c['state_time']=self.clock
   self.s.races.tick()
  self.assertEqual(self.db.execute('SELECT count(*) FROM race_results').fetchone()[0],2)
  self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
  self.c['state'][:2]=[10,0];self.c['state_time']=time.monotonic()
  p=self.pick(self.view(),3);self.assertIn('ALL players',p['question'])
  self.pick(p,1)
  event=json.loads(self.db.execute('SELECT data FROM events').fetchone()[0])
  self.assertTrue(canonical_cast.reaction_activity(event,'canon_rydel',{}));self.assertTrue(canonical_cast.decision_evidence(event,'canon_rydel',{}))
  self.assertNotIn('Alice',json.dumps(event));self.assertNotIn('Bob',json.dumps(event));self.assertNotIn('run',event)
  # Independent author may publish a different real route; no automatic promise/reward.
  second=dict(self.course,id='return_route',title='A new route',laps=2)
  shared_races.publish(self.s,'canon_rydel',{},dict(course=json.dumps(second)))
  self.assertEqual(self.s.races.course('return_route')['laps'],2)
  self.pick(self.pick(self.view(),3),1)
  self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
 def test_stale_forged_and_wrong_place(self):
  p=self.view();self.pick(p,1)
  with self.assertRaises(ValueError):self.pick(p,3)
  p=self.view();self.c['rydel_board']['until']=0
  with self.assertRaises(ValueError):self.pick(p,1)
  self.c['state'][0]=9
  with self.assertRaises(ValueError):self.view()
  self.c['state'][0]=10;self.s.link_protocol.busy=lambda n:True
  with self.assertRaises(ValueError):self.view()
 def test_cancel_and_private_records(self):
  self.db.execute('INSERT INTO race_results VALUES(?,?,?,?,?)',('run','cycling_route','Bob',9000,'[9000]'));self.db.commit()
  p=self.pick(self.view(),3);self.assertIn('No completed',p['question'])
  self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
 def test_restart_dedup(self):
  self.db.execute('INSERT INTO race_results VALUES(?,?,?,?,?)',('run','cycling_route','Alice',9000,'[9000]'));self.db.commit()
  self.pick(self.pick(self.view(),3),1)
  copy=sqlite3.connect(':memory:');self.db.backup(copy);self.s.db=copy;self.s.memory.db=copy;self.s.races.db=copy
  self.c.pop('rydel_board');self.pick(self.pick(self.view(),3),1)
  self.assertEqual(copy.execute('SELECT count(*) FROM events').fetchone()[0],1)
 def test_failed_publication_and_stale_join(self):
  self.db.execute('INSERT INTO race_results VALUES(?,?,?,?,?)',('run','cycling_route','Alice',9000,'[9000]'));self.db.commit()
  p=self.pick(self.view(),3)
  original=self.s.memory.append
  def failure(*args):
   original(*args);raise sqlite3.OperationalError('synthetic failure')
  self.s.memory.append=failure
  with self.assertRaises(sqlite3.OperationalError):self.pick(p,1)
  self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
  self.assertEqual(self.db.execute('SELECT count(*) FROM route_finish_shares').fetchone()[0],0)
  self.assertEqual(self.s.revision,0)
  self.s.races.command(self.c,['start','cycling_route'])
  p=self.pick(self.view(self.d),2,self.d)
  self.s.races.command(self.c,['leave'])
  with self.assertRaises(ValueError):self.pick(p,1,self.d)
 def test_long_title_and_rules(self):
  self.course['id']='z'*24;self.course['title']='Z'*55;self.course['laps']=8;self.course['limit']=1800;self.course['mounted']=True
  self.s.races.publish(self.course)
  p=self.pick(self.view(),1);p=self.pick(p,2)
  self.assertLessEqual(len(p['question']),160)
  p=self.pick(p,1);self.assertLessEqual(len(p['question']),160)
 def test_native_wiring_and_default(self):
  native=ROOT if (ROOT/'src/world/world_core_story.c').exists() else ROOT/'engines/expansion-native'
  s=(native/'src/world/world_core_story.c').read_text()
  self.assertIn('#define EW_RYDEL_ROUTES 0',s)
  self.assertIn('EW_RYDEL_ROUTES && (pressed&L_BUTTON)',s)
  self.assertIn('sCore.panelRace?"RACE":',s)
  self.assertIn('return keys&~L_BUTTON',s)
  self.assertIn('sCore.panelRace=race',s)
if __name__=='__main__':unittest.main()
