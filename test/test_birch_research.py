import json,pathlib,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT if (ROOT/'src/world/world_core_story.c').exists() else ROOT/'engines/expansion-native'
pkg=types.ModuleType('birch_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules['birch_fixture']=pkg
from birch_fixture import shared_research as research, canonical_cast as cast, shared_outbreaks as outbreaks, canonical_seeds as seeds
class Memory:
 def __init__(self,db):self.db=db;db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,data TEXT)')
 def append(self,kind,row):
  row=dict(row,event=kind);seq=self.db.execute('INSERT INTO events(data) VALUES(?)',(json.dumps(row),)).lastrowid;return seq
 def events(self):return [dict(json.loads(d),seq=s) for s,d in self.db.execute('SELECT * FROM events')]
class Research(unittest.TestCase):
 def setUp(self):
  db=sqlite3.connect(':memory:');self.s=types.SimpleNamespace(db=db,memory=Memory(db),revision=0,link_protocol=types.SimpleNamespace(busy=lambda who:False))
  self.c=dict(id='private-name',presence=dict(campaign_run='a'*32,state=[1,4,5,5,0,0,1],state_time=time.monotonic()))
 def test_publication_then_actual_world_opportunity(self):
  self.assertEqual(research.handle(self.s,self.c,b'D REPORT 1 3'),'D ACK 1\n')
  event=self.s.memory.events()[-1]
  self.assertTrue(cast.reaction_activity(event,'canon_birch',{}))
  self.assertTrue(cast.decision_evidence(event,'canon_birch',{}))
  self.assertNotIn('private-name',json.dumps(event));self.assertNotIn('run',event)
  self.assertEqual(cast.location('birch'),('canon_birch','LittlerootTown_ProfessorBirchsLab'))
  self.assertIn('anonymous',seeds.profile('canon_birch')['identity'])
  # Deterministic author choice, not an automatic reaction or a live model.
  outbreaks.setup(self.s.db)
  result=outbreaks.configure(self.s,'canon_birch',{},dict(map='Route102',species='RALTS',level=5,chance=10,minutes=5))
  self.assertEqual(result['outcome'],'shared_outbreak_configured')
  line=outbreaks.line(self.s,dict(outbreak_capable=True,state=[0,17,1,1,0,0,1]))
  # Use the actual catalog identity rather than a guessed route number.
  from birch_fixture.build_catalog import catalog_maps
  pair=next(k for k,v in catalog_maps().items() if v['name']=='Route102')
  line=outbreaks.line(self.s,dict(outbreak_capable=True,state=[*pair,1,1,0,0,1]))
  self.assertTrue(line.startswith('WILD_OUTBREAK '));self.assertIn(' 5 10 ',line)
  self.assertNotIn('capture',result)
 def test_dedup_and_private_remain_private(self):
  self.assertEqual(research.catalog(self.s)['entries'],[])
  for _ in range(2):self.assertEqual(research.handle(self.s,self.c,b'D REPORT 1 3'),'D ACK 1\n')
  self.assertEqual(len(self.s.memory.events()),1)
  self.assertEqual(research.catalog(self.s)['entries'],[dict(dex=1,seen=True,caught=True)])
 def test_stale_busy_malformed(self):
  for raw in [b'D REPORT 1 xyz',b'D REPORT 2 3',b'D REPORT 1 ',b'D REPORT 1 '+b'f'*514]:self.assertEqual(research.handle(self.s,self.c,raw),'D ERROR 1\n')
  self.c['presence']['state_time']-=10
  self.assertEqual(research.handle(self.s,self.c,b'D REPORT 1 3'),'D ERROR 1\n')
  self.c['presence']['state_time']=time.monotonic();self.s.link_protocol.busy=lambda who:True
  self.assertEqual(research.handle(self.s,self.c,b'D REPORT 1 3'),'D ERROR 1\n')
  self.assertEqual(self.s.memory.events(),[])
 def test_relevance_rejects_invented_and_other_actor(self):
  e=dict(event='shared_research_published',basis=research.BASIS,publication='explicit_current_dex_snapshot',entries=[[1,1]])
  self.assertTrue(research.relevant(e,'canon_birch'))
  self.assertFalse(research.relevant(e,'canon_steven'))
  for patch in [dict(entries=[]),dict(entries=[[1,1],[1,2]]),dict(entries=[[True,1]]),dict(entries=[[1,0]]),dict(publication='automatic')]:self.assertFalse(research.relevant(dict(e,**patch),'canon_birch'))
 def test_restart_no_report_replay(self):
  research.handle(self.s,self.c,b'D REPORT 1 3')
  with tempfile.TemporaryDirectory() as d:
   copy=sqlite3.connect(d+'/world.db');self.s.db.backup(copy);copy.close()
   db=sqlite3.connect(d+'/world.db');restored=types.SimpleNamespace(db=db)
   self.assertEqual(research.catalog(restored)['entries'][0]['dex'],1)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1);db.close()
 def test_native_story_tail_and_default(self):
  text=(NATIVE/'data/scripts/prof_birch.inc').read_text()
  off=subprocess.run(['cpp','-P','-x','c','-DEW_BIRCH_RESEARCH=0','-DPORTABLE'],input=text,text=True,capture_output=True,check=True).stdout
  base=(pathlib.Path(__file__).parent/'prof_birch_base.inc').read_text()
  original=subprocess.run(['cpp','-P','-x','c'],input=base,text=True,capture_output=True,check=True).stdout
  self.assertEqual(off.strip(),original.strip())
  self.assertEqual(text.count('\tcall ProfBirch_EventScript_WorldResearch'),2)
  self.assertIn('call ProfBirch_EventScript_RatePokedex\n#if',text)
  native=(NATIVE/'src/world/world_core_story.c').read_text()
  self.assertIn('mapGroup!=1 || gSaveBlock1Ptr->location.mapNum!=4',native)
  self.assertIn('!FlagGet(FLAG_RECEIVED_POKEDEX_FROM_BIRCH)',native)
  self.assertIn('#define EW_BIRCH_RESEARCH 0',native)
if __name__=='__main__':unittest.main()
