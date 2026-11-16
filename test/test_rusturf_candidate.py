"""Build option contract only; no native binary or actual save is used."""
import ast,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Candidate(unittest.TestCase):
 def test_recovery_requires_explicit_complete_development_cohort(self):
  for flags in ([],['--development'],['--development','--regional-state']):
   r=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-rusturf-recovery',*flags],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0)
   self.assertIn('requires --development --regional-state --kanto-content',r.stderr)
 def test_default_off_and_same_abi_reference_flags(self):
  make=(ROOT/'engines/expansion.mk').read_text();source=(ROOT/'scripts/build_expansion.py').read_text()
  for flag in ('EW_RUSTURF_RECOVERY','EW_REGIONAL_BADGES','EW_REGIONAL_COMPLETION','EW_ROUTE5_CUSTODY','EW_KANTO_REMATCHES','EW_REGIONAL_STARTERS'):
   self.assertIn(flag+' ?= 0',make)
   self.assertIn('-D'+flag+'=$('+flag+')',make[:make.index('include Makefile.native')])
   self.assertIn(flag,source)
  tree=ast.parse(source)
  gitlink=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD:engines/expansion-native'],text=True).strip()
  self.assertIn("PIN = '"+gitlink+"'",source)
  option=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='--experimental-rusturf-recovery')
  self.assertFalse(any(k.arg=='default' and isinstance(k.value,ast.Constant) and k.value.value for k in option.keywords))
  self.assertIn("version_suffix: str = 'rc13'",source)
 def test_recovery_reader_flags_are_not_overridden_by_default_options(self):
  import types
  tree=ast.parse((ROOT/'scripts/build_expansion.py').read_text())
  main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
  command=next(n for n in main.body if isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id=='command' and isinstance(n.value,ast.List) and any(isinstance(x,ast.Constant) and x.value=='native' for x in n.value.elts))
  options={n.attr:False for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='args'}
  for recovery in (False,True):
   options.update(experimental_rusturf_recovery=recovery,jobs=1)
   values=eval(compile(ast.Expression(command.value),'<make command>','eval'),dict(args=types.SimpleNamespace(**options),ROOT=ROOT,regional_state=1,kanto_content=1,map_version='combined',RELEASE_CONFIG=types.SimpleNamespace(map_version='combined',generated_world_regions=0,version_suffix='rc13'),compiler='gcc',head='a'*40))
   for flag in ('EW_REGIONAL_BADGES','EW_REGIONAL_COMPLETION','EW_ROUTE5_CUSTODY','EW_KANTO_REMATCHES','EW_REGIONAL_STARTERS'):
    self.assertEqual([v for v in values if v.startswith(flag+'=')],[flag+'='+str(int(recovery))])
if __name__=='__main__':unittest.main()
