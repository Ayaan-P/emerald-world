"""Exercise production collision and remote ownership with a small C fixture.

This is not a substitute for multiplayer native gameplay testing.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]
PREAMBLE = r'''
#include <assert.h>
#include <stddef.h>
typedef int bool8; typedef int s16; typedef unsigned char u8;
#define TRUE 1
#define FALSE 0
#define WB_REMOTES 2
#define WB_LOCALID 224
#define WB_MARKER 0x5742
#define OBJECT_EVENTS_COUNT 8
#define MAX_SPRITES 8
struct Coords { int x, y; };
struct ObjectEvent { int active, isPlayer, localId, mapGroup, mapNum, spriteId, currentElevation; struct Coords currentCoords, previousCoords; };
struct Sprite { int inUse, data[8]; };
struct Remote { char id[2]; unsigned object, sprite, group, num; };
struct { struct Remote remotes[WB_REMOTES]; } sWorld;
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
struct Sprite gSprites[MAX_SPRITES];
int inside;
int GeneratedMap_IsInside(void) { return inside; }
int AreElevationsCompatible(int a, int b) { return a == b; }
'''
MAIN = r'''
int main(void) {
    struct ObjectEvent *p=&gObjectEvents[0], *r=&gObjectEvents[1], *n=&gObjectEvents[2];
    p->active=1; p->isPlayer=1; r->active=1; r->localId=WB_LOCALID;
    r->spriteId=1; r->currentCoords.x=3; r->currentCoords.y=4;
    r->previousCoords.x=2; r->previousCoords.y=4;
    sWorld.remotes[0].id[0]='x'; sWorld.remotes[0].object=1; sWorld.remotes[0].sprite=1;
    gSprites[1].inUse=1; gSprites[1].data[0]=1; gSprites[1].data[7]=WB_MARKER;
    assert(WorldBridge_IsRemoteObject(r)); assert(!WorldBridge_IsRemoteObject(NULL));
    inside=1;
#if defined(PORTABLE) && GENERATED_MAP_READY
    assert(!DoesObjectCollideWithObjectAt(p,3,4));
    assert(!DoesObjectCollideWithObjectAt(p,2,4));
#else
    assert(DoesObjectCollideWithObjectAt(p,3,4));
#endif
    inside=0; assert(DoesObjectCollideWithObjectAt(p,3,4)); inside=1;
    n->active=1; n->currentCoords.x=3; n->currentCoords.y=4;
    assert(DoesObjectCollideWithObjectAt(p,3,4));
    n->active=0;
    assert(DoesObjectCollideWithObjectAt(n,3,4));
    gSprites[1].data[7]=0; assert(!WorldBridge_IsRemoteObject(r));
    assert(DoesObjectCollideWithObjectAt(p,3,4));
    return 0;
}
'''

class CaveCollisionTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_production_collision_and_owned_identity(self):
        movement = (ROOT / 'src/event_object_movement.c').read_text()
        bridge = (ROOT / 'src/platform/world_bridge.c').read_text()
        source = PREAMBLE + function(bridge, 'Owned') + function(bridge, 'WorldBridge_IsRemoteObject') + function(movement, 'DoesObjectCollideWithObjectAt') + MAIN
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.c').write_text(source)
            for flags in (['-DPORTABLE', '-DGENERATED_MAP_READY=1'], ['-DPORTABLE', '-DGENERATED_MAP_READY=0'], []):
                subprocess.run(['cc', '-std=c99', '-Wall', '-Werror', *flags, str(path / 'test.c'), '-o', str(path / 'test')], check=True)
                subprocess.run([str(path / 'test')], check=True)

if __name__ == '__main__': unittest.main()
