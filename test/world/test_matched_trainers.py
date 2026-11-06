"""Exercise actual bridge reconciliation and palette compatibility in C fixtures."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]

class MatchedTrainers(unittest.TestCase):
    def test_palette_match_and_remote_reconciliation(self):
        bridge = (ROOT/'src/platform/world_bridge.c').read_text()
        movement = (ROOT/'src/event_object_movement.c').read_text()
        prior = (ROOT/'test/world/test_presence_reconcile.py').read_text()
        fixture = prior.split("        fixture = r'''", 1)[1].split("'''", 1)[0]
        fixture = fixture.replace('#define UBFIX 1', '#define UBFIX 1\n#define WORLD_EXTENDED_OBJECTS 1\n#define WORLD_MATCHED_TRAINERS 1\n#define PALSLOT_PLAYER 0')
        fixture = fixture.replace('static struct {int paletteSlot,inanimate;} graphics[NUM_OBJ_EVENT_GFX];',
                                  'struct ObjectEventGraphicsInfo {int paletteSlot,inanimate,paletteTag;};\nstatic struct ObjectEventGraphicsInfo graphics[NUM_OBJ_EVENT_GFX];\nstatic struct {u8 objectEventId;} gPlayerAvatar;')
        fixture += '\n#define SpawnWorldObjectEventParameterized SpawnSpecialObjectEventParameterized\n'
        fixture += r'''
#define OBJ_EVENT_GFX_BRENDAN_NORMAL 0
#define OBJ_EVENT_GFX_BRENDAN_MACH_BIKE 1
#define OBJ_EVENT_GFX_BRENDAN_ACRO_BIKE 2
#define OBJ_EVENT_GFX_MAY_NORMAL 3
#define OBJ_EVENT_GFX_MAY_MACH_BIKE 4
#define OBJ_EVENT_GFX_MAY_ACRO_BIKE 5
'''
        fixture += function(movement, 'WorldPlayerPaletteCompatible')
        fixture += ''.join(function(bridge, name) for name in ('Owned', 'RemoveRemote', 'NativeNpcAt', 'SelectPeers', 'SyncEngine'))
        fixture += r'''
int main(void) {
 struct Peer *p=&sWorld.live.peers[0];
 gPlayerAvatar.objectEventId=0;
 gObjectEvents[0].active=1;gObjectEvents[0].isPlayer=1;gObjectEvents[0].graphicsId=1;
 graphics[1].paletteSlot=PALSLOT_PLAYER;graphics[1].paletteTag=42;
 graphics[2].paletteSlot=PALSLOT_PLAYER;graphics[2].paletteTag=42;
 graphics[3].paletteSlot=PALSLOT_PLAYER;graphics[3].paletteTag=43;
 graphics[7].paletteSlot=PALSLOT_NPC_1;
 if (!WorldPlayerPaletteCompatible(2) || WorldPlayerPaletteCompatible(3) || WorldPlayerPaletteCompatible(255)) return 1;
 graphics[2].inanimate=1;if (WorldPlayerPaletteCompatible(2)) return 2;graphics[2].inanimate=0;
 gObjectEvents[0].isPlayer=0;if (WorldPlayerPaletteCompatible(2)) return 3;gObjectEvents[0].isPlayer=1;
 sWorld.tilesLive=1;sWorld.live.peerCount=1;strcpy(p->id,"peer");p->x=12;p->y=12;p->ready=1;p->gfx=2;
 SyncEngine(); if (!Owned(0) || gObjectEvents[sWorld.remotes[0].object].graphicsId!=2) return 4;
 p->gfx=3;SyncEngine();if (!Owned(0)||gObjectEvents[sWorld.remotes[0].object].graphicsId!=7) return 5;
 p->gfx=2;SyncEngine();if (!Owned(0)||gObjectEvents[sWorld.remotes[0].object].graphicsId!=2) return 6;
 graphics[1].paletteTag=43;SyncEngine();if (!Owned(0)||gObjectEvents[sWorld.remotes[0].object].graphicsId!=7) return 7;
 p->gfx=3;SyncEngine();if (!Owned(0)||gObjectEvents[sWorld.remotes[0].object].graphicsId!=3) return 8;
 puts("matching palettes use trainer graphics; mismatches fall back");return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c, exe = Path(tmp)/'test.c', Path(tmp)/'test'
            c.write_text(fixture)
            for flags in ([], ['-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie']):
                r=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',*flags,str(c),'-o',str(exe)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
                r=subprocess.run([str(exe)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn('mismatches fall back',r.stdout)

    def test_actual_spawn_never_overwrites_local_palette(self):
        movement = (ROOT/'src/event_object_movement.c').read_text()
        fixture = r"""
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16; typedef u8 bool8;
#define PORTABLE 1
#define WORLD_EXTENDED_OBJECTS 1
#define WORLD_MATCHED_TRAINERS 1
#define TRUE 1
#define FALSE 0
#define OBJECT_EVENTS_COUNT 8
#define NUM_OBJ_EVENT_GFX 8
#define PALSLOT_PLAYER 0
#define PALSLOT_NPC_SPECIAL 10
#define MOVEMENT_TYPE_INVISIBLE 3
#define MAX_SPRITES 8
#define TAG_NONE 0xffff
struct Coords {s16 x,y;};
struct ObjectEvent {u8 active,isPlayer,graphicsId,movementType,invisible,spriteId,inanimate,facingDirection,previousElevation;struct Coords currentCoords;};
struct ObjectEventTemplate {int dummy;};
struct SpriteTemplate {u16 paletteTag;};
struct Sprite {s16 x,y,centerToCornerVecX,centerToCornerVecY;struct {u8 paletteNum;} oam;u8 coordOffsetEnabled,sObjEventId;};
struct ObjectEventGraphicsInfo {u8 inanimate,paletteSlot,width,height;u16 paletteTag;};
static struct ObjectEvent gObjectEvents[8];static struct Sprite gSprites[8];
static struct ObjectEventGraphicsInfo graphics[8];static struct {u8 objectEventId;} gPlayerAvatar;
static int sWorldObjectAllocation, loads, special, patches, failCreate;
static const struct ObjectEventGraphicsInfo *GetObjectEventGraphicsInfo(u8 id){return &graphics[id];}
static u8 InitObjectEventStateFromTemplate(const struct ObjectEventTemplate *t,u8 n,u8 g){(void)t;(void)n;(void)g;gObjectEvents[1].active=1;return 1;}
static void LoadPlayerObjectReflectionPalette(u16 t,u8 s){(void)t;(void)s;loads++;}
static void LoadSpecialObjectReflectionPalette(u16 t,u8 s){(void)t;(void)s;special++;}
static void _PatchObjectPalette(u16 t,u8 s){(void)t;(void)s;patches++;}
static u8 CreateSprite(struct SpriteTemplate *t,int x,int y,int p){(void)t;(void)x;(void)y;(void)p;return failCreate?MAX_SPRITES:1;}
static void GetMapCoordsFromSpritePos(int x,int y,s16 *a,s16 *b){*a=x;*b=y;}
static int GetFaceDirectionAnimNum(int d){return d;}
static void StartSpriteAnim(struct Sprite *s,int n){(void)s;(void)n;}
static void SetObjectSubpriorityByElevation(int e,struct Sprite *s,int v){(void)e;(void)s;(void)v;}
static void UpdateObjectEventVisibility(struct ObjectEvent *o,struct Sprite *s){(void)o;(void)s;}
"""
        fixture += r'''
#define OBJ_EVENT_GFX_BRENDAN_NORMAL 0
#define OBJ_EVENT_GFX_BRENDAN_MACH_BIKE 1
#define OBJ_EVENT_GFX_BRENDAN_ACRO_BIKE 2
#define OBJ_EVENT_GFX_MAY_NORMAL 3
#define OBJ_EVENT_GFX_MAY_MACH_BIKE 4
#define OBJ_EVENT_GFX_MAY_ACRO_BIKE 5
'''
        fixture += function(movement,'WorldPlayerPaletteCompatible')
        fixture += function(movement,'TrySetupObjectEventSprite')
        fixture += r"""
int main(void) {
 struct ObjectEventTemplate t={0};struct SpriteTemplate st={0};
 gObjectEvents[0].active=1;gObjectEvents[0].isPlayer=1;gObjectEvents[0].graphicsId=0;
 graphics[0].paletteTag=1;graphics[1].paletteTag=1;graphics[2].paletteTag=2;
 graphics[0].paletteSlot=graphics[1].paletteSlot=graphics[2].paletteSlot=PALSLOT_PLAYER;
 gObjectEvents[1].graphicsId=1;sWorldObjectAllocation=1;
 if(TrySetupObjectEventSprite(&t,&st,0,0,0,0)!=1 || loads || gSprites[1].oam.paletteNum!=PALSLOT_PLAYER) return 1;
 gObjectEvents[1].graphicsId=2;
 if(TrySetupObjectEventSprite(&t,&st,0,0,0,0)!=OBJECT_EVENTS_COUNT || loads || gObjectEvents[1].active) return 2;
 sWorldObjectAllocation=0;
 if(TrySetupObjectEventSprite(&t,&st,0,0,0,0)!=1 || loads!=1) return 3;
 sWorldObjectAllocation=1;gObjectEvents[1].graphicsId=1;failCreate=1;
 if(TrySetupObjectEventSprite(&t,&st,0,0,0,0)!=OBJECT_EVENTS_COUNT || loads!=1 || gObjectEvents[1].active) return 4;
 return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            c, exe = Path(tmp)/'spawn.c', Path(tmp)/'spawn'
            c.write_text(fixture)
            r=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)

if __name__ == '__main__': unittest.main()
