"""Build admission for experimental dynamic-NPC co-op, never a linked playtest."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
class NpcTagBattles(unittest.TestCase):
 def test_release_builder_refuses_experiment(self):
  p=subprocess.run([sys.executable,str(ROOT/'scripts/build_expansion.py'),'--experimental-npc-coop'],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0)
  self.assertIn('--experimental-npc-coop requires --development',p.stderr)
 def test_build_option_reaches_make_and_defaults_off(self):
  source=(ROOT/'scripts/build_expansion.py').read_text()
  self.assertIn('WORLD_CHARACTER_COOP_EXPERIMENT={int(args.experimental_npc_coop)}',source)
  self.assertIn('WORLD_CHARACTER_COOP_EXPERIMENT ?= 0',(ROOT/'engines/expansion.mk').read_text())
 def test_actual_native_component_suite_when_source_available(self):
  native=Path(os.environ.get('EW_TAG_NATIVE_SOURCE',ROOT.parent/'native-npc-tag-battles')).resolve()
  if not (native/'tests/test_dynamic_coop.py').is_file(): self.skipTest('paired native source not available')
  p=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(native/'tests'),'-v'],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
