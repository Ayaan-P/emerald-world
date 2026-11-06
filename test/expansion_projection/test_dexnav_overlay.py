import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('patch_dexnav',Path(__file__).resolve().parents[2]/'scripts/patch_expansion_dexnav.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class DexNavOverlay(unittest.TestCase):
 def test_config_opt_in_and_pinned_vars(self):
  source='\n'.join(['#define DEXNAV_ENABLED                FALSE','#define DN_FLAG_SEARCHING             0','#define DN_FLAG_DEXNAV_GET            0','#define DN_FLAG_DETECTOR_MODE         0','#define DN_VAR_SPECIES                0','#define DN_VAR_STEP_COUNTER           0'])
  out=mod.patch_config(source)
  self.assertIn('DN_VAR_SPECIES                0x40F7',out)
  self.assertIn('DN_FLAG_DEXNAV_GET            0x4007',out)
  with self.assertRaises(ValueError):mod.patch_config(source.replace('DN_VAR_SPECIES                0','DN_VAR_SPECIES                9'))
 def test_source_guards_all_entrypoints(self):
  source='#include "global.h"\n'+'\n'.join(x+'\n{' for x in ('bool32 TryStartDexNavSearch(void)','bool32 TryFindHiddenPokemon(void)','bool32 OnStep_DexNavSearch(void)','u32 CalculateDexNavShinyRolls(void)','void ResetDexNavSearch(void)','void IncrementDexNavChain(void)','void TryIncrementSpeciesSearchLevel()'))
  out=mod.patch_source(source)
  self.assertEqual(out.count('if (!ExpansionDexNav_Enabled())'),7)
  with self.assertRaises(ValueError):mod.patch_source(source.replace('void ResetDexNavSearch(void)','void renamed(void)'))
