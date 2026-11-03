"""Compile the production field reconciler with explicit engine allocation fixtures.

This checks reconciliation, not SDL rendering or a native multiplayer playthrough.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


class PresenceReconcile(unittest.TestCase):
    def test_graphics_replacement_has_no_missing_presence_frame(self):
        source = (ROOT/'src/platform/world_bridge.c').read_text()
        fixture = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define WB_REMOTES 4
#define WB_TILES 4
#define OBJECT_EVENTS_COUNT 8
#define MAX_SPRITES 16
#define MAP_OFFSET 7
#define WB_LOCALID 224
#define WB_MARKER 0x5742
#define OBJ_EVENT_GFX_BOY_1 7
#define NUM_OBJ_EVENT_GFX 16
#define PALSLOT_NPC_1 2
#define PALSLOT_NPC_4 5
#define MOVEMENT_TYPE_NONE 0
#define MAPGRID_IMPASSABLE 0xC00
struct Coords {int x,y;};
struct ObjectEvent {u8 active,isPlayer,localId,mapGroup,mapNum,spriteId,graphicsId;
 struct Coords currentCoords,initialCoords;u8 currentElevation,previousElevation,facingDirection;};
struct Peer {char id[26],text[58];unsigned group,num,x,y,facing,gfx,ready;};
struct Remote {char id[26];u8 object,sprite,group,num;};
struct Tile {unsigned group,num,x,y,metatile,collision;};
struct Applied {struct Tile tile;u16 original,raw;};
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
struct {int inUse,data[8];} gSprites[16];
struct {unsigned objectEventCount;} events;
struct {void *mapLayout;typeof(events) *events;} gMapHeader={0,&events};
struct {void *map;} gBackupMapLayout;
struct Save {struct {int mapGroup,mapNum;} location;
 struct {u8 localId;} objectEventTemplates[8];} save,*gSaveBlock1Ptr=&save;
struct {int active;} gPaletteFade;
static struct {int paletteSlot,inanimate;} graphics[NUM_OBJ_EVENT_GFX];
static struct {int dialogueActive,tilesLive,group,num;void *layout,*grid;
 unsigned appliedCount,restoredCount,generation,appliedGeneration;
 struct {unsigned peerCount,tileCount;struct Peer peers[WB_REMOTES];struct Tile tiles[WB_TILES];} live;
 struct Remote remotes[WB_REMOTES];struct Applied applied[WB_TILES];} sWorld;
static int removed,spawned,failSpawn,overworld=1;
static bool8 Overworld(void) {return overworld;}
static bool8 ScriptContext_IsEnabled(void) {return FALSE;}
static bool8 ArePlayerFieldControlsLocked(void) {return FALSE;}
static void RestoreTiles(void) {}
static bool8 SameGrid(void) {return TRUE;}
static bool8 Owned(unsigned i);
static void RemoveRemote(unsigned i) {struct Remote *r=&sWorld.remotes[i];
 if (Owned(i)) {removed++;gObjectEvents[r->object].active=FALSE;gSprites[r->sprite].inUse=FALSE;}
 memset(r,0,sizeof(*r));}
static bool8 GridCoords(unsigned x,unsigned y) {return x<30 && y<30;}

static typeof(graphics[0]) *GetObjectEventGraphicsInfo(unsigned id) {return &graphics[id];}
static unsigned MapGridGetElevationAt(unsigned x,unsigned y) {(void)x;(void)y;return 1;}
static u8 SpawnSpecialObjectEventParameterized(u8 gfx,u8 movement,u8 local,int x,int y,u8 elevation) {
 unsigned id;(void)movement;(void)elevation;
 if(failSpawn) return OBJECT_EVENTS_COUNT;
 for(id=1;id<OBJECT_EVENTS_COUNT;id++) if(!gObjectEvents[id].active) {
  struct ObjectEvent *o=&gObjectEvents[id];memset(o,0,sizeof(*o));
  o->active=TRUE;o->graphicsId=gfx;o->spriteId=id;o->localId=local;
  o->currentCoords=(struct Coords){x,y};gSprites[id].inUse=TRUE;gSprites[id].data[0]=id;spawned++;return id;
 }
 return OBJECT_EVENTS_COUNT;
}
static void MoveObjectEventToMapCoords(struct ObjectEvent *o,int x,int y) {o->currentCoords=(struct Coords){x,y};}
static void ObjectEventTurn(struct ObjectEvent *o,unsigned facing) {o->facingDirection=facing;}
static bool8 WorldCatalog_Metatile(unsigned g,unsigned n,unsigned m) {(void)g;(void)n;(void)m;return TRUE;}
static u16 Raw(unsigned x,unsigned y) {(void)x;(void)y;return 0;}
static void MapGridSetMetatileIdAt(unsigned x,unsigned y,unsigned m) {(void)x;(void)y;(void)m;}
static void CurrentMapDrawMetatileAt(unsigned x,unsigned y) {(void)x;(void)y;}
'''
        fixture += ''.join(function(source, name) for name in ('Owned', 'NativeNpcAt', 'SyncEngine'))
        fixture += r'''
int main(int argc,char **argv) {
 unsigned i,target=argc>1?(unsigned)strtoul(argv[1],NULL,10):1;
 if(target>=3) return 10;
 sWorld.tilesLive=TRUE;
 for(i=0;i<NUM_OBJ_EVENT_GFX;i++) graphics[i].paletteSlot=PALSLOT_NPC_1;
 sWorld.live.peerCount=3;
 for(i=0;i<3;i++) {
  struct Peer *p=&sWorld.live.peers[i];struct Remote *r=&sWorld.remotes[i];
  snprintf(p->id,sizeof(p->id),"peer%u",i);p->x=10+i;p->y=12;p->facing=1;p->gfx=7;p->ready=1;
  strcpy(r->id,p->id);r->object=i+1;r->sprite=i+1;
  gObjectEvents[i+1].active=TRUE;gObjectEvents[i+1].graphicsId=7;gObjectEvents[i+1].spriteId=i+1;
  gObjectEvents[i+1].localId=WB_LOCALID+i;
  gObjectEvents[i+1].currentCoords=(struct Coords){17+(int)i,19};gSprites[i+1].inUse=TRUE;
  gSprites[i+1].data[0]=i+1;gSprites[i+1].data[7]=WB_MARKER;
 }
 /* One peer changes appearance, the other two remain unchanged. */
 sWorld.live.peers[target].gfx=8;
 SyncEngine();
 if(!Owned(target)) {fputs("peer disappeared during graphics replacement\n",stderr);return 1;}
 if(gObjectEvents[sWorld.remotes[target].object].graphicsId!=8) return 2;
 if(removed!=1 || spawned!=1 || !Owned(0) || !Owned(1) || !Owned(2)) return 3;
 /* A stable frame does not churn any allocations. */
 SyncEngine();if(removed!=1 || spawned!=1) return 4;
 /* Allocation exhaustion leaves no stale handle and retries safely. */
 sWorld.live.peers[target].gfx=9;failSpawn=1;SyncEngine();
 if(Owned(target) || sWorld.remotes[target].id[0] || removed!=2 || spawned!=1) return 5;
 failSpawn=0;SyncEngine();
 if(!Owned(target) || gObjectEvents[sWorld.remotes[target].object].graphicsId!=9 || spawned!=2) return 6;
 /* Unsafe peer graphics select the ordinary trainer, not dynamic graphics. */
 sWorld.live.peers[target].gfx=255;SyncEngine();
 if(!Owned(target) || gObjectEvents[sWorld.remotes[target].object].graphicsId!=7) return 8;
 if(removed!=3 || spawned!=3) return 9;
 /* A single snapshot may change every peer, with no missing intermediate frame. */
 for(i=0;i<3;i++) sWorld.live.peers[i].gfx=8;
 SyncEngine();
 for(i=0;i<3;i++)
  if(!Owned(i) || gObjectEvents[sWorld.remotes[i].object].graphicsId!=8) return 11;
 if(removed!=6 || spawned!=6) return 12;
 /* The engine may reuse a former remote's slot for an ordinary map NPC.
  * Reconciliation must revoke that handle, not resize or delete the NPC. */
 {
  unsigned npc=sWorld.remotes[target].object;
  struct ObjectEvent before;
  gObjectEvents[npc].localId=42;gObjectEvents[npc].graphicsId=10;
  gObjectEvents[npc].currentCoords=(struct Coords){25,25};
  gSprites[npc].data[7]=0;before=gObjectEvents[npc];
  sWorld.live.peers[target].gfx=9;SyncEngine();
  if(memcmp(&before,&gObjectEvents[npc],sizeof(before))) return 13;
  if(!gSprites[npc].inUse || gSprites[npc].data[7]) return 14;
  if(!Owned(target) || sWorld.remotes[target].object==npc) return 15;
  if(removed!=6 || spawned!=7) return 16;
 }
 /* Leaving the field still releases all remote handles. */
 overworld=0;SyncEngine();
 if(Owned(0)||Owned(1)||Owned(2)||removed!=9) return 7;
 puts("graphics replacement and unchanged peers reconcile in one frame");return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='ew-presence-reconcile-') as tmp:
            c, exe = Path(tmp)/'fixture.c', Path(tmp)/'fixture'
            c.write_text(fixture)
            built = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                    str(c), '-o', str(exe)], text=True, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            for target in range(3):
                with self.subTest(remote_slot=target):
                    result = subprocess.run([str(exe), str(target)], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('one frame', result.stdout)


if __name__ == '__main__':
    unittest.main()
