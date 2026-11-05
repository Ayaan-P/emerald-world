"""Verify the Makefile's real preprocessor flags, not merely compiler flags."""
from pathlib import Path
import re
import shlex
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]

class CaveBuildFlags(unittest.TestCase):
    def test_feature_switches_reach_preprocessor(self):
        target='cave-test-flags:;@printf "%s\\n" "$(CPPFLAGS)"'
        for ready,auto in ((0,0),(1,0),(1,1)):
            with self.subTest(ready=ready,auto=auto):
                args=['make','-s','--no-print-directory','--eval',target,'cave-test-flags',
                      'NODEP=1','SETUP_PREREQS=0','PORTABLE=1','MODERN=1',f'GENERATED_MAP_READY={ready}',f'GENERATED_MAP_AUTOTILE={auto}']
                flags=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(flags.returncode,0,flags.stderr)
                cpp=subprocess.run(['cpp',*shlex.split(flags.stdout),'-dM','-'],cwd=ROOT,
                    input='#include "platform/generated_map.h"\n',capture_output=True,text=True)
                self.assertEqual(cpp.returncode,0,cpp.stderr)
                self.assertRegex(cpp.stdout,rf'(?m)^#define GENERATED_MAP_READY {ready}$')
                self.assertRegex(cpp.stdout,rf'(?m)^#define GENERATED_MAP_AUTOTILE {auto}$')

if __name__=='__main__':unittest.main()
