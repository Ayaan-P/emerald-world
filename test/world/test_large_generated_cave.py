"""Large generated caves: geometry, opt-in model author and native runtime."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from world import cave_blueprint, large_cave, author_cave
from test_save_isolation import function

ROOT=Path(__file__).resolve().parents[2]
DOC={'rooms':[[2,2,15,15],[45,45,15,15]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':'organic','seed':5}

class LargeCave(unittest.TestCase):
    def test_blueprint_and_model_wire(self):
        proposal=cave_blueprint.proposal_from_blueprint(DOC,side=63)
        blob=large_cave.encode(proposal)
        self.assertEqual(len(blob),3977);self.assertEqual(blob[:8],b'EWGMAP04')
        self.assertEqual(proposal['exit'],[61,61]);self.assertEqual(len(proposal['rows']),63)
        wire='\n'.join(json.dumps(x) for x in [{'type':'item.completed','item':{'type':'agent_message','text':json.dumps(DOC)}},{'type':'turn.completed'}]).encode()
        self.assertEqual(author_cave.decode_blueprint_events(wire,large=True),proposal)
        self.assertIn('1..61',author_cave.prompt_for('large cave',large=True))
        with tempfile.TemporaryDirectory() as t,patch('world.author_cave.author',return_value=(proposal,blob)) as a,patch('world.author_cave.publish_bytes') as p,patch('builtins.print'):
            path=Path(t)/'large.bin';self.assertEqual(author_cave.main(['large cave','--large-offline-output',str(path)]),0)
            self.assertEqual(path.read_bytes(),blob);self.assertTrue(a.call_args.kwargs['large']);p.assert_not_called()

    def test_invalid_geometry_never_encodes(self):
        p=cave_blueprint.proposal_from_blueprint(DOC,side=63)
        bad=dict(p);bad['rows']=p['rows'].copy();bad['rows'][0]='.'+bad['rows'][0][1:]
        with self.assertRaises(ValueError):large_cave.encode(bad)
        bad=dict(p);bad['exit']=[29,29]
        with self.assertRaises(ValueError):large_cave.encode(bad)
        with self.assertRaises(ValueError):cave_blueprint.proposal_from_blueprint(DOC,side=32)
        with self.assertRaises(ValueError):cave_blueprint.proposal_from_blueprint(DOC)

    def test_actual_loader_accepts_only_exact_large_format(self):
        src=(ROOT/'src/platform/sdl2.c').read_text()
        code=r'''#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef int bool8;
#define FALSE 0
#define GENERATED_MAP_LARGE 1
#define GENERATED_CAVE_PROFILES 0
#define GENERATED_CAVE_WILDLIFE 0
#define GENERATED_MAP_TEMPLATE_BYTES 961
#define GENERATED_LARGE_MAP_TEMPLATE_BYTES 3969
#define GENERATED_WILDLIFE_BYTES 37
static int calls;static FILE *NativeFile_Open(const char *p,const char *m){return fopen(p,m);}
static int GeneratedMap_StageTemplate(const u8 *p,unsigned n){(void)p;(void)n;return 0;}
static int GeneratedMap_StageLargeTemplate(const u8 *p,unsigned n){calls++;return n==3969 && p[0]=='#';}
''' + function(src,'LoadGeneratedMapTemplate') + r'''
int main(int argc,char **argv){if(argc!=4)return 1;
if(!LoadGeneratedMapTemplate(argv[1])||calls!=1)return 2;
if(LoadGeneratedMapTemplate(argv[2])||calls!=1)return 3;
if(LoadGeneratedMapTemplate(argv[3])||calls!=1)return 4;return 0;}
'''
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'test.c').write_text(code);blob=large_cave.encode(cave_blueprint.proposal_from_blueprint(DOC,side=63))
            for name,data in [('good',blob),('short',blob[:-1]),('long',blob+b'x')]:(p/name).write_bytes(data)
            build=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(p/'test'),str(p/'good'),str(p/'short'),str(p/'long')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)

    def test_native_staging_rejects_corruption_and_uses_large_layout(self):
        groups=json.loads((ROOT/'data/maps/map_groups.json').read_text());group=groups['group_order'].index('gMapGroup_GeneratedWorld')
        global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;} gMapHeader;\n'''
        code=r'''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
static int online;static struct WarpData destination;
const char *LinkTransport_TagPeer(void){return 0;}const void *LinkTransport_PendingTag(void){return 0;}const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void){return 0;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return online;}int WorldBridge_GeneratedCaveReady(void){return 1;}int Platform_ReloadGeneratedMap(void){return 1;}
int IsMapTypeOutdoors(int x){return x==1;}int TestPlayerAvatarFlags(int f){return f==1;}
void PlayerGetDestCoords(s16 *x,s16 *y){*x=15;*y=16;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int z,s8 g,s8 n,s8 w,s8 x,s8 y){(void)z;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){}
int main(void){u8 data[3969],bad[3969];struct MapLayout base={19,26,0,0,0,0};const struct MapLayout *layout;
 assert(fread(data,1,sizeof(data),stdin)==sizeof(data));memcpy(bad,data,sizeof(data));bad[0]='.';
 assert(!GeneratedMap_StageLargeTemplate(bad,sizeof(bad)));assert(GeneratedMap_StageLargeTemplate(data,sizeof(data)));
 online=1;assert(!GeneratedMap_StageLargeTemplate(data,sizeof(data)));online=0;
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;save.location=(struct WarpData){3,4,0,8,9};
 assert(GeneratedMap_Enter());save.location=destination;layout=GeneratedMap_ResolveLayout(&base);
 assert(layout->width==63 && layout->height==63 && layout->map[61*63+61]==0x3323);
 for(int i=0;i<3969;i++){u16 tile=layout->map[i];if(i==61*63+61)continue;
 if(data[i]=='.')assert(tile==0x331b);else assert((tile&0x400)!=0);}
 assert(!GeneratedMap_StageLargeTemplate(data,sizeof(data)));
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
            (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
            (p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_MAP_AUTOTILE=1','-DGENERATED_MAP_LARGE=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(p/'test.c'),'-o',str(p/'test')]
            build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
            cells=large_cave.encode(cave_blueprint.proposal_from_blueprint(DOC,side=63))[8:]
            result=subprocess.run([str(p/'test')],input=cells,capture_output=True);self.assertEqual(result.returncode,0,result.stderr.decode())
