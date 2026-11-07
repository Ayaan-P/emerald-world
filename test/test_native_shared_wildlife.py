"""Real native wire/runtime C with isolated engine adapters, not a game build."""
from pathlib import Path
import os, hashlib, json, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT / 'engines/expansion-native'))
class NativeSharedWildlifeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global ENGINE
        cls.source_dir = tempfile.TemporaryDirectory()
        handoff = ROOT / 'docs/attempt-handoffs/rc7'
        manifest = json.loads((handoff / 'shared-wildlife-source-manifest.json').read_text())
        patch = (handoff / manifest['patch']).read_bytes()
        assert hashlib.sha256(patch).hexdigest() == manifest['patch_sha256']
        sources, path = {}, None
        for line in patch.decode().splitlines():
            if line.startswith('diff --git '):
                path = None
            elif line.startswith('+++ b/'):
                path = line[6:]
                sources[path] = []
            elif path and line.startswith((' ', '+')):
                sources[path].append(line[1:])
            elif path and line == '':
                sources[path].append('')
        for entry in manifest['files']:
            content = '\n'.join(sources[entry['path']]) + '\n'
            if entry['path'] not in manifest.get('partial_context_files', []):
                assert hashlib.sha256(content.encode()).hexdigest() == entry['sha256']
            if 'EW_RC7_ENGINE' in os.environ:
                assert hashlib.sha256((ENGINE / entry['path']).read_bytes()).hexdigest() == entry['sha256']
            target = Path(cls.source_dir.name) / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        if 'EW_RC7_ENGINE' not in os.environ:
            ENGINE = Path(cls.source_dir.name)

    @classmethod
    def tearDownClass(cls):
        cls.source_dir.cleanup()

    def compile_run(self, sources):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            files = []
            for i, source in enumerate(sources):
                path = p / f'test{i}.c'; path.write_text(source); files.append(str(path))
            subprocess.run(['gcc','-DPORTABLE','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                            '-iquote',str(ENGINE/'include'),*files,'-o',str(p/'test')],check=True,capture_output=True)
            subprocess.run([str(p/'test')],check=True,capture_output=True)

    def test_wire_validation(self):
        self.compile_run([(ENGINE/'src/world/shared_wildlife_wire.c').read_text(),WIRE_MAIN])

    def test_native_admission_lifecycle(self):
        source = (ENGINE/'src/world/shared_wildlife.c').read_text()
        source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
        self.compile_run([RUNTIME_STUB + source + '\n' + RUNTIME_MAIN])

    def test_bridge_atomic_publication_and_teardown(self):
        source = (ENGINE/'src/world/world_bridge.c').read_text()
        validation = source.index('!SharedWildlifeWire_Complete')
        publish = source.index('sWorld.live = sWorld.stage', validation)
        self.assertLess(source.index('!IsSpeciesEnabled(mon->species)',validation), publish)
        self.assertIn('SharedWildlife_ClearSprites();',source.split('void WorldBridge_PrepareSave(void)')[1])
        self.assertIn('SharedWildlife_ClearSprites();',source.split('void WorldBridge_Close(void)')[1])
        self.assertIn('WILDLIFE SUBSCRIBE %s 2',source)
        self.assertIn('sWorld.wildlifeRequested = FALSE',source)
        battle=(ENGINE/'src/wild_encounter_ow.c').read_text().split('bool8 StartSharedWildlifeBattle')[1]
        self.assertIn('ClearNativeOWEEncounter(NULL)',battle)
        self.assertIn('BattleSetup_StartWildBattle()',battle)
        self.assertNotIn('gSpecialVar_LastTalked',battle)

WIRE_MAIN = r'''
#include <assert.h>
#include <string.h>
#include "platform/shared_wildlife_wire.h"
static int line(struct SharedWildlifeSnapshot *s,const char *text){char buf[300],*tokens[20],*p;unsigned n=0;strcpy(buf,text);p=strtok(buf," ");while(p){tokens[n++]=p;p=strtok(NULL," ");}return SharedWildlifeWire_Line(s,n,tokens);}
int main(void){struct SharedWildlifeSnapshot s={0};
 assert(!line(&s,"WILDMON bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb 0 16 5 5 25 5 available"));
 assert(line(&s,"WILDLIFE2 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 1 1"));
 assert(!SharedWildlifeWire_Complete(&s));
 assert(!line(&s,"WILDMON bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb 0 16 5 5 25 101 available"));
 assert(!line(&s,"WILDMON bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb 0 16 5 5 025 5 available"));
 assert(line(&s,"WILDMON bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb 0 16 5 5 25 5 available"));
 assert(SharedWildlifeWire_Complete(&s));
 assert(!line(&s,"WILDMON bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb 0 16 5 5 25 5 available"));
 assert(line(&s,"WILDBATTLE bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb cccccccccccccccccccccccccccccccc 0 16 5 5 25 5"));
 assert(!SharedWildlifeWire_Complete(&s));
 memset(&s,0,sizeof(s));assert(!line(&s,"WILDLIFE2 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 4294967296 0"));
 memset(&s,0,sizeof(s));assert(line(&s,"WILDLIFE2 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 2 0"));
 assert(line(&s,"WILDBATTLE bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb cccccccccccccccccccccccccccccccc 0 16 5 5 25 5"));
 assert(SharedWildlifeWire_Complete(&s));
 assert(!line(&s,"WILDBATTLE bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb cccccccccccccccccccccccccccccccc 0 16 5 5 25 5"));
 assert(line(&s,"WILDLEASE bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb cccccccccccccccccccccccccccccccc"));
 assert(!SharedWildlifeWire_Complete(&s));return 0;}
'''
RUNTIME_STUB = r'''
#include <assert.h>
#include <stddef.h>
#include <string.h>
#include <limits.h>
typedef unsigned u32; typedef unsigned short u16; typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define OBJECT_EVENTS_COUNT 16
#define MAX_SPRITES 32
#define MAP_OFFSET 7
#define DIR_SOUTH 1
#define DIR_NORTH 2
#define DIR_WEST 3
#define DIR_EAST 4
#define A_BUTTON 1
#define B_BUTTON 2
struct ObjectEvent {unsigned active,isPlayer,localId,mapGroup,mapNum,spriteId; struct {int x,y;} currentCoords;};
struct ObjectEvent gObjectEvents[16];
struct {unsigned inUse; int data[8];} gSprites[32];
struct {unsigned objectEventId,tileTransitionState;} gPlayerAvatar;
struct Save {struct {unsigned mapGroup,mapNum;} location; struct {unsigned localId;} objectEventTemplates[16];} save,*gSaveBlock1Ptr=&save;
void *gSaveBlock2Ptr=&save;
struct Events {unsigned objectEventCount;};
struct {struct Events *events;} gMapHeader;
void CB1_Overworld(void){} void CB2_Overworld(void){}
struct {void (*callback1)(void),(*callback2)(void); unsigned inBattle;} gMain;
struct {unsigned active;} gPaletteFade;
static int locked,freeze,removed,started,have=1,allow=1,requests[4],blocked,unavailable;
int ScriptContext_IsEnabled(void){return 0;}
int WorldActivity_OwnsFieldInput(void){return 0;}
void RemoveObjectEvent(struct ObjectEvent *o){o->active=0; removed++;}
void UnlockPlayerFieldControls(void){locked=0;}
void UnfreezeObjectEvents(void){freeze=0;}
void LockPlayerFieldControls(void){locked=1;}
void FreezeObjectEvents(void){freeze=1;}
void StopPlayerAvatar(void){}
int GetPlayerFacingDirection(void){return DIR_SOUTH;}
int MapGridGetCollisionAt(int x,int y){(void)x;(void)y;return blocked;}
int ArePlayerFieldControlsLocked(void){return locked;}
const char *OverworldEncounters_UnavailableReason(void){return unavailable?"busy":NULL;}
#include "platform/shared_wildlife_wire.h"
static struct SharedWildlifeSnapshot snapshot;
bool8 WorldBridge_SharedWildlifeSnapshot(struct SharedWildlifeSnapshot *out){*out=snapshot;return have;}
bool8 WorldBridge_SharedWildlifeRequest(unsigned a,const char *e,const char *id,const char *l){(void)e;(void)id;(void)l;requests[a]++;return allow;}
u32 SpawnSharedWildlifeObject(u32 local,u32 species,int x,int y){(void)species;gObjectEvents[1]=(struct ObjectEvent){1,0,local,0,16,1,{x+7,y+7}};gSprites[1].inUse=1;gSprites[1].data[0]=1;return 1;}
bool8 StartSharedWildlifeBattle(u32 species,u32 level){assert(species==25&&level==5);started++;gMain.inBattle=1;return 1;}
'''
RUNTIME_MAIN = r'''
int main(void){
 gMain.callback1=CB1_Overworld; gMain.callback2=CB2_Overworld;
 save.location.mapNum=16; gObjectEvents[0]=(struct ObjectEvent){1,1,255,0,16,0,{12,11}};
 strcpy(snapshot.epoch,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
 snapshot.seen=1;snapshot.count=snapshot.expected=1;
 snapshot.mons[0]=(struct SharedWildlifeMon){.group=0,.num=16,.x=5,.y=5,.species=25,.level=5};
 strcpy(snapshot.mons[0].id,"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
 SharedWildlife_Update(1);assert(Owned(0));
 assert(!(SharedWildlife_FilterInput(A_BUTTON)&A_BUTTON));assert(requests[0]==1&&locked&&freeze);
 strcpy(snapshot.leaseId,snapshot.mons[0].id);strcpy(snapshot.lease,"cccccccccccccccccccccccccccccccc");
 SharedWildlife_Update(2);assert(requests[1]==1&&started==0);
 snapshot.battle=snapshot.mons[0];snapshot.count=snapshot.expected=0;snapshot.leaseId[0]=0;
 strcpy(snapshot.battleLease,snapshot.lease);snapshot.battleSeen=1;
 SharedWildlife_Update(3);assert(started==1&&requests[2]==1&&!gObjectEvents[1].active);
 SharedWildlife_Update(4);assert(started==1);
 gMain.inBattle=0;locked=freeze=0;SharedWildlife_Update(5);assert(started==1&&requests[2]==2);
 snapshot.battleSeen=0;snapshot.count=snapshot.expected=1;
 SharedWildlife_FilterInput(0);SharedWildlife_Update(6);assert(Owned(0));
 /* Reused object slot must never be removed by stale projection ownership. */
 gSprites[1].data[7]=0;SharedWildlife_ClearSprites();assert(gObjectEvents[1].active);
 gObjectEvents[1].active=0;SharedWildlife_Update(7);assert(Owned(0));
 SharedWildlife_FilterInput(A_BUTTON);assert(sPhase==1);
 SharedWildlife_FilterInput(B_BUTTON);assert(!sPhase&&!locked&&!freeze);
 snapshot.battleSeen=1;snapshot.count=snapshot.expected=0;
 SharedWildlife_Update(8);assert(started==1); /* Late receipt cannot start battle. */
 snapshot.battleSeen=0;snapshot.count=snapshot.expected=1;
 SharedWildlife_FilterInput(0);SharedWildlife_Update(9);
 SharedWildlife_FilterInput(A_BUTTON);have=0;SharedWildlife_Update(10);
 assert(!sPhase&&!locked&&!freeze&&!gObjectEvents[1].active);
 return 0;
}
'''
