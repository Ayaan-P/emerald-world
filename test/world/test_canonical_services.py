from pathlib import Path
import importlib.util,sys,types,time,unittest
ROOT=Path(__file__).resolve().parents[2]
class Services(unittest.TestCase):
 def setUp(self):
  name='service_fixture';pkg=types.ModuleType(name);pkg.__path__=[str(ROOT/'world')];sys.modules[name]=pkg
  moves=types.ModuleType(name+'.actor_tutors');moves.MOVES={164:'Substitute'};sys.modules[moves.__name__]=moves
  cast=types.ModuleType(name+'.canonical_cast')
  cast.location=lambda key:('canon_steven','GraniteCave_StevensRoom') if key=='steven_gc' else (None,None)
  self.row=dict(version=2,tutor=dict(move=164,appearances=['steven_gc']))
  cast.records=lambda s:{'canon_steven':self.row};sys.modules[cast.__name__]=cast
  spec=importlib.util.spec_from_file_location(name+'.canonical_services',ROOT/'world/canonical_services.py');self.m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=self.m;spec.loader.exec_module(self.m)
  self.conn=dict(core_active_run='run',state=[0]*6+[1],canonical_location=dict(actor='canon_steven',map='GraniteCave_StevensRoom',run='run',version=2,expires=time.monotonic()+120))
  def place(c,m):
   if c.get('away'):raise ValueError('moved')
  self.s=types.SimpleNamespace(module_state={},core_story=types.SimpleNamespace(_place=place))
 def call(self,guard='preview',run='run'):return self.m.handle(self.s,self.conn,run,'steven_gc',guard)
 def test_preview_confirm_is_single_use_and_no_outcome(self):
  p=self.call();self.assertEqual(p['tutor_move'],164);self.assertEqual(self.call(p['tutor_token']),dict(tutor_move=164,tutor_token='accepted'))
  with self.assertRaises(ValueError):self.call(p['tutor_token'])
 def test_revoked_changed_moved_expired_wrong_save_refused(self):
  for case in ['revoke','version','move','map','expiry','run','busy']:
   self.setUp();p=self.call()
   if case=='revoke':self.row.pop('tutor')
   if case=='version':self.row['version']+=1
   if case=='move':self.row['tutor']['move']=38
   if case=='map':self.conn['away']=True
   if case=='expiry':self.conn['canonical_tutor_preview']['until']=0
   if case=='busy':self.conn['state'][6]=0
   with self.assertRaises(ValueError):self.call(p['tutor_token'],run='other' if case=='run' else 'run')
 def test_authoring_bounds_and_no_automatic_service(self):
  self.m.validate(self.row['tutor'],'canon_steven');self.m.validate(None,'canon_steven');self.assertEqual(self.m.hint({},'steven_gc'),'')
  for service in [dict(move=1,appearances=['steven_gc']),dict(move=164,appearances=['briney']),dict(move=164,appearances=['steven_gc','steven_gc'])]:
   with self.assertRaises(ValueError):self.m.validate(service,'canon_steven')
if __name__=='__main__':unittest.main()
