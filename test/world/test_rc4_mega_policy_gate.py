"""Keep release Mega policy closed, permit explicitly opted-in proof builds."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class MegaPolicyGateTests(unittest.TestCase):
    def test_native_policy_tracks_the_compile_time_feature_gate(self):
        source = r'''
#include "platform/world_rules.h"
#include <assert.h>
int main(void) {
    const char *wire = "1:8:0000000000000000000000000000000000000000000000000000000000000000";
    assert(WorldRules_Init(wire) == MEGA_FEATURE_READY);
    assert(WorldRules_Enabled(WORLD_RULE_MEGA_EVOLUTION) == MEGA_FEATURE_READY);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rc4-mega-policy-') as directory:
            root = Path(directory)
            c = root/'probe.c'
            c.write_text(source)
            for enabled in (0, 1):
                with self.subTest(enabled=enabled):
                    exe = root/f'gate-{enabled}'
                    result = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-DPORTABLE', '-DVER_64BIT', f'-DMEGA_FEATURE_READY={enabled}', '-Iinclude', str(c), 'src/platform/world_rules.c', '-o', str(exe)], cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(exe)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
