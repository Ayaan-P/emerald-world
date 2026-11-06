from pathlib import Path
import json,subprocess,tempfile,unittest
from collections import deque
from world import cave_blueprint,xl_wilds
from world.shared_cave import SharedCave,CaveError
from test_large_generated_cave import DOC
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
class XLWilds(unittest.TestCase):
    def test_agent_blueprint_and_closed_connected_geometry(self):
        for style in ('rooms','rounded','organic','maze'):
            p=cave_blueprint.proposal_from_blueprint({**DOC,'style':style},side=127);b=xl_wilds.encode(p)
            self.assertEqual(len(b),16137);self.assertEqual(b[:8],b'EWGMAP0A');self.assertEqual(p['exit'],[125,125])
            with self.assertRaises(CaveError):SharedCave(b)
        bad=dict(p);bad['rows']=p['rows'].copy();bad['rows'][0]='.'+bad['rows'][0][1:]
        with self.assertRaises(ValueError):xl_wilds.encode(bad)
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);(d/'in.json').write_text(json.dumps(DOC));r=subprocess.run(['python','-m','world.xl_wilds',str(d/'in.json'),str(d/'out.bin')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual((d/'out.bin').read_bytes(),xl_wilds.encode(cave_blueprint.proposal_from_blueprint(DOC,side=127)))
            self.assertNotEqual(subprocess.run(['python','-m','world.xl_wilds',str(d/'in.json'),str(d/'out.bin')],cwd=ROOT,capture_output=True).returncode,0)

    def test_actual_loader_accepts_only_exact_xl_format(self):
        src=(ROOT/'src/platform/sdl2.c').read_text()
        code=r'''#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_MAP_LARGE 1
#define GENERATED_MAP_WILDS 1
#define GENERATED_WORLD_XL 1
#define GENERATED_XL_MAP_BYTES 16129
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES 3969
#define GENERATED_WILDLIFE_BYTES 37
static int calls;static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageLargeTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageWildsTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageXLWilds(const u8 *p,unsigned n){calls++;return n==16129 && p[0]=='#';}
static int GeneratedMap_StageXLPalette(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
''' + function(src,'LoadGeneratedMapTemplate') + r'''
int main(int argc,char **argv){if(argc!=4)return 1;
if(!LoadGeneratedMapTemplate(argv[1])||calls!=1)return 2;
if(LoadGeneratedMapTemplate(argv[2])||calls!=1)return 3;
if(LoadGeneratedMapTemplate(argv[3])||calls!=1)return 4;return 0;}
'''
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'test.c').write_text(code);blob=xl_wilds.encode(cave_blueprint.proposal_from_blueprint(DOC,side=127))
            for name,data in [('good',blob),('short',blob[:-1]),('long',blob+b'x')]:(p/name).write_bytes(data)
            build=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(p/'test'),str(p/'good'),str(p/'short'),str(p/'long')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)

    def test_map_buffer_gate_keeps_default_and_gba_capacity(self):
        for defines,expected in ((['-DPORTABLE','-DGENERATED_WORLD_XL=1'],'24576'),(['-DPORTABLE','-DGENERATED_WORLD_XL=0'],'10240'),(['-DGENERATED_WORLD_XL=1'],'10240')):
            run=subprocess.run(['cc','-E','-dM',*defines,'-I'+str(ROOT/'include'),'-x','c','-'],input='#include "fieldmap.h"\n',capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertIn('#define MAX_MAP_DATA_SIZE '+expected,run.stdout)

    def test_native_xl_staging_warp_and_layout(self):
        groups=json.loads((ROOT/'data/maps/map_groups.json').read_text());group=groups['group_order'].index('gMapGroup_GeneratedWorld')
        global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nstruct WarpEvent {s16 x,y;u8 elevation,warpId,mapNum,mapGroup;};\nstruct MapEvents {u8 objectEventCount,warpCount,coordEventCount,bgEventCount;const void *objectEvents;const struct WarpEvent *warps;const void *coordEvents,*bgEvents;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;const struct MapEvents *events;} gMapHeader;\n'''
        code=r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
static int online;static struct WarpData destination;static struct WarpEvent warp={61,61,3,0,0,0};static struct MapEvents events={0,1,0,0,0,&warp,0,0};
const char *LinkTransport_TagPeer(void){return 0;}const void *LinkTransport_PendingTag(void){return 0;}const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void){return 0;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return online;}int WorldBridge_GeneratedCaveReady(void){return 1;}int Platform_ReloadGeneratedMap(void){return 1;}
int IsMapTypeOutdoors(int x){return x==1;}int TestPlayerAvatarFlags(int f){return f==1;}
void PlayerGetDestCoords(s16 *x,s16 *y){*x=15;*y=16;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int z,s8 g,s8 n,s8 w,s8 x,s8 y){(void)z;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){}
int main(void){u8 data[16129],bad[16129],paint[16129];unsigned chosen=0;struct MapLayout base={19,26,0,0,0,0};const struct MapLayout *layout;
 assert(fread(data,1,sizeof(data),stdin)==sizeof(data));memcpy(bad,data,sizeof(data));bad[0]='.';
 assert(!GeneratedMap_StageXLWilds(bad,sizeof(bad)));memcpy(paint,data,sizeof(paint));for(unsigned i=129;i<16000;i++)if(paint[i]=='.'){chosen=i;break;}assert(chosen);paint[chosen]='t';assert(GeneratedMap_StageXLPalette(paint,sizeof(paint)));
 online=1;assert(!GeneratedMap_StageXLWilds(data,sizeof(data)));online=0;
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;gMapHeader.events=&events;save.location=(struct WarpData){3,4,0,8,9};
 assert(GeneratedMap_Enter());save.location=destination;layout=GeneratedMap_ResolveLayout(&base);
 assert(layout->width==127 && layout->height==127 && layout->map[chosen]==0x300d && layout->map[125*127+125]==0x3024 && gMapHeader.events->warps->x==125 && gMapHeader.events->warps->y==125);
 for(int i=0;i<16129;i++){u16 tile=layout->map[i];if(i==125*127+125)continue;
 if(data[i]=='.')assert(tile==0x3001||tile==0x300d);else assert(tile==0x0487);}
 assert(!GeneratedMap_StageXLWilds(data,sizeof(data)));
 assert(GeneratedMap_Leave());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(save.location.mapGroup==3 && save.location.mapNum==4 && save.location.x==8 && save.location.y==9);
 return 0;}
'''
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
            for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
                (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void SetWarpDestination(s8,s8,s8,s8,s8);void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void PlayerGetDestCoords(s16*,s16*);void StoreInitialPlayerAvatarState(void);void DoWarp(void);\n#define MAP_OFFSET 7\n')
            (p/'task.h').write_text('struct Task {int isActive;}; extern struct Task gTasks[16];\n#define NUM_TASKS 16\n')
            (p/'platform/world_rally.h').write_text('struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void);int WorldRally_GetSnapshot(struct WorldRallySnapshot *);\n')
            (p/'platform/link_transport.h').write_text('const char *LinkTransport_TagPeer(void);const void *LinkTransport_PendingTag(void);const void *LinkTransport_PendingInvitation(void);\n')
            (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void);int WorldBridge_GeneratedCaveReady(void);\n')
            (p/'platform/generated_map.h').write_text((ROOT/'include/platform/generated_map.h').read_text())
            (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GENERATED_WORLD_WILDS (({group}<<8)|1)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
            (p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_MAP_AUTOTILE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WORLD_XL=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(p/'test.c'),'-o',str(p/'test')]
            build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
            cells=xl_wilds.encode(cave_blueprint.proposal_from_blueprint(DOC,side=127))[8:]
            result=subprocess.run([str(p/'test')],input=cells,capture_output=True);self.assertEqual(result.returncode,0,result.stderr.decode())
