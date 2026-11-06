"""Compile the native Teleport completion seam, not a Python simulation."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class UnstuckNativeTests(unittest.TestCase):
    def test_native_spin_finishes_when_subsprite_mode_is_not_a_direction(self):
        text = Path(os.environ.get('UNSTUCK_FIELD_EFFECT_SOURCE', ROOT / 'src/field_effect.c')).read_text()
        start = text.index('static void TeleportWarpInFieldEffect_SpinGround(struct Task *task)\n{')
        end = text.index('\n}\n', start) + 3
        function = text[start:end]
        source = r'''
#include <assert.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint8_t bool8;
#define TRUE 1
#define DIR_SOUTH 1
#define DIR_NORTH 2
#define DIR_WEST 3
#define DIR_EAST 4
#define OBJECT_EVENTS_COUNT 16
struct Task { short data[16]; };
typedef void (*TaskFunc)(u8);
struct PlayerAvatar { u8 objectEventId; };
struct ObjectEvent { u8 facingDirection; };
struct PlayerAvatar gPlayerAvatar;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
static int unlocked, destroyed;
void ObjectEventTurn(struct ObjectEvent *o, u8 d) { o->facingDirection=d; }
void UnlockPlayerFieldControls(void) { unlocked++; }
void CameraObjectReset(void) {}
void UnfreezeObjectEvents(void) {}
static void Task_TeleportWarpIn(u8 id) { (void)id; }
u8 FindTaskIdByFunc(TaskFunc f) { (void)f; return 0; }
void DestroyTask(u8 id) { (void)id; destroyed++; }
bool8 WorldUnstuck_OwnsFieldInput(void) { return TRUE; }
''' + function + r'''
int main(void) {
 struct Task task={0}; task.data[1]=1; task.data[14]=0; task.data[15]=DIR_SOUTH;
 gObjectEvents[0].facingDirection=DIR_SOUTH;
 for (int i=0;i<5000 && !destroyed;i++) TeleportWarpInFieldEffect_SpinGround(&task);
 assert(unlocked==1 && destroyed==1);
 return 0;
}
'''
        # Recovery hook is tested separately; isolate the engine's spin condition.
        hook = source.find('WorldUnstuck_CompleteArrival')
        a = source.rfind('#if defined(PORTABLE)', 0, hook) if hook != -1 else -1
        if a != -1:
            b = source.index('#endif', a) + len('#endif')
            source = source[:a] + source[b:]
        with tempfile.TemporaryDirectory(prefix='unstuck-native-') as tmp:
            c, exe = Path(tmp)/'spin.c', Path(tmp)/'spin'
            c.write_text(source)
            compile_result = subprocess.run(['cc','-std=gnu99','-DPORTABLE','-DVER_64BIT','-DMODERN=1',
                '-iquote',str(ROOT/'include'),str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(compile_result.returncode,0,compile_result.stderr)
            result = subprocess.run([str(exe)],capture_output=True)
            self.assertEqual(result.returncode,0,'Teleport did not release controls in 5000 frames')

if __name__ == '__main__':
    unittest.main()
