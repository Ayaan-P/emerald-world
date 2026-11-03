"""Full-tick gate placement plus compiled production gate helper behavior."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeFrameGateTests(unittest.TestCase):
    def test_gameplay_and_headless_wait_before_vblank(self):
        source = (ROOT/'src/platform/sdl2.c').read_text()
        main = source.split('int main(int argc, char **argv)',1)[1].split('static void ReadSaveFile(',1)[0]
        gate = main.index('if (!BeginNativeFrame(FALSE))')
        self.assertLess(gate, main.index('WorldBootstrapFrame();'))
        self.assertLess(gate, main.index('PlayerControl_BeforeFrame();'))
        self.assertLess(gate, main.index('ENTER_VBLANK();'))
        self.assertIn('accumulator = 0;', main[gate:gate+240])
        self.assertIn('NativeLink_AfterFrame();', main)
        headless = source.split('static int RunTestMode(void)\n{',1)[1]
        self.assertLess(headless.index('while (!BeginNativeFrame(TRUE))'), headless.index('ENTER_VBLANK();'))
        self.assertIn('NativeLink_AfterFrame();', headless)
        self.assertIn('LinkTransport_Close();', headless)

    def test_compiled_gate_pumps_transport_and_only_grants_committed_tick(self):
        source = (ROOT/'src/platform/sdl2.c').read_text()
        self.assertIn('static bool BeginNativeFrame(bool8 headless)\n{', source)
        helper = 'static bool BeginNativeFrame(bool8 headless)\n{' + source.split(
            'static bool BeginNativeFrame(bool8 headless)\n{',1)[1].split('\n}',1)[0] + '\n}'
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('C compiler unavailable')
        program = '''#include <stdbool.h>
#include <assert.h>
#include <stdint.h>
typedef unsigned char bool8;
static uint16_t gSendCmd[8];
static int stage, committed;
static void WorldBridge_Poll(bool8 h) { assert(stage==0); stage=1; (void)h; }
static void LinkTransport_Pump(void) { assert(stage==1); stage=2; }
static int NativeLink_BeforeFrame(const uint16_t *p) {
 assert(stage==2 && p==gSendCmd); stage=3; return committed;
}
''' + helper + '''
int main(void) {
 assert(!BeginNativeFrame(0)); assert(stage==3);
 stage=0; committed=1; assert(BeginNativeFrame(1)); assert(stage==3);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='native-gate-') as tmp:
            c = Path(tmp)/'gate.c'
            exe = Path(tmp)/'gate'
            c.write_text(program)
            result = subprocess.run([compiler,'-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            subprocess.run([str(exe)],check=True)
