"""Production response and private-memory functions, with bounded world doubles."""
import ast,hashlib,importlib.util,json,re,sqlite3,sys,time,types,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class Granite(unittest.TestCase):
 def setUp(self):
  self.package='granite_fixture';pkg=types.ModuleType(self.package);pkg.__path__=[];sys.modules[self.package]=pkg
  self.mods={}
  for name in ('canonical_cast','canonical_memory'):
   spec=importlib.util.spec_from_file_location(self.package+'.'+name,ROOT/'world'/f'{name}.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);self.mods[name]=m
  self.cast=self.mods['canonical_cast'];self.mem=self.mods['canonical_memory']
  def module(name,**kw):
   m=types.ModuleType(self.package+'.'+name);m.__dict__.update(kw);sys.modules[m.__name__]=m
  module('canonical_activity_projects',visible=lambda s,i,r:r)
  def forbidden(*a,**k):raise AssertionError('Late private reflection consulted')
  module('canonical_reflection',private_reply=forbidden,ready_record=forbidden,acknowledge_perspective=lambda *a:None)
  self.row=dict(version=1,dialogue='Late Mossdeep reply.',first_meeting='These stones keep surprising me.',goal='Study stones',evidence=[1],companion='steven_wild_once',council={'question':'Later choice'})
  self.cast.records=lambda state:{'canon_steven':self.row}
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
  self.db.executescript('CREATE TABLE canonical_memory_optin(trainer,actor); CREATE TABLE canonical_encounters(trainer,run,actor,talks,updated,version,goal,text,UNIQUE(trainer,run,actor)); CREATE TABLE canonical_perspectives(trainer,actor,run);')
  self.conn=dict(id='local',core_active_run='a'*32)
  def place(c,name):
   if name!='GraniteCave_StevensRoom' or c.get('wrong_place'):raise ValueError('wrong location')
  self.s=types.SimpleNamespace(db=self.db,module_state={},memory=types.SimpleNamespace(world_id='world'),core_story=types.SimpleNamespace(_place=place))
 def response(self):return self.cast.response(self.s,self.conn,'a'*32,'steven_gc')
 def test_optional_early_text_never_falls_back_to_late_features(self):
  out=self.response();self.assertEqual(out['actor'],'canon_steven');self.assertEqual(out['briefing'],self.row['first_meeting']);self.assertEqual(out['objective'],'');self.assertNotIn('cast_seen_pending',self.conn)
  del self.row['first_meeting']
  with self.assertRaises(ValueError):self.response()
  self.conn['wrong_place']=True
  with self.assertRaises(ValueError):self.response()
 def test_opted_in_ack_records_same_actor_without_progress_or_reflection(self):
  self.db.execute('INSERT INTO canonical_memory_optin VALUES(?,?)',('local','canon_steven'))
  out=self.response();self.assertEqual(self.db.execute('SELECT count(*) FROM canonical_encounters').fetchone()[0],0)
  self.assertIsNone(self.conn['cast_seen_pending']['reflection'])
  with self.assertRaises(ValueError):self.mem.acknowledge(self.s,self.conn,'a'*32,'canon_steven',out['digest'],map_name='MossdeepCity_StevensHouse')
  self.mem.acknowledge(self.s,self.conn,'a'*32,'canon_steven',out['digest'],map_name='GraniteCave_StevensRoom')
  row=self.db.execute('SELECT actor,talks,text FROM canonical_encounters').fetchone();self.assertEqual(row,('canon_steven',1,self.row['first_meeting']))
  with self.assertRaises(ValueError):self.mem.acknowledge(self.s,self.conn,'a'*32,'canon_steven',out['digest'],map_name='GraniteCave_StevensRoom')
  self.assertEqual(self.db.execute("SELECT name FROM sqlite_master WHERE name='core_story_progress'").fetchall(),[])
 def test_actual_first_meeting_validation(self):
  tree=ast.parse((ROOT/'world/canonical_cast.py').read_text());record=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='records')
  loop=next(n for n in record.body if isinstance(n,ast.For))
  node=next(n for n in loop.body if isinstance(n,ast.If) and "row.get('first_meeting')" in ast.unparse(n.test))
  code=compile(ast.Module(body=[node],type_ignores=[]),'<production first-meeting validation>','exec')
  for identity,text,valid in [('canon_steven','Stone studies.',True),('canon_wally','Stone studies.',False),('canon_steven','x'*201,False),('canon_steven','bad\ntext',False)]:
   ns=dict(identity=identity,row={'first_meeting':text},re=re,native_text=self.cast.native_text)
   if valid:exec(code,ns)
   else:
    with self.assertRaises(ValueError):exec(code,ns)
if __name__=='__main__':unittest.main()
