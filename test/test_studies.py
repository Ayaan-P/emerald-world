import importlib.util,json,pathlib,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
pkg=types.ModuleType('studyfixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
species=types.ModuleType('studyfixture.species_cohort');species.species_id=lambda n,c:{'WURMPLE':25,'ZIGZAGOON':133}[n];sys.modules[species.__name__]=species
cast=types.ModuleType('studyfixture.canonical_cast');cast.records=lambda s:s;sys.modules[cast.__name__]=cast
from studyfixture import birch_field_studies as study
class Studies(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
  self.run='a'*32;self.c=dict(id='player1',core_active_run=self.run,state=[1,4,5,8,1,1,0],state_time=time.monotonic(),canonical_location=dict(actor='canon_birch',map='LittlerootTown_ProfessorBirchsLab',run=self.run,version=3,expires=time.monotonic()+120))
  self.row=dict(version=3,tutor=dict(move=102,appearances=['birch'],research=dict(species=['WURMPLE','ZIGZAGOON'],days=2)))
  def place(c,n):
   if c['state'][:2]!=[1,4] or time.monotonic()-c['state_time']>3:raise ValueError('place')
  self.s=types.SimpleNamespace(db=self.db,module_state={'canon_birch':self.row},memory=types.SimpleNamespace(world_id='world'),core_story=types.SimpleNamespace(_place=place))
 def call(self,guard='view'):return study.handle(self.s,self.c,self.run,'birch',guard)
 def accept(self):
  p=self.call();return self.call('accept:'+p['token'])
 def test_retained_terms_restart_and_private_ownership(self):
  p=self.accept();self.assertEqual(p['mode'],'active')
  self.row['tutor']['move']=205;self.row['tutor']['research']['species']=['ZIGZAGOON'];self.row['version']=4
  saved=self.call();self.assertEqual(saved['move'],102);self.assertEqual(saved['species'],[25,133])
  db=sqlite3.connect(':memory:');self.addCleanup(db.close);self.db.backup(db);self.s.db=db
  self.c.pop('birch_study_preview',None);self.assertEqual(self.call()['species'],[25,133])
  self.c['id']='player2';self.assertIsNone(study.retained(self.s,self.c,self.run));self.c['id']='player1'
  self.assertIsNone(study.retained(self.s,self.c,'b'*32))
  self.s.module_state.clear();self.assertIsNotNone(study.fallback(self.s,self.c,self.run,'birch'))
  p=self.call();result=self.call('tutor:'+p['token']);self.assertEqual(result['mode'],'teach');self.assertEqual(result['move'],102)
  self.assertEqual(db.execute('SELECT count(*) FROM birch_field_studies').fetchone()[0],1)
  self.assertNotIn('caught',json.dumps(result));self.assertNotIn('complete',json.dumps(result))
 def test_revised_unaccepted_withdrawal_replay_leave_expiry(self):
  p=self.call();self.row['tutor']['move']=205
  with self.assertRaises(ValueError):self.call('accept:'+p['token'])
  p=self.call();self.row['tutor'].pop('research')
  with self.assertRaises(ValueError):self.call('accept:'+p['token'])
  self.row['tutor']['research']=dict(species=['WURMPLE'],days=1)
  p=self.accept()
  with self.assertRaises(ValueError):self.call('accept:'+p['token'])
  p=self.call();self.assertEqual(self.call('leave:'+p['token'])['mode'],'none');self.assertIsNone(study.retained(self.s,self.c,self.run))
  self.accept();self.db.execute('UPDATE birch_field_studies SET expires=0');self.assertIsNone(study.retained(self.s,self.c,self.run))
 def test_context_and_token_revalidation(self):
  for field,val in [('actor','canon_wally'),('run','b'*32),('expires',0)]:
   old=self.c['canonical_location'][field];self.c['canonical_location'][field]=val
   with self.assertRaises(ValueError):self.call()
   self.c['canonical_location'][field]=old
  p=self.call();self.c['birch_study_preview']['until']=0
  with self.assertRaises(ValueError):self.call('accept:'+p['token'])
  self.c['state'][0]=2
  with self.assertRaises(ValueError):self.call()
 def test_unknown_retained_schema_refuses(self):
  self.accept();self.db.execute("UPDATE birch_field_studies SET body='{}'")
  with self.assertRaises(ValueError):self.call()
 def test_bounded_reviewed_habitats(self):
  self.assertEqual(len(study.catalog()['species']),42)
  with self.assertRaises(ValueError):study.validate(dict(species=['MEWTWO'],days=1),'canon_birch',['birch'])
  with self.assertRaises(ValueError):study.validate(dict(species=['WURMPLE'],days=8),'canon_birch',['birch'])
  p=self.call();self.c['canonical_location']['expires']=0
  self.assertEqual(self.call('accept:'+p['token'])['mode'],'active') # The bounded live preview is the menu's context.
 def test_native_and_wire_shape(self):
  p=self.accept();wire=study.wire(p);self.assertEqual(len(wire.split()),7);self.assertEqual(wire.split()[-2:],['25','133'])
  with tempfile.TemporaryDirectory() as d:
   native=ROOT/'src/world/birch_study.inc.c'
   if not native.exists():native=ROOT/'engines/expansion-native/src/world/birch_study.inc.c'
   fixture=ROOT/'tests/native_study.c'
   if not fixture.exists():fixture=ROOT/'test/native_study.c'
   src=pathlib.Path(d)/'test.c';src.write_text(fixture.read_text().replace('../src/world/birch_study.inc.c',str(native)))
   for flag in (0,1):
    exe=pathlib.Path(d)/str(flag);subprocess.run(['cc','-std=c99','-fsanitize=undefined',f'-DEW_BIRCH_STUDIES={flag}',str(src),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
 def test_original_tutor_cannot_bypass_study(self):
  actor=types.ModuleType('studyfixture.actor_tutors');actor.MOVES={102:'Mimic',205:'Rollout'};sys.modules[actor.__name__]=actor
  cast.location=lambda key:('canon_birch','LittlerootTown_ProfessorBirchsLab')
  from studyfixture import canonical_services as services
  services.validate(self.row['tutor'],'canon_birch')
  with self.assertRaises(ValueError):services.handle(self.s,self.c,self.run,'birch','preview')
  with self.assertRaises(ValueError):services.validate(self.row['tutor'],'canon_wally')
 def test_actual_core_dispatch_and_native_wiring(self):
  from studyfixture import core_story
  handler=core_story.CoreStory.__new__(core_story.CoreStory);handler.s=self.s;self.s.peers={self.c['id']:self.c};self.c['core_story_capable']=True
  self.assertEqual(handler.handle(self.c,['CORE',self.run,'STUDY','birch','view'])['mode'],'offer')
  self.s.peers[self.c['id']]=dict(self.c)
  with self.assertRaises(ValueError):handler.handle(self.c,['CORE',self.run,'STUDY','birch','view'])
  native=ROOT/'src/world/world_core_story.c'
  if not native.exists():native=ROOT/'engines/expansion-native/src/world/world_core_story.c'
  s=native.read_text();self.assertIn('if(!BirchStudy_Line(n,t))return FALSE;sCore.pending=0;return TRUE;',s)
  self.assertIn('if(BirchStudy_Frame())return TRUE;',s);self.assertIn('BirchStudy_Update();',s)
  self.assertIn('sTutor.active=TRUE;LockPlayerFieldControls();ChooseMonForWorldTutor(TutorReturn)',s)
  self.assertIn('EW_BIRCH_STUDIES ?= 0',(ROOT/'engines/expansion.mk').read_text())
if __name__=='__main__':unittest.main()
