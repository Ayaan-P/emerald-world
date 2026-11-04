"""C regressions using real headers and extracted engine manager functions.

Parent runs these on the integrated candidate. No game, save, or display opens.
The sprite fixture stubs resource acquisition, not allocation search or OAM emit.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


def compile_fixture(test, source):
    with tempfile.TemporaryDirectory(prefix='emerald-runtime-capacity-') as tmp:
        cfile, binary = Path(tmp) / 'capacity.c', Path(tmp) / 'capacity'
        cfile.write_text(source)
        compiler = shutil.which('cc')
        if compiler is None:
            test.fail('C compiler required')
            return
        result = subprocess.run([
            compiler, '-std=gnu99', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-function', '-DPORTABLE', '-DVER_64BIT', '-DUBFIX',
            '-I' + str(ROOT / 'include'), '-I' + str(ROOT), str(cfile),
            '-o', str(binary)], capture_output=True, text=True)
        test.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(binary)], capture_output=True, text=True, cwd=tmp)
        test.assertEqual(result.returncode, 0, result.stderr)


class NativeRuntimePools(unittest.TestCase):
    def test_runtime_object_allocator_searches_high_slots_and_retains_duplicate_check(self):
        source = (ROOT / 'src/event_object_movement.c').read_text()
        bodies = ''.join(function(source, name) for name in (
            'GetFirstInactiveObjectEventId', 'GetAvailableObjectEventId',
            'GetObjectEventIdByLocalIdAndMapInternal'))
        compile_fixture(self, r'''
#include "global.h"
#include <assert.h>
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
''' + bodies + r'''
int main(void) {
    u8 slot;
    for (unsigned i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        assert(GetFirstInactiveObjectEventId() == i);
        assert(!GetAvailableObjectEventId(i + 1, 9, 0, &slot));
        assert(slot == i);
        gObjectEvents[i].active = TRUE;
        gObjectEvents[i].localId = i + 1;
        gObjectEvents[i].mapNum = 9;
    }
    assert(GetFirstInactiveObjectEventId() == OBJECT_EVENTS_COUNT);
    assert(GetAvailableObjectEventId(200, 9, 0, &slot));
    assert(GetObjectEventIdByLocalIdAndMapInternal(OBJECT_EVENTS_COUNT, 9, 0)
           == OBJECT_EVENTS_COUNT - 1);
    gObjectEvents[OBJECT_EVENTS_COUNT - 2].active = FALSE;
    assert(GetAvailableObjectEventId(OBJECT_EVENTS_COUNT, 9, 0, &slot));
    assert(!GetAvailableObjectEventId(200, 9, 0, &slot));
    assert(slot == OBJECT_EVENTS_COUNT - 2);
    return 0;
}
''')

    def test_all_native_sprite_slots_animate_and_emit_oam(self):
        source = (ROOT / 'src/sprite.c').read_text()
        bodies = ''.join(function(source, name) for name in (
            'CreateSprite', 'CreateSpriteAtEnd', 'AnimateSprites',
            'AddSpriteToOamBuffer', 'AddSpritesToOamBuffer'))
        compile_fixture(self, r'''
#include "global.h"
#include "sprite.h"
#include "main.h"
#include <assert.h>
struct Sprite gSprites[MAX_SPRITES + 1];
struct Main gMain;
u8 gOamLimit = MAX_SPRITES;
static u8 sSpriteOrder[MAX_SPRITES];
const struct OamData gDummyOamData = {0};
static unsigned animated, callbacks;
static void Callback(struct Sprite *sprite) { (void)sprite; callbacks++; }
void AnimateSprite(struct Sprite *sprite) { (void)sprite; animated++; }
u8 CreateSpriteAt(u8 id, const struct SpriteTemplate *template, s16 x, s16 y, u8 subpriority) {
    (void)template; (void)x; (void)y; (void)subpriority;
    gSprites[id].inUse = TRUE;
    gSprites[id].callback = Callback;
    gSprites[id].oam.tileNum = id;
    return id;
}
bool8 AddSubspritesToOamBuffer(struct Sprite *sprite, struct OamData *dest, u8 *id) {
    (void)sprite; (void)dest; (void)id;
    assert(!"scalar sprite fixture unexpectedly requested subsprites");
    return TRUE;
}
''' + bodies + r'''
int main(void) {
    assert(MAX_SPRITES == 128);
    for (unsigned i = 0; i < MAX_SPRITES; i++) {
        assert(CreateSprite(NULL, 0, 0, 0) == i);
        sSpriteOrder[i] = i;
    }
    assert(CreateSprite(NULL, 0, 0, 0) == MAX_SPRITES);
    AnimateSprites();
    assert(animated == MAX_SPRITES && callbacks == MAX_SPRITES);
    AddSpritesToOamBuffer();
    for (unsigned i = 0; i < MAX_SPRITES; i++)
        assert(gMain.oamBuffer[i].tileNum == i);
    gSprites[MAX_SPRITES - 1].inUse = FALSE;
    assert(CreateSpriteAtEnd(NULL, 0, 0, 0) == MAX_SPRITES - 1);
    assert(CreateSpriteAtEnd(NULL, 0, 0, 0) == MAX_SPRITES);
    return 0;
}
''')

    def test_movement_ids_and_completion_above_15_and_31_do_not_touch_task_data(self):
        source = (ROOT / 'src/script_movement.c').read_text()
        state = source[source.index('static EWRAM_DATA const u8 *sMovementScripts'):
                       source.index('bool8 ScriptMovement_StartObjectMovementScript')]
        names = ('ScriptMovement_StartMoveObjects', 'ScriptMovement_TryAddNewMovement',
                 'GetMovementScriptIdFromObjectEventId', 'LoadObjectEventIdPtrFromMovementScript',
                 'SetObjectEventIdAtMovementScript', 'LoadObjectEventIdFromMovementScript',
                 'ClearMovementScriptFinished', 'SetMovementScriptFinished',
                 'IsMovementScriptFinished', 'SetMovementScript', 'GetMovementScript',
                 'ScriptMovement_AddNewMovement')
        bodies = [function(source, name) for name in names]
        prototypes = ''.join(body.split('{', 1)[0].rstrip() + ';\n' for body in bodies)
        compile_fixture(self, r'''
#include "global.h"
#include "task.h"
#include "constants/event_objects.h"
#include <assert.h>
struct Task gTasks[NUM_TASKS];
static void ScriptMovement_MoveObjects(u8 taskId) { (void)taskId; }
u8 CreateTask(TaskFunc func, u8 priority) { (void)func; (void)priority; return 0; }
''' + state + prototypes + ''.join(bodies) + r'''
int main(void) {
    const u8 script[] = {0};
    u8 id;
    memset(gTasks, 0x5a, sizeof(gTasks));
    ScriptMovement_StartMoveObjects(50);
    assert(OBJECT_EVENTS_COUNT == 64);
    for (unsigned i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        assert(!ScriptMovement_TryAddNewMovement(0, i, script));
        assert(GetMovementScriptIdFromObjectEventId(0, i) == i);
        LoadObjectEventIdFromMovementScript(0, i, &id);
        assert(id == i);
        assert(GetMovementScript(i) == script);
        assert(!IsMovementScriptFinished(0, i));
    }
    assert(ScriptMovement_TryAddNewMovement(0, OBJECT_EVENTS_COUNT, script));
    for (unsigned i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        SetMovementScriptFinished(0, i);
        assert(IsMovementScriptFinished(0, i));
    }
    ClearMovementScriptFinished(0, OBJECT_EVENTS_COUNT - 1);
    assert(!IsMovementScriptFinished(0, OBJECT_EVENTS_COUNT - 1));
    assert(IsMovementScriptFinished(0, SAVED_OBJECT_EVENTS_COUNT - 1));
    assert(IsMovementScriptFinished(0, OBJECT_EVENTS_COUNT / 2));
    for (unsigned i = 0; i < sizeof(gTasks); i++)
        assert(((u8 *)gTasks)[i] == 0x5a);
    return 0;
}
''')

    def test_persisted_struct_byte_boundary_uses_real_headers(self):
        source = (ROOT / 'src/load_save.c').read_text()
        bodies = function(source, 'SaveObjectEvents') + function(source, 'LoadObjectEvents')
        compile_fixture(self, r'''
#include "global.h"
#include <stddef.h>
#include <assert.h>
STATIC_ASSERT(sizeof(struct ObjectEvent) == 0x24, ObjectSize);
STATIC_ASSERT(offsetof(struct SaveBlock1, objectEvents) == 0xa30, ObjectsStart);
STATIC_ASSERT(sizeof(((struct SaveBlock1 *)0)->objectEvents) == 0x240, ObjectsBytes);
STATIC_ASSERT(offsetof(struct SaveBlock1, objectEventTemplates) == 0xc70, ObjectsEnd);
static struct SaveBlock1 save;
struct SaveBlock1 *gSaveBlock1Ptr = &save;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
static void WorldBridge_PrepareSave(void) {}
static bool8 ObjectEventIsPersistent(const struct ObjectEvent *objectEvent) {
    return objectEvent->active && objectEvent->isPlayer;
}
''' + bodies + r'''
int main(void) {
    memset(save.objectEventTemplates, 0xa5, sizeof(save.objectEventTemplates));
    gObjectEvents[OBJECT_EVENTS_COUNT - 1].active = TRUE;
    gObjectEvents[OBJECT_EVENTS_COUNT - 1].isPlayer = TRUE;
    SaveObjectEvents();
    assert(save.objectEvents[0].active && save.objectEvents[0].isPlayer);
    for (unsigned i = 0; i < sizeof(save.objectEventTemplates); i++)
        assert(((u8 *)save.objectEventTemplates)[i] == 0xa5);
    LoadObjectEvents();
    assert(gObjectEvents[0].isPlayer);
    assert(!gObjectEvents[OBJECT_EVENTS_COUNT - 1].active);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
