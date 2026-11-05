from pathlib import Path
from collections import deque
import json, subprocess, tempfile, unittest
from unittest.mock import patch
from test_large_generated_cave import DOC
from test_save_isolation import function
from world import author_cave, cave_blueprint, wilds_cast
from world.shared_cave import SharedCave, CaveError
ROOT=Path(__file__).resolve().parents[2]

class WildsCast(unittest.TestCase):
    def test_model_cast_is_inert_and_connected(self):
        for style in ('rooms','rounded','organic','maze'):
            for seed in range(4):
                p=cave_blueprint.proposal_from_blueprint({**DOC,'style':style,'seed':seed},side=63)
                cast=[{'gfx':7,'text':'Hello!'},{'gfx':8,'text':'Welcome!'}, {'gfx':7,'text':'Third!'}]
                b=wilds_cast.encode(p,cast); self.assertEqual(len(b),4161);self.assertEqual(b[:9],b'EWGMAP08\x03')
                self.assertEqual(SharedCave(b).version,8)
                rows=wilds_cast.prepare(p,3)['rows'];blocked=set(wilds_cast.POSITIONS);seen={(1,1)};q=deque(seen)
                while q:
                    x,y=q.popleft()
                    for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
                        if 0<=nx<63 and 0<=ny<63 and (nx,ny) not in blocked and rows[ny][nx]=='.' and (nx,ny) not in seen:seen.add((nx,ny));q.append((nx,ny))
                self.assertEqual(len(seen),sum(r.count('.') for r in rows)-3);self.assertIn((61,61),seen)
                for x,y in blocked:self.assertIn((x-1,y),seen)
        for text in ('', ' '*4, 'x'*29, 'bad\x01', 'ok\n', 'café'):
            with self.assertRaises(ValueError):wilds_cast.encode(p,[{'gfx':7,'text':text}])
        doc={**DOC,'cast':[{'gfx':'boy','text':'Hello!'}, {'gfx':'girl','text':'Welcome!'}]}
        wire='\n'.join(json.dumps(x) for x in [{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(doc)}},{'type':'turn.completed'}]).encode()
        proposal,chars=author_cave.decode_blueprint_events(wire,large=True,cast=True);self.assertEqual(len(chars),2);self.assertEqual(chars[1]['gfx'],8)
        blob=wilds_cast.encode(proposal,chars)
        with tempfile.TemporaryDirectory() as t,patch('world.author_cave.author',return_value=(proposal,blob)) as a,patch('world.author_cave.publish_bytes') as pub,patch('builtins.print'):
            out=Path(t)/'cast.bin';self.assertEqual(author_cave.main(['forest','--cast-wilds-output',str(out)]),0);self.assertTrue(a.call_args.kwargs['cast']);self.assertEqual(out.read_bytes(),blob);pub.assert_not_called()

    def test_actual_loader_dispatches_and_rejects_truncation(self):
        source=(ROOT/'src/platform/sdl2.c').read_text()
        code=r'''#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_MAP_LARGE 1
#define GENERATED_MAP_WILDS 1
#define GENERATED_WILDS_GUIDE 1
#define GENERATED_WILDS_CAST 1
#define GENERATED_CAST_BYTES 184
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES 3969
#define GENERATED_WILDLIFE_BYTES 37
#define GENERATED_GUIDE_BYTES 59
static int calls;static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageLargeTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageWildsTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageGuidedWilds(const u8 *m,unsigned k,const u8 *p,unsigned n){(void)m;(void)k;(void)p;(void)n;return 0;}
static int GeneratedMap_StageCastWilds(const u8 *m,unsigned k,const u8 *p,unsigned n){calls++;return k==184&&n==3969&&m[0]==2&&p[0]=='#';}
''' + function(source,'LoadGeneratedMapTemplate') + r'''
int main(int argc,char **argv){if(argc!=4)return 1;
if(!LoadGeneratedMapTemplate(argv[1])||calls!=1)return 2;
if(LoadGeneratedMapTemplate(argv[2])||calls!=1)return 3;
if(LoadGeneratedMapTemplate(argv[3])||calls!=1)return 4;return 0;}
'''
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'test.c').write_text(code);blob=wilds_cast.encode(cave_blueprint.proposal_from_blueprint(DOC,side=63),[{'gfx':7,'text':'Welcome!'},{'gfx':8,'text':'Hello!'}])
            for name,data in [('good',blob),('short',blob[:-1]),('long',blob+b'x')]:(p/name).write_bytes(data)
            build=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(p/'test'),str(p/'good'),str(p/'short'),str(p/'long')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)

    def test_native_cast_event_and_safe_staging(self):
        groups=json.loads((ROOT/'data/maps/map_groups.json').read_text());group=groups['group_order'].index('gMapGroup_GeneratedWorld')
        global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\n#define OBJECT_EVENT_TEMPLATES_COUNT 64\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nstruct ObjectEventTemplate {u8 localId,graphicsId,kind;s16 x,y;u8 elevation,movementType;u16 trainerType,trainerRange_berryTreeId;const u8 *script;u16 flagId;};\nstruct MapEvents {u8 objectEventCount,warpCount,coordEventCount,bgEventCount;const struct ObjectEventTemplate *objectEvents;const void *warps,*coordEvents,*bgEvents;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;const struct MapEvents *events;} gMapHeader;\n'''
        code=r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
static int online;static struct WarpData destination;static struct MapEvents events;
const u8 GeneratedWorld_Wilds_EventScript_Guide[]={0};const u8 GeneratedWorld_Wilds_EventScript_Cast2[]={0}, GeneratedWorld_Wilds_EventScript_Cast3[]={0};extern u8 gGeneratedWildsGuideText[58];
const char *LinkTransport_TagPeer(void){return 0;}const void *LinkTransport_PendingTag(void){return 0;}const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void){return 0;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return online;}int WorldBridge_GeneratedCaveReady(void){return 1;}int Platform_ReloadGeneratedMap(void){return 1;}
int IsMapTypeOutdoors(int x){return x==1;}int TestPlayerAvatarFlags(int f){return f==1;}
void PlayerGetDestCoords(s16 *x,s16 *y){*x=15;*y=16;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int z,s8 g,s8 n,s8 w,s8 x,s8 y){(void)z;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){}
int main(void){u8 meta[184],badmeta[184],data[3969],bad[3969];struct MapLayout base={19,26,0,0,0,0};const struct MapLayout *layout;
 assert(fread(meta,1,sizeof(meta),stdin)==sizeof(meta));assert(fread(data,1,sizeof(data),stdin)==sizeof(data));memcpy(bad,data,sizeof(data));bad[0]='.';
 assert(!GeneratedMap_StageCastWilds(meta,sizeof(meta),bad,sizeof(bad)));memcpy(badmeta,meta,sizeof(meta));badmeta[4]=0xfc;
 assert(!GeneratedMap_StageCastWilds(badmeta,sizeof(badmeta),data,sizeof(data)));assert(GeneratedMap_StageCastWilds(meta,sizeof(meta),data,sizeof(data)));
 assert(!GeneratedMap_StageCastWilds(badmeta,sizeof(badmeta),data,sizeof(data)));assert(gGeneratedWildsGuideText[0]==0xd1);
 online=1;assert(!GeneratedMap_StageCastWilds(meta,sizeof(meta),data,sizeof(data)));online=0;
 events.warpCount=1;events.warps=(const void*)0x1;gMapHeader.mapType=1;gMapHeader.mapLayout=&base;gMapHeader.events=&events;save.location=(struct WarpData){3,4,0,8,9};
 assert(GeneratedMap_Enter());save.location=destination;layout=GeneratedMap_ResolveLayout(&base);
 assert(layout->width==63 && layout->height==63 && layout->map[61*63+61]==0x3024);
 assert(gMapHeader.events->warpCount==1 && gMapHeader.events->warps==(const void*)0x1);
 assert(gMapHeader.events->objectEventCount==3 && gMapHeader.events->objectEvents[0].x==2 && gMapHeader.events->objectEvents[0].y==1);
 assert(gMapHeader.events->objectEvents[0].graphicsId==7 && gMapHeader.events->objectEvents[0].script==GeneratedWorld_Wilds_EventScript_Guide);
 assert(gGeneratedWildsGuideText[0]==0xd1 && gGeneratedWildsGuideText[8]==0xff); assert(gMapHeader.events->objectEvents[1].x==20 && gMapHeader.events->objectEvents[1].y==20); assert(gMapHeader.events->objectEvents[2].x==40 && gMapHeader.events->objectEvents[2].y==40); assert(gMapHeader.events->objectEvents[1].script==GeneratedWorld_Wilds_EventScript_Cast2);
 for(int i=0;i<3969;i++){u16 tile=layout->map[i];if(i==61*63+61)continue;
 if(data[i]=='.')assert(tile==0x3001||tile==0x300d);else assert(tile==0x0487);}
 assert(!GeneratedMap_StageCastWilds(meta,sizeof(meta),data,sizeof(data)));
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
            (p/'constants/event_object_movement.h').write_text('#define MOVEMENT_TYPE_FACE_LEFT 9\n')
            (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GENERATED_WORLD_WILDS (({group}<<8)|1)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
            (p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_MAP_AUTOTILE=1','-DGENERATED_MAP_LARGE=1','-DGENERATED_MAP_WILDS=1','-DGENERATED_WILDS_GUIDE=1','-DGENERATED_WILDS_CAST=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(p/'test.c'),'-o',str(p/'test')]
            build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
            cells=wilds_cast.encode(cave_blueprint.proposal_from_blueprint(DOC,side=63),[{'gfx':7,'text':'Welcome!'},{'gfx':8,'text':'Second!'},{'gfx':7,'text':'Third!'}])[8:]
            result=subprocess.run([str(p/'test')],input=cells,capture_output=True);self.assertEqual(result.returncode,0,result.stderr.decode())
