"""Exercise the actual native assembler-preprocessing recipe's CPP flags."""
from pathlib import Path
import re
import shlex
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]

class NativeAssemblyConstants(unittest.TestCase):
    def test_native_cpp_exposes_items_without_rewriting_assembler_guards(self):
        result = subprocess.run(['make', '--no-print-directory', '-n', 'linux', '-W', 'data/event_scripts.s', 'WERROR=1', 'CFLAGS=-g'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        pipeline = next(line for line in result.stdout.splitlines() if line.startswith('tools/preproc/preproc data/event_scripts.s '))
        cpp = shlex.split(pipeline.split('|')[1])
        fixture = '#include "constants/items.h"\n#include "constants/moves.h"\n.ifdef PORTABLE\n.short ITEM_MEGA_RING\n.short MOVE_MOONBLAST\n.endif\n'
        result = subprocess.run(cpp, input=fixture, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r'\.ifdef\s+PORTABLE\b')
        self.assertRegex(result.stdout, r'\.short\s+393\b')
        self.assertRegex(result.stdout, r'\.short\s+355\b')
