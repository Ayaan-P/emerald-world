"""Compile the production virtual cable in isolation, without a simulated game."""
import pathlib
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

class NativeLinkTests(unittest.TestCase):
    def run_c(self, body):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / 'test.c').write_text('#include "platform/native_link.h"\n#include <assert.h>\n#include <string.h>\n' + body)
            cmd = [os.environ.get('CC', 'cc'), '-std=c99', '-Wall', '-Wextra', '-Werror', '-DPORTABLE', '-I'+str(ROOT/'include'), str(p/'test.c'), str(ROOT/'src/platform/native_link.c'), '-o', str(p/'test')] + shlex.split(os.environ.get('NATIVE_LINK_CFLAGS', ''))
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(p/'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_repeated_abort_keeps_backpressured_terminal_event(self):
        self.run_c('''
static unsigned count; static int blocked=1;
static int emit(void *c,const struct NativeLinkEvent *e) {
 (void)c;assert(e->session==70);assert(e->kind==NATIVE_LINK_ABORT);
 if(blocked)return 0;
 count++;return 1;
}
int main(void) {
 NativeLink_Init(emit,0);assert(NativeLink_Admit(70,NATIVE_LINK_TRADE,1));
 NativeLink_Abort();NativeLink_Abort();NativeLink_Reset();
 assert(!NativeLink_Admit(71,NATIVE_LINK_TRADE,1));
 blocked=0;NativeLink_Pump();assert(count==1);
 assert(NativeLink_Admit(71,NATIVE_LINK_TRADE,1));return 0;
}''')

    def test_graceful_close_waits_for_queued_commands_and_echoes(self):
        self.run_c('''
static struct NativeLinkEvent last;
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;last=*e;return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=0;
 NativeLink_Init(emit,0);assert(NativeLink_Admit(72,NATIVE_LINK_TRADE,1));
 NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,72,1,0,m)==1);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,72,1,0,m)==1);
 send[0]=0x8888;send[1]=123;
 assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);NativeLink_AfterFrame();
 assert(NativeLink_SendQueueCount()==1);
 assert(!NativeLink_TryClose());assert(NativeLink_IsOpen());
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,72,1,0,m)==1);
 memset(send,0,sizeof(send));assert(NativeLink_BeforeFrame(send));
 assert(last.kind==NATIVE_LINK_COMMAND && last.command[1]==123);
 NativeLink_Main1(&a,send,r);NativeLink_AfterFrame();
 assert(!NativeLink_TryClose());
 m[1][0]=0x8888;m[1][1]=123;
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,72,1,1,m)==1);
 assert(!NativeLink_TryClose()); /* Receive must reach the engine too. */
 assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);
 assert(r[1][1]==123);NativeLink_AfterFrame();
 assert(NativeLink_TryClose());assert(last.kind==NATIVE_LINK_CLOSE);
 assert(NativeLink_IsActive() && !NativeLink_IsOpen());return 0;
}''')

    def test_authoritative_end_is_session_scoped_and_does_not_echo(self):
        self.run_c('''
static int calls;
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;calls++;return 0;}
int main(void) {
 NativeLink_Init(emit,0);assert(NativeLink_Admit(73,NATIVE_LINK_TRADE,1));
 NativeLink_Open(0x2233);assert(calls==1);
 NativeLink_EndSession(72);assert(NativeLink_IsActive());
 NativeLink_Pump();assert(calls==2);
 NativeLink_EndSession(73);assert(!NativeLink_IsActive());
 NativeLink_Pump();assert(calls==2);
 assert(NativeLink_Admit(74,NATIVE_LINK_TRADE,1));NativeLink_Abort();
 assert(!NativeLink_Admit(75,NATIVE_LINK_TRADE,1));
 NativeLink_EndSession(73);assert(!NativeLink_Admit(75,NATIVE_LINK_TRADE,1));
 NativeLink_EndSession(74);assert(NativeLink_Admit(75,NATIVE_LINK_TRADE,1));
 return 0;
}''')

    def test_disabled_and_consent(self):
        self.run_c('''
static int emit(void *ctx, const struct NativeLinkEvent *e) { (void)ctx; (void)e; return 1; }
int main(void) {
 NativeLink_Init(emit, 0);
 assert(!NativeLink_IsActive()); assert(NativeLink_FrameReady());
 assert(!NativeLink_Admit(0, NATIVE_LINK_SINGLE, 0));
 assert(!NativeLink_Admit(1, NATIVE_LINK_SINGLE, 2));
 assert(NativeLink_Admit(1, NATIVE_LINK_SINGLE, 0));
 assert(NativeLink_IsActive()); assert(NativeLink_FrameReady());
 NativeLink_Reset(); assert(!NativeLink_IsActive());
 return 0;
}''')

    def test_native_pump_is_not_stub(self):
        link = (ROOT/'src/link.c').read_text()
        stub = (ROOT/'src/stub.c').read_text()
        self.assertNotIn('STUB_FUNC_QUIET_BLOCK(bool8 HandleLinkConnection()', stub)
        for hook in ['NativeLink_Open(gLinkType)', 'NativeLink_Close()', 'NativeLink_Main1(', 'NativeLink_IsActive()', 'NativeLink_LocalId()', 'NativeLink_Abort()']:
            self.assertIn(hook, link)
        self.assertIn('gRecvCmds[i][1] >= ARRAY_COUNT(sBlockRequests)', link)
        self.assertIn('sBlockRecv[i].pos + 14 > BLOCK_BUFFER_SIZE', link)

    def test_round_handshake_backpressure_and_generations(self):
        self.run_c('''
static struct NativeLinkEvent last;
static int blocked, calls;
static int emit(void *ctx, const struct NativeLinkEvent *e) {
 (void)ctx; last=*e; calls++; return !blocked;
}
int main(void) {
 uint16_t send[8]={0}, matrix[2][8]={{0}}, recv[5][8]; uint8_t advance=1;
 NativeLink_Init(emit,0); NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(7,NATIVE_LINK_SINGLE,0));
 NativeLink_Open(0x2233); assert(last.kind==NATIVE_LINK_OPEN);
 assert(last.generation==1); assert(NativeLink_FrameReady());
 assert(!NativeLink_IsConnected());
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,7,1,0,matrix)==1);
 assert(NativeLink_FrameReady()); assert(last.kind==NATIVE_LINK_COMMAND);
 assert(last.round==0); assert(NativeLink_SendQueueCount()==0);
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,7,1,0,matrix)==1);
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,7,1,0,matrix)==1);
 assert(NativeLink_FrameReady()); assert(NativeLink_BeforeFrame(send));
 memset(recv,0xff,sizeof(recv));
 assert(!(NativeLink_Main1(&advance,send,recv)&0x40));
 assert(advance==0); assert(last.kind==NATIVE_LINK_ADVANCE);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,7,1,0,matrix)==1);
 NativeLink_AfterFrame();
 send[0]=0x2222; send[1]=0x2233; blocked=1;
 assert(NativeLink_BeforeFrame(send)); assert(last.round==1);
 send[1]=123; NativeLink_Pump(); assert(last.command[1]==0x2233);
 NativeLink_AfterFrame(); memset(send,0,sizeof(send));
 blocked=0; NativeLink_Pump();
 matrix[0][0]=0x2222; matrix[0][1]=0x2233;
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,7,1,1,matrix)==1);
 assert(NativeLink_FrameReady()); assert(NativeLink_BeforeFrame(send));
 assert(NativeLink_Main1(&advance,send,recv)&0x40);
 assert(!memcmp(recv,matrix,sizeof(matrix)));
 for(int i=2;i<5;i++) for(int j=0;j<8;j++) assert(recv[i][j]==0);
 NativeLink_AfterFrame();
 NativeLink_Close(); assert(NativeLink_IsActive()); assert(!NativeLink_IsOpen());
 NativeLink_Open(0x2233); assert(NativeLink_Generation()==2);
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,7,1,1,matrix)==0);
 NativeLink_Abort(); assert(!NativeLink_IsActive()); assert(NativeLink_FrameReady());
 assert(calls>4); return 0;
}''')

    def test_consumed_round_is_not_a_hardware_queue_backlog(self):
        # The native engine's close/standby callbacks wait for queue counts of
        # zero AFTER LinkMain1 dequeues the current round. Retained replay/echo
        # bookkeeping must not report that already-delivered round as queued.
        self.run_c('''
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},recv[5][8]; uint8_t advance=0;
 NativeLink_Init(emit,0); NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(77,NATIVE_LINK_SINGLE,1)); NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,77,1,0,m)==1);
 assert(NativeLink_FrameReady());
 assert(NativeLink_SendQueueCount()==0);
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,77,1,0,m)==1);
 assert(NativeLink_RecvQueueCount()==0);
 assert(NativeLink_BeforeFrame(send));
 NativeLink_Main1(&advance,send,recv);
 assert(NativeLink_RecvQueueCount()==0);
 assert(NativeLink_SendQueueCount()==0);
 NativeLink_AfterFrame();
 return 0;
}''')

    def test_early_advance_survives_until_pair(self):
        self.run_c('''
static int advances;
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c; if(e->kind==NATIVE_LINK_ADVANCE) advances++; return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8]; uint8_t a=1;
 NativeLink_Init(emit,0); NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(9,NATIVE_LINK_DOUBLE,0)); NativeLink_Open(0x2244);
 NativeLink_Main1(&a,send,r); assert(a==1);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,9,1,0,m)==1);
 assert(NativeLink_FrameReady());
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,9,1,0,m)==1);
 assert(NativeLink_BeforeFrame(send)); NativeLink_Main1(&a,send,r);
 assert(advances==1); assert(a==0);
 return 0;
}''')

    def test_bootstrap_is_defined_zero_not_initlink_sentinel(self):
        self.run_c('''
static struct NativeLinkEvent e;
static int emit(void *c,const struct NativeLinkEvent *v) {(void)c;e=*v;return 1;}
int main(void) {
 uint16_t send[8],m[2][8]={{0}}; for(int i=0;i<8;i++)send[i]=0xefff;
 NativeLink_Init(emit,0); NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(11,NATIVE_LINK_SINGLE,0)); NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,11,1,0,m)==1);
 assert(NativeLink_FrameReady());
 for(int i=0;i<8;i++)assert(e.command[i]==0);
 return 0;
}''')

    def test_native_receive_engine_bounds_and_real_player_exchange(self):
        # Compile the real function bodies, not a Python replica of the engine.
        source = (ROOT/'src/link.c').read_text()
        def function(signature):
            start = source.index(signature + '\n{')
            end = source.index('\n}', start) + 2
            return source[start:end]
        types = '''
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef u8 bool8;
#define PLAYER_NAME_LENGTH 7
#include "link.h"
#define TRUE 1
#define FALSE 0
#define EOS 255
#define VERSION_RUBY 1
#define VERSION_SAPPHIRE 2
#define VERSION_EMERALD 3
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
struct BlockTransfer { u16 pos,size; const u8 *src; bool8 active; u8 multiplayerId; };
static struct BlockTransfer sBlockRecv[4];
static bool8 sNativePlayerExchangeRequested;
static u16 gRecvCmds[5][8],gLinkPartnersHeldKeys[6],gBlockRecvBuffer[5][128];
static u8 gDecompressionBuffer[4096];
static bool8 gRemoteLinkPlayersNotReceived[4],gReceivedRemoteLinkPlayers,gLinkErrorOccurred;
static bool8 gReadyToCloseLink[4],gReadyToExitStandby[4],gLinkDummy2;
static u16 gLinkType=0x2233;
static struct LinkPlayer gLocalLinkPlayer,gLinkPlayers[5];
static struct LinkPlayerBlock gLocalLinkPlayerBlock;
static const char sASCIIGameFreakInc[]="GameFreak inc.";
static struct { const void *address; unsigned size; } sBlockRequests[5];
static unsigned receivedMask;
static int GetLinkPlayerCount_2(void) { return 2; }
static void InitLocalLinkPlayer(void) {}
static int InitBlockSend(const void *p,unsigned n) {(void)p;(void)n;return 1;}
static void ConvertLinkPlayerName(struct LinkPlayer *p) {(void)p;}
static void CB2_LinkError(void) {}
static void SetMainCallback2(void (*f)(void)) {(void)f;assert(0);}
static void SetBlockReceivedFlag(u8 i) { receivedMask |= 1u<<i; }
static void SetBerryBlenderLinkCallback(void) {}
static void SendBlock(int i,const void *p,unsigned n) {(void)i;(void)p;(void)n;}
'''
        header = (ROOT/'include/link.h').read_text().split('extern ', 1)[0] + '\n#endif\n'
        types = types.replace('#include "link.h"', header).replace('typedef u8 bool8;', 'typedef u8 bool8; typedef int8_t s8;')
        body = types + function('static void HandleReceiveRemoteLinkPlayer(u8 who)') + '\n' + function('static void ProcessRecvCmds(u8 unused)').replace('u16 i;', 'u16 i; (void)unused;', 1)
        body += '''
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;return 1;}
static void init(void) {
 NativeLink_Init(emit,0); assert(NativeLink_Admit(42,NATIVE_LINK_SINGLE,0));
 memset(gRecvCmds,0,sizeof(gRecvCmds)); memset(sBlockRecv,0,sizeof(sBlockRecv));
 memset(gRemoteLinkPlayersNotReceived,1,sizeof(gRemoteLinkPlayersNotReceived));
 gReceivedRemoteLinkPlayers=0; gLinkErrorOccurred=0; sNativePlayerExchangeRequested=1;
}
int main(void) {
 init(); gRecvCmds[0][0]=LINKCMD_CONT_BLOCK; ProcessRecvCmds(0);
 assert(!NativeLink_IsActive() && gLinkErrorOccurred);
 init(); gRecvCmds[0][0]=LINKCMD_INIT_BLOCK;gRecvCmds[0][1]=256;gRecvCmds[0][2]=0x80;
 ProcessRecvCmds(0);assert(!NativeLink_IsActive());
 init(); gRemoteLinkPlayersNotReceived[0]=0; gReceivedRemoteLinkPlayers=1;
 gRecvCmds[0][0]=LINKCMD_SEND_BLOCK_REQ;gRecvCmds[0][1]=65535;
 ProcessRecvCmds(0);assert(!NativeLink_IsActive());
 init();
 for(unsigned slot=0;slot<2;slot++) {
  struct LinkPlayerBlock block; memset(&block,0,sizeof(block));
  memcpy(block.magic1,sASCIIGameFreakInc,sizeof(sASCIIGameFreakInc));
  memcpy(block.magic2,sASCIIGameFreakInc,sizeof(sASCIIGameFreakInc));
  block.linkPlayer.version=3;block.linkPlayer.language=2;
  block.linkPlayer.trainerId=100+slot;block.linkPlayer.name[0]=EOS;
  memset(gRecvCmds,0,sizeof(gRecvCmds));
  gRecvCmds[slot][0]=LINKCMD_INIT_BLOCK;gRecvCmds[slot][1]=sizeof(block);gRecvCmds[slot][2]=0x80+slot;
  ProcessRecvCmds(0);assert(NativeLink_IsActive());
  for(unsigned off=0;off<sizeof(block);off+=14) {
   unsigned char data[14]={0}; unsigned n=sizeof(block)-off;if(n>14)n=14;
   memcpy(data,(unsigned char*)&block+off,n);
   gRecvCmds[slot][0]=LINKCMD_CONT_BLOCK;
   for(unsigned j=0;j<7;j++)gRecvCmds[slot][j+1]=data[2*j]|data[2*j+1]<<8;
   ProcessRecvCmds(0);assert(NativeLink_IsActive());
  }
 }
 assert(gReceivedRemoteLinkPlayers==1);
 assert(gLinkPlayers[0].trainerId==100 && gLinkPlayers[1].trainerId==101);
 assert(!receivedMask);
 return 0;
}'''
        self.run_c(body)

    def test_completed_block_size_accessor_rejects_stale_and_partial_data(self):
        source = (ROOT/'src/link.c').read_text()
        start = source.index('u16 GetBlockReceivedSize(u8 who)\n{')
        end = source.index('\n}', start) + 2
        self.run_c('''
 typedef uint8_t u8; typedef uint16_t u16;
 #define MAX_LINK_PLAYERS 4
 #define BLOCK_BUFFER_SIZE 256
 static struct {u16 size, pos; int active;} sBlockRecv[4];
 static int gWirelessCommType, gBlockReceivedStatus[4];
 ''' + source[start:end] + '''
 int main(void) {
  assert(GetBlockReceivedSize(255)==0);
  sBlockRecv[0].size=200; sBlockRecv[0].pos=210;
  assert(GetBlockReceivedSize(0)==0);
  gBlockReceivedStatus[0]=1;
  assert(GetBlockReceivedSize(0)==200);
  sBlockRecv[0].active=1; assert(GetBlockReceivedSize(0)==0);
  sBlockRecv[0].active=0; sBlockRecv[0].pos=196;
  assert(GetBlockReceivedSize(0)==0);
  sBlockRecv[0].pos=210; gWirelessCommType=1;
  assert(GetBlockReceivedSize(0)==0);
  gWirelessCommType=0; sBlockRecv[0].size=257;
  assert(GetBlockReceivedSize(0)==0);
  sBlockRecv[0].size=0; assert(GetBlockReceivedSize(0)==0);
  return 0;
 }''')

    def test_prehandshake_nonzero_commands_abort(self):
        self.run_c('''
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}};
 NativeLink_Init(emit,0); NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(13,NATIVE_LINK_SINGLE,0)); NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,13,1,0,m)==1);assert(NativeLink_FrameReady());
 m[1][0]=0xbbbb;m[1][1]=60;m[1][2]=0x81;
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,13,1,0,m)==-1);
 assert(!NativeLink_IsActive());return 0;
}''')

    def test_control_fifo_exhaustion_cancel_and_future_generation(self):
        self.run_c('''
static int blocked=1; static unsigned kinds[20],count;
static int emit(void *c,const struct NativeLinkEvent *e) {
 (void)c;if(blocked)return 0;kinds[count++]=e->kind;return 1;
}
int main(void) {
 uint16_t m[2][8]={{0}};
 NativeLink_Init(emit,0);assert(NativeLink_Admit(14,NATIVE_LINK_TRADE,0));
 NativeLink_Open(0x1111);NativeLink_Close();NativeLink_Open(0x1111);
 assert(NativeLink_Generation()==2);blocked=0;NativeLink_Pump();
 assert(count==3 && kinds[0]==NATIVE_LINK_OPEN && kinds[1]==NATIVE_LINK_CLOSE && kinds[2]==NATIVE_LINK_OPEN);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,14,1,0,m)==0);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,14,3,0,m)==-1);
 blocked=1;assert(NativeLink_Admit(15,NATIVE_LINK_TRADE,1));
 for(int i=0;i<5;i++){NativeLink_Open(0x1111);NativeLink_Close();}
 assert(!NativeLink_IsActive());assert(!NativeLink_Admit(16,NATIVE_LINK_SINGLE,0));
 blocked=0;NativeLink_Pump();assert(kinds[count-1]==NATIVE_LINK_ABORT);
 assert(NativeLink_Admit(16,NATIVE_LINK_SINGLE,0));NativeLink_Reset();
 assert(!NativeLink_IsActive());return 0;
}''')

    def test_handshake_cancel_and_duplicate_conflict(self):
        self.run_c('''
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=2;
 NativeLink_Init(emit,0);NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(17,NATIVE_LINK_SINGLE,0));NativeLink_Open(0x2233);
 NativeLink_Main1(&a,send,r);assert(!NativeLink_IsActive());assert(a==0);
 assert(NativeLink_Admit(18,NATIVE_LINK_SINGLE,0));NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,18,1,0,m)==1);
 assert(NativeLink_BeforeFrame(send));NativeLink_AfterFrame();
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,18,1,0,m)==1);
 assert(NativeLink_BeforeFrame(send)); a=1;NativeLink_Main1(&a,send,r);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,18,1,0,m)==1);NativeLink_AfterFrame();
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,18,1,0,m)==1);
 m[1][0]=1;assert(NativeLink_Feed(NATIVE_LINK_ROUND,18,1,0,m)==-1);
 assert(!NativeLink_IsActive());return 0;
}''')

    def test_host_advance_control_round_is_zero_after_lobby_ticks(self):
        self.run_c('''
static struct NativeLinkEvent event;
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;event=*e;return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=0;
 NativeLink_Init(emit,0);NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(19,NATIVE_LINK_SINGLE,0));NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,19,1,0,m)==1);
 for(unsigned round=0;round<5;round++) {
  assert(NativeLink_FrameReady());assert(event.round==round);
  assert(NativeLink_Feed(NATIVE_LINK_ROUND,19,1,round,m)==1);
  assert(NativeLink_BeforeFrame(send));a=round==4?1:0;
  NativeLink_Main1(&a,send,r);NativeLink_AfterFrame();
 }
 assert(event.kind==NATIVE_LINK_ADVANCE && event.round==0);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,19,1,0,m)==1);
 assert(NativeLink_IsConnected());return 0;
}''')

    def test_protocol_conflict_aborts(self):
        self.run_c('''
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;return 1;}
int main(void) {
 uint16_t send[8]={0}, m[2][8]={{0}};
 NativeLink_Init(emit,0); NativeLink_SetCommandSource(send);
 assert(NativeLink_Admit(2,NATIVE_LINK_TRADE,1)); NativeLink_Open(0x1111);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,2,1,0,m)==1);
 assert(NativeLink_FrameReady());
 m[1][0]=123;
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,2,1,0,m)==-1);
 assert(!NativeLink_IsActive());
 return 0;
}''')

if __name__ == '__main__':
    unittest.main()
