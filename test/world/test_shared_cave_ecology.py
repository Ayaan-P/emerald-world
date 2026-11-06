"""Versioned shared cave ecology: in-memory authority and native wire components.

No real sockets, multiplayer game sessions or provider calls are used.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_save_isolation import function
from test_shared_generated_cave import MemoryAuthority
from world import author_cave, cave_blueprint, offline_cave
from world.shared_cave import SharedCave, CaveError
from scripts.export_generated_cave import encode

ROOT=Path(__file__).resolve().parents[2]
BLUEPRINT={'rooms':[[2,2,12,12],[16,16,12,12]],'links':[[0,1]],'entrance_room':0,'exit_room':1,'style':'organic','seed':42}
PROPOSAL=cave_blueprint.proposal_from_blueprint(BLUEPRINT)

class SharedCaveEcology(unittest.TestCase):
    def test_authority_v2_negotiation_legacy_and_profile_identity(self):
        blob=offline_cave.encode_profile(PROPOSAL,'meteor')
        v2=SharedCave(blob)
        self.assertEqual(v2.profile,1)
        self.assertEqual(v2.identity,hashlib.sha256(blob).hexdigest())
        self.assertEqual(v2.frames().splitlines()[0],f'CAVE BEGIN {v2.identity} 1')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);server=MemoryAuthority(root/'socket',root/'world',cave_template=blob)
            try:
                alice=server.create_identity('Alice');bob=server.create_identity('Bob')
                def connect(identity,role):
                    c={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
                    server._line(c,('HELLO 1 %s %s %s' % (identity['id'],identity['token'],role)).encode())
                    self.assertIn(b'WELCOME 1',c['out']);c['out'].clear();return c
                new=connect(alice,'SOCIALTRAVELCHATRALLYCAVE2')
                old=connect(bob,'SOCIALTRAVELCHATRALLYCAVE')
                server._line(new,b'CAVE GET');self.assertEqual(new['out'].decode(),v2.frames());new['out'].clear()
                server._line(old,b'CAVE GET');self.assertEqual(old['out'],b'CAVE NONE\n');old['out'].clear()
                server._line(new,('CAVE ACK '+v2.identity).encode());self.assertEqual(new['out'],('CAVE OK '+v2.identity+'\n').encode());new['out'].clear()
                group,num=server.cave_map
                server._line(new,(f'STATE 1 {group} {num} 1 1 1 7 1 '+('a'*16)+' '+('b'*16)).encode())
                self.assertFalse(new['closing'])
                with self.assertRaises(ValueError):server._replace_cave(offline_cave.encode_profile(PROPOSAL,'ice'))
                # A legacy client cannot acknowledge a v2 cave it was never offered.
                server._line(old,('CAVE ACK '+v2.identity).encode());self.assertTrue(old['closing'])
            finally:server.close()

    def test_legacy_client_recovers_when_host_returns_to_v1(self):
        v2=offline_cave.encode_profile(PROPOSAL,'meteor')
        v1=encode(PROPOSAL)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);server=MemoryAuthority(root/'socket',root/'world',cave_template=v2)
            try:
                bob=server.create_identity('Bob')
                conn={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
                server._line(conn,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE' % (bob['id'],bob['token'])).encode())
                conn['out'].clear();server._line(conn,b'CAVE GET')
                self.assertEqual(conn['out'],b'CAVE NONE\n');conn['out'].clear()
                expected=server._replace_cave(v1)
                self.assertEqual(conn['out'],('CAVE RESET '+expected+'\n').encode());conn['out'].clear()
                server._line(conn,b'CAVE GET')
                self.assertEqual(conn['out'].decode(),server.shared_cave.frames())
                self.assertIsNone(server.shared_cave.profile)
            finally:server.close()

    def test_profile_only_replacement_resets_clients_and_persists(self):
        first=offline_cave.encode_profile(PROPOSAL,'meteor')
        replacement=offline_cave.encode_profile(PROPOSAL,'ice')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);server=MemoryAuthority(root/'socket',root/'world',cave_template=first,persist_generated_cave=True)
            try:
                alice=server.create_identity('Alice')
                conn={'id':None,'out':bytearray(),'closing':False,'state':None,'seq':0,'sock':object()}
                server._line(conn,('HELLO 1 %s %s SOCIALTRAVELCHATRALLYCAVE2' % (alice['id'],alice['token'])).encode())
                self.assertIn(b'WELCOME 1',conn['out']);conn['out'].clear()
                server._line(conn,b'CAVE GET');old=server.shared_cave.identity;conn['out'].clear()
                server._line(conn,('CAVE ACK '+old).encode());conn['out'].clear()
                new=server._replace_cave(replacement)
                self.assertNotEqual(old,new)
                self.assertEqual(conn['out'],('CAVE RESET '+new+'\n').encode())
                self.assertIsNone(conn['cave_ack'])
                self.assertEqual(server.shared_cave.profile,2)
            finally:server.close()
            restored=MemoryAuthority(root/'socket',root/'world',persist_generated_cave=True)
            try:
                self.assertEqual(restored.shared_cave.identity,new)
                self.assertEqual(restored.shared_cave.profile,2)
            finally:restored.close()

    def test_real_native_v2_digest_and_tamper_rejection(self):
        code=r'''
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/world_cave_wire.h"
int main(void){char line[256];struct WorldCaveWire w={0};int result=0;
 while(fgets(line,sizeof(line),stdin)){char *tokens[5],*save,*p;unsigned n=0;
 line[strcspn(line,"\n")]=0;for(p=strtok_r(line," ",&save);p&&n<5;p=strtok_r(NULL," ",&save))tokens[n++]=p;
 result=WorldCaveWire_Feed(&w,n,(const char *const*)tokens);if(result<0)return 2;}
 return result==1 && w.version==2 ? 0 : 3;}
'''
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'global.h').write_text('#include <stdint.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n');(root/'test.c').write_text(code)
            exe=root/'test';build=subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_CAVE_PROFILES=1','-iquote',str(root),'-iquote',str(ROOT/'include'),str(ROOT/'src/platform/world_cave_wire.c'),str(root/'test.c'),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            for profile in offline_cave.PROFILES:
                cave=SharedCave(offline_cave.encode_profile(PROPOSAL,profile));frames=cave.frames()
                result=subprocess.run([str(exe)],input=frames,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                changed=frames.replace(f'CAVE BEGIN {cave.identity} {cave.profile}',f'CAVE BEGIN {cave.identity} {(cave.profile+1)%4}',1)
                self.assertNotEqual(subprocess.run([str(exe)],input=changed,capture_output=True,text=True).returncode,0)
            cave=SharedCave(offline_cave.encode_profile(PROPOSAL,'meteor'))
            for bad in ('4','-1','01','x'):
                frames=cave.frames().replace(f'CAVE BEGIN {cave.identity} 1',f'CAVE BEGIN {cave.identity} {bad}',1)
                self.assertNotEqual(subprocess.run([str(exe)],input=frames,capture_output=True,text=True).returncode,0)

    def test_native_negotiation_falls_back_to_v1_then_legacy(self):
        src=(ROOT/'src/platform/world_bridge.c').read_text()
        code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define GENERATED_MAP_READY 1
#define GENERATED_CAVE_PROFILES 1
static struct {bool8 rallyProbe,rallyLegacy,travelProbe,travelLegacy,chatProbe,chatLegacy,caveProbe,caveLegacy,caveV2Probe,caveV2Legacy;char trainer[25],token[65],output[4096];int outputSize;} sWorld;
''' + function(src,'CaveProbeRejected') + function(src,'QueueHello') + r'''
int main(void){char *err[]={"ERROR","AUTH"};strcpy(sWorld.trainer,"alice");strcpy(sWorld.token,"token");
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYCAVE2\n") && sWorld.caveV2Probe);
 assert(CaveProbeRejected(2,err)&&sWorld.caveV2Legacy&&!sWorld.caveLegacy);
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLYCAVE\n")&&!sWorld.caveV2Probe);
 assert(CaveProbeRejected(2,err)&&sWorld.caveLegacy);
 QueueHello(0);assert(strstr(sWorld.output,"SOCIALTRAVELCHATRALLY\n")&&!sWorld.caveProbe);
 return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c,exe=Path(tmp)/'test.c',Path(tmp)/'test';c.write_text(code)
            build=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_model_shared_ecology_requires_explicit_owner_target(self):
        blob=offline_cave.encode_profile(PROPOSAL,'ice')
        with patch('world.author_cave.author',return_value=(PROPOSAL,blob)) as author, \
             patch('world.author_cave.publish_bytes',return_value='id') as publish,patch('builtins.print'):
            self.assertEqual(author_cave.main(['ice','--admin-socket','/tmp/owner.sock','--shared-ecology']),0)
            self.assertTrue(author.call_args.kwargs['offline_ecology']);publish.assert_called_once()
        with self.assertRaises(SystemExit),patch('builtins.print'),patch('sys.stderr'):
            author_cave.main(['ice','--shared-ecology'])


class NativeSharedEcologyFlow(unittest.TestCase):
    def test_profile_only_replacement_returns_before_restaging(self):
        groups=json.loads((ROOT/'data/maps/map_groups.json').read_text())
        group=groups['group_order'].index('gMapGroup_GeneratedWorld')
        rows=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
        cells=''.join(rows).encode('ascii')
        ida=hashlib.sha256(b'EWGMAP02'+b'\x01'+cells).hexdigest()
        idb=hashlib.sha256(b'EWGMAP02'+b'\x02'+cells).hexdigest()
        bridge=(ROOT/'src/platform/world_bridge.c').read_text()
        helpers='\n'.join(function(bridge,name) for name in ('WorldBridge_GeneratedCaveReady','CaveLine','CavePump'))
        global_h='''#include <stdint.h>\ntypedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int8_t s8;typedef int16_t s16;typedef int bool8;\n#define TRUE 1\n#define FALSE 0\n#define PLAYER_AVATAR_FLAG_ON_FOOT 1\nstruct WarpData {s8 mapGroup,mapNum,warpId;s16 x,y;};\nstruct MapLayout {int width,height;const u16 *border,*map;const void *primary,*secondary;};\nstruct Save {struct WarpData location,dynamicWarp;struct {s16 x,y;} pos;};\nextern struct Save *gSaveBlock1Ptr;extern struct {u32 vblankCounter1;} gMain;extern struct {int mapType;struct MapLayout *mapLayout;} gMapHeader;\n'''
        code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "global.h"
#include "platform/generated_map.h"
#include "platform/world_cave_wire.h"
struct Task {int isActive;};struct Task gTasks[16];
struct Save save,*gSaveBlock1Ptr=&save;__typeof__(gMain) gMain;__typeof__(gMapHeader) gMapHeader;
enum CaveState {CAVE_DISABLED,CAVE_IDLE,CAVE_WAIT,CAVE_WAIT_RESET,CAVE_ACK,CAVE_WAIT_OK,CAVE_READY,CAVE_MISMATCH,CAVE_RETURN_NONE};
static struct {bool8 connected,caveAvailable,staging,caveReturning,caveV2Probe;enum CaveState caveState;unsigned caveTimeout,caveRetry,snapshotAge;char caveExpected[65];struct WorldCaveWire caveWire;size_t outputSize;char output[4096];} sWorld;
static int leaving,disconnected;static struct WarpData destination;
const char *LinkTransport_TagPeer(void){return 0;}
const void *LinkTransport_PendingTag(void){return 0;}
const void *LinkTransport_PendingInvitation(void){return 0;}
struct WorldRallySnapshot{unsigned id;};
int WorldRally_HasReturn(void){return 0;}int WorldRally_GetSnapshot(struct WorldRallySnapshot *r){(void)r;return 0;}
int WorldBridge_Enabled(void){return 1;}int Platform_ReloadGeneratedMap(void){return 1;}
int IsMapTypeOutdoors(int x){return x==1;}int TestPlayerAvatarFlags(int f){return f==1;}
void PlayerGetDestCoords(s16 *x,s16 *y){*x=15;*y=16;}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){destination=(struct WarpData){g,n,w,x,y};}
void SetDynamicWarpWithCoords(int z,s8 g,s8 n,s8 w,s8 x,s8 y){(void)z;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void StoreInitialPlayerAvatarState(void){}void DoWarp(void){leaving++;}
static bool8 Ready(void){return TRUE;}
static void Flush(void){sWorld.outputSize=0;}
static void Disconnect(void){disconnected=1;sWorld.connected=0;}
''' + helpers + r'''
static void deliver(const char *id,char *profile){
 char *begin[]={"CAVE","BEGIN",(char *)id,profile};char *end[]={"CAVE","END",(char *)id};
 char row[32],idx[4];char *parts[]={"CAVE","ROW",(char *)id,idx,row};
 assert(CaveLine(4,begin));
 for(int y=0;y<31;y++){
  for(int x=0;x<31;x++)row[x]=(x==0||y==0||x==30||y==30)?'#':'.';
  row[31]=0;snprintf(idx,sizeof(idx),"%d",y);assert(CaveLine(5,parts));
 }
 assert(CaveLine(3,end));
}
int main(void){const char *a="ID_A",*b="ID_B";struct MapLayout base={19,26,0,0,0,0};
 gMapHeader.mapType=1;gMapHeader.mapLayout=&base;save.location=(struct WarpData){3,4,0,8,9};
 sWorld.connected=1;sWorld.caveAvailable=1;sWorld.caveV2Probe=1;sWorld.caveState=CAVE_WAIT;
 deliver(a,"1");assert(sWorld.caveState==CAVE_ACK);CavePump();assert(sWorld.caveState==CAVE_WAIT_OK);
 char *ok[]={"CAVE","OK",(char*)a};assert(CaveLine(3,ok));
 assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(GeneratedMap_EncounterProfile()==1);
 /* Same geometry with a different ecology is a different identity. It must
    leave the old cave before staging or acknowledging the replacement. */
 sWorld.caveState=CAVE_WAIT;WorldCaveWire_Reset(&sWorld.caveWire);deliver(b,"2");
 assert(sWorld.caveState==CAVE_MISMATCH && GeneratedMap_EncounterProfile()==1);
 CavePump();assert(sWorld.caveReturning && leaving==2);
 save.location=destination;GeneratedMap_ResolveLayout(&base);CavePump();
 assert(sWorld.caveState==CAVE_WAIT_OK);char *ok2[]={"CAVE","OK",(char*)b};assert(CaveLine(3,ok2));
 assert(GeneratedMap_Enter());save.location=destination;GeneratedMap_ResolveLayout(&base);
 assert(GeneratedMap_EncounterProfile()==2&&!disconnected);
 /* An unsupported profile response must not be accepted without v2 negotiation. */
 sWorld.caveState=CAVE_WAIT;sWorld.caveV2Probe=0;WorldCaveWire_Reset(&sWorld.caveWire);
 char *bad[]={"CAVE","BEGIN",(char*)a,"1"};assert(!CaveLine(4,bad));
 /* Legacy clients receiving NONE after an in-flight reset return safely. */
 sWorld.caveState=CAVE_WAIT_RESET;char *none[]={"CAVE","NONE"};
 assert(CaveLine(2,none)&&sWorld.caveState==CAVE_RETURN_NONE);
 return 0;}
'''.replace('ID_A',ida).replace('ID_B',idb)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'platform').mkdir();(p/'constants').mkdir();(p/'global.h').write_text('#ifndef G\n#define G\n'+global_h+'\n#endif\n')
            for name in ('main.h','overworld.h','field_screen_effect.h','field_player_avatar.h','fieldmap.h'):
                (p/name).write_text('#include "global.h"\nint IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void SetWarpDestination(s8,s8,s8,s8,s8);void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void PlayerGetDestCoords(s16*,s16*);void StoreInitialPlayerAvatarState(void);void DoWarp(void);\n#define MAP_OFFSET 7\n')
            (p/'task.h').write_text('struct Task {int isActive;}; extern struct Task gTasks[16];\n#define NUM_TASKS 16\n')
            (p/'platform/world_rally.h').write_text('struct WorldRallySnapshot{unsigned id;};int WorldRally_HasReturn(void);int WorldRally_GetSnapshot(struct WorldRallySnapshot *);\n')
            (p/'platform/link_transport.h').write_text('const char *LinkTransport_TagPeer(void);const void *LinkTransport_PendingTag(void);const void *LinkTransport_PendingInvitation(void);\n')
            (p/'platform/world_bridge.h').write_text('int WorldBridge_Enabled(void);int WorldBridge_GeneratedCaveReady(void);\n')
            for name in ('generated_map.h','world_cave_wire.h'):(p/'platform'/name).write_text((ROOT/'include/platform'/name).read_text())
            (p/'constants/maps.h').write_text(f'#define MAP_GENERATED_WORLD_CAVE ({group}<<8)\n#define MAP_GROUP(x) ((x)>>8)\n#define MAP_NUM(x) ((x)&255)\n#define WARP_ID_NONE (-1)\n')
            (p/'test.c').write_text(code)
            cmd=['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DGENERATED_MAP_READY=1','-DGENERATED_CAVE_PROFILES=1','-iquote',str(p),str(ROOT/'src/platform/generated_map.c'),str(ROOT/'src/platform/world_cave_wire.c'),str(p/'test.c'),'-o',str(p/'test')]
            build=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
