"""Compile the actual trade consumers, not a Python model of their checks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function(source, name):
    import re
    match = re.search(r"^(?:static )?(?:const char \*|void |bool8 )" + name + r"\([^;]*?\)\n\{", source, re.M)
    if not match:
        raise AssertionError(f"missing actual function {name}")
    end = match.end()
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


class TradePayloads(unittest.TestCase):
    def compile_run(self, names, prelude, main):
        source = (ROOT / 'src/trade.c').read_text()
        if 'static bool8 NativeTradeBlockSizeValid(' in source and 'NativeTradeBlockSizeValid' not in names:
            names = ['NativeTradeBlockSizeValid'] + names
        with tempfile.TemporaryDirectory(prefix='trade-payload-') as tmp:
            c = Path(tmp) / 'test.c'
            c.write_text(prelude + '\n' + '\n'.join(function(source, n) for n in names) + '\n' + main)
            exe = Path(tmp) / 'test'
            subprocess.run(['cc', '-std=gnu99', '-DPORTABLE', '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', '-g',
                            str(c), '-o', str(exe)], check=True, capture_output=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True,
                                    env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0',
                                         'UBSAN_OPTIONS': 'halt_on_error=1'})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_animation_teardown_retires_vblank_before_free(self):
        self.compile_run(['CB2_FreeTradeAnim'], COMMON + r'''
struct { int active; } gPaletteFade;
struct { void (*savedCallback)(void); } gMain;
int storage, *sTradeAnim=&storage, gWirelessCommType;
int released, frames, callbacks;
void (*vblank)(void);
void AnimationVBlank(void) { assert(!released && sTradeAnim); frames++; }
void SetVBlankCallback(void (*cb)(void)) { vblank=cb; }
void FreeAllWindowBuffers(void) { assert(!vblank); released++; }
void *GetBgTilemapBuffer(int bg) { return NULL; }
void Free(void *ptr) { assert(!vblank); }
void FreeMonSpritesGfx(void) { assert(!vblank); }
#define FREE_AND_SET_NULL(ptr) do { Free(ptr); (ptr)=NULL; } while(0)
void DestroyWirelessStatusIndicatorSprite(void) {}
void SetMainCallback2(void (*cb)(void)) { assert(cb==gMain.savedCallback); callbacks++; }
void RunTasks(void) {}
void AnimateSprites(void) {}
void BuildOamBuffer(void) {}
void UpdatePaletteFade(void) {}
''', r'''
int main(void) {
 for(int wireless=0;wireless<2;wireless++) {
  gWirelessCommType=wireless; sTradeAnim=&storage;
  released=frames=callbacks=0; vblank=AnimationVBlank;
  // The animation must keep rendering until the fade completes.
  gPaletteFade.active=1; CB2_FreeTradeAnim();
  assert(!released && !callbacks && vblank); vblank(); assert(frames==1);
  gPaletteFade.active=0; CB2_FreeTradeAnim();
  assert(released==1 && callbacks==1 && !sTradeAnim && !vblank);
  // Native SDL dispatches VBlank before running the next main callback.
  if(vblank) vblank();
 }
 return 0;
}
''')

    def test_own_phase_is_bounded_and_callback_gated(self):
        self.compile_run(['TradeMenu_Phase'], COMMON + r'''
enum { CB_MAIN_MENU, CB_SELECTED_MON, CB_CONFIRM_TRADE_PROMPT, CB_CANCEL_TRADE_PROMPT };
static void CB2_TradeMenu(void) {}
struct { void (*callback2)(void); } gMain;
struct { int callbackId; } menu, *sTradeMenu;
''', r'''
int main(void) {
 assert(!strcmp(TradeMenu_Phase(), "inactive"));
 sTradeMenu=&menu; assert(!strcmp(TradeMenu_Phase(), "inactive"));
 gMain.callback2=CB2_TradeMenu;
 const char *phases[]={"choosing","selected","confirm","cancel_confirm","busy"};
 for(int i=0;i<5;i++) { menu.callbackId=i; assert(!strcmp(TradeMenu_Phase(),phases[i])); }
 sTradeMenu=NULL; assert(!strcmp(TradeMenu_Phase(), "inactive"));
 return 0;
}
''')

    def test_remote_cursor_rejected_before_assignment(self):
        source = (ROOT / 'src/trade.c').read_text()
        helpers = ['NativeTradeReject', 'NativeTradeSelectionValid'] if 'static bool8 NativeTradeSelectionValid(' in source else []
        self.compile_run(helpers + ['SetSelectedMon', 'Leader_ReadLinkBuffer', 'Follower_ReadLinkBuffer'], COMMON + r'''
#define TRADE_PLAYER 0
#define TRADE_PARTNER 1
#define STATUS_CANCEL 2
#define STATUS_READY 1
#define PALETTES_ALL 0
#define RGB_BLACK 0
#define MSG_WAITING_FOR_FRIEND 0
#define MSG_FRIEND_WANTS_TO_TRADE 1
#define MSG_CANCELED 2
#define CB_INIT_EXIT_CANCELED_TRADE 0
#define CB_HANDLE_TRADE_CANCELED 1
#define CB_PRINT_IS_THIS_OKAY 2
#define CB_WAIT_TO_START_TRADE 3
enum { LINKCMD_REQUEST_CANCEL, LINKCMD_READY_TO_TRADE, LINKCMD_INIT_BLOCK,
LINKCMD_READY_CANCEL_TRADE, LINKCMD_BOTH_CANCEL_TRADE, LINKCMD_PARTNER_CANCEL_TRADE,
LINKCMD_SET_MONS_TO_TRADE, LINKCMD_START_TRADE, LINKCMD_PLAYER_CANCEL_TRADE };
struct { u8 partyCounts[2], cursorPosition, partnerCursorPosition;
u8 playerSelectStatus, partnerSelectStatus, playerConfirmStatus, partnerConfirmStatus;
u8 callbackId, drawSelectedMonState[2], selectedMonIdx[2]; } menu, *sTradeMenu=&menu;
u16 gBlockRecvBuffer[2][128];
int resets;
void TradeResetReceivedFlag(int n) { resets++; receivedSizes[n]=0; }
void BeginNormalPaletteFade(int a,int b,int c,int d,int e) {}
void PrintTradeMessage(int n) {}
void rbox_fill_rectangle(int n) {}
''', r'''
int main(void) {
 menu.partyCounts[0]=2; menu.partyCounts[1]=1;
 for(int len=0;len<=256;len++) {
  if(len==20) continue;
  for(int peer=0;peer<2;peer++) {
   receivedSizes[0]=receivedSizes[1]=20; receivedSizes[peer]=len;
   gBlockRecvBuffer[peer][0]=LINKCMD_REQUEST_CANCEL;
   menu.playerSelectStatus=menu.partnerSelectStatus=99;
   aborted=resets=0; Leader_ReadLinkBuffer(0,1<<peer);
   assert(aborted && !resets && menu.playerSelectStatus==99 && menu.partnerSelectStatus==99);
   gBlockRecvBuffer[0][0]=LINKCMD_START_TRADE; menu.callbackId=99;
   aborted=resets=0; Follower_ReadLinkBuffer(1,1<<peer);
   assert(aborted && !resets && menu.callbackId==99);
  }
 }
 receivedSizes[0]=receivedSizes[1]=20; aborted=resets=0;
 gBlockRecvBuffer[0][0]=LINKCMD_REQUEST_CANCEL; gBlockRecvBuffer[1][0]=LINKCMD_REQUEST_CANCEL;
 Leader_ReadLinkBuffer(0,3); assert(!aborted && resets==2);
 receivedSizes[0]=receivedSizes[1]=20;
 for (unsigned v=1;v<65536;v++) {
  aborted=0; menu.partnerCursorPosition=99; gBlockRecvBuffer[1][0]=LINKCMD_READY_TO_TRADE;
  gBlockRecvBuffer[1][1]=v; Leader_ReadLinkBuffer(0,2);
  assert(aborted && menu.partnerCursorPosition==99);
  aborted=0; gBlockRecvBuffer[0][0]=LINKCMD_SET_MONS_TO_TRADE; gBlockRecvBuffer[0][1]=v;
  Follower_ReadLinkBuffer(1,1); assert(aborted && menu.partnerCursorPosition==99);
 }
 aborted=0; gBlockRecvBuffer[0][1]=0; Follower_ReadLinkBuffer(1,1);
 assert(!aborted && menu.partnerCursorPosition==6 && menu.selectedMonIdx[1]==6);
 receivedSizes[0]=20;
 menu.cursorPosition=2; aborted=0; Follower_ReadLinkBuffer(1,1); assert(aborted);
 aborted=0; SetSelectedMon(255); assert(aborted);
 return 0;
}
''')

    def test_incoming_mon_metadata_and_checksum(self):
        self.compile_run(['NativeTradeMonValid'], COMMON + r'''
#define NUM_SPECIES 412
#define SPECIES_NONE 0
#define MAX_MON_MOVES 4
#define EOS 255
#define MOVES_COUNT 355
#define ITEMS_COUNT 377
#define MAX_LEVEL 100
#define LANGUAGE_JAPANESE 1
#define LANGUAGE_SPANISH 7
#define LANGUAGE_KOREAN 6
#define MON_DATA_SPECIES 0
#define MON_DATA_HELD_ITEM 1
#define MON_DATA_MOVE1 2
#define MON_DATA_EXP 6
#define MON_DATA_POKEBALL 9
#define LAST_BALL 12
#define MON_DATA_COOL_RIBBON 10
#define MON_DATA_TOUGH_RIBBON 14
struct Pokemon { struct { u32 personality, otId; u8 nickname[10], otName[7], language;
 u8 hasSpecies,isBadEgg; u16 checksum; struct { u32 raw[12]; } secure; } box;
 u32 status; u8 level, mail; u16 hp,maxHP; u32 fields[15]; };
u32 GetMonData(struct Pokemon *p,int f) { return p->fields[f]; }
''', r'''
int main(void) {
 struct Pokemon mon={0}; mon.fields[0]=1; mon.box.hasSpecies=1; mon.level=5; mon.mail=255; mon.box.language=2;
 assert(NativeTradeMonValid(&mon));
 mon.box.personality=0x12345678; mon.box.otId=0xabcdef01;
 for(int i=0;i<12;i++) mon.box.secure.raw[i]=mon.box.personality ^ mon.box.otId;
 assert(NativeTradeMonValid(&mon));
 mon.box.personality=mon.box.otId=0; memset(mon.box.secure.raw,0,sizeof(mon.box.secure.raw));
 mon.box.secure.raw[0]=1; assert(!NativeTradeMonValid(&mon)); mon.box.secure.raw[0]=0;
 mon.fields[0]=65535; assert(!NativeTradeMonValid(&mon)); mon.fields[0]=1;
 for(int f=1;f<6;f++) { mon.fields[f]=65535; assert(!NativeTradeMonValid(&mon)); mon.fields[f]=0; }
 mon.mail=100; assert(!NativeTradeMonValid(&mon)); mon.mail=255;
 mon.status=0x10000; assert(!NativeTradeMonValid(&mon)); mon.status=0;
 mon.level=101; assert(!NativeTradeMonValid(&mon)); mon.level=5;
 mon.box.language=255; assert(!NativeTradeMonValid(&mon)); mon.box.language=2;
 mon.box.nickname[0]=0xfc; assert(!NativeTradeMonValid(&mon)); mon.box.nickname[0]=0;
 mon.fields[6]=0xffffffff; assert(!NativeTradeMonValid(&mon)); mon.fields[6]=0;
 mon.fields[9]=15; assert(!NativeTradeMonValid(&mon)); mon.fields[9]=0;
 for(int f=10;f<=14;f++) { mon.fields[f]=7; assert(!NativeTradeMonValid(&mon)); mon.fields[f]=0; }
 return 0;
}
''')

    def test_incoming_mail_and_ribbon_indices(self):
        self.compile_run(['NativeTradeReject', 'NativeTradeAuxBlockValid'], COMMON + r'''
#define NUM_SPECIES 412
#define SPECIES_NONE 0
#define EOS 255
#define EC_EMPTY_WORD 65535
#define ITEM_NONE 0
#define MAX_GIFT_RIBBON 64
#define GIFT_RIBBONS_COUNT 11
struct Mail { u16 words[9]; u8 playerName[8]; u16 species,itemId; };
u16 gBlockRecvBuffer[2][128];
void Trade_Memcpy(void *d,const void *s,u32 n) { memcpy(d,s,n); }
bool8 ItemIsMail(u16 n) { return n>=121 && n<=132; }
bool8 IsBardWordInvalid(u16 n) { return n>500; }
u16 MailSpeciesToSpecies(u16 n,u16 *letter) { return n>=30000 && n<30028 ? 201 : n; }
''', r'''
int main(void) {
 struct Mail mails[6]={0}; mails[0].itemId=121; mails[0].species=1;
 receivedSizes[1]=220;
 memcpy(gBlockRecvBuffer[1],mails,sizeof(mails)); assert(NativeTradeAuxBlockValid(1,1));
 mails[0].species=65535; memcpy(gBlockRecvBuffer[1],mails,sizeof(mails));
 assert(!NativeTradeAuxBlockValid(1,1) && aborted);
 mails[0].species=30027; mails[0].words[0]=65535;
 memcpy(gBlockRecvBuffer[1],mails,sizeof(mails)); assert(NativeTradeAuxBlockValid(1,1));
 mails[0].itemId=65535; memcpy(gBlockRecvBuffer[1],mails,sizeof(mails)); assert(!NativeTradeAuxBlockValid(1,1));
 receivedSizes[1]=40;
 memset(gBlockRecvBuffer,0,sizeof(gBlockRecvBuffer)); assert(NativeTradeAuxBlockValid(1,0));
 ((u8*)gBlockRecvBuffer[1])[10]=64; assert(!NativeTradeAuxBlockValid(1,0));
 return 0;
}
''')

    def test_actual_block_consumer_does_not_publish_invalid_payload(self):
        self.compile_run(['Trade_Memcpy', 'NativeTradeReject', 'NativeTradeMonValid',
                          'NativeTradePartyBlockValid', 'NativeTradeAuxBlockValid', 'BufferTradeParties'], COMMON + r'''
#define NUM_SPECIES 412
#define SPECIES_NONE 0
#define SPECIES_SHEDINJA 303
#define MAX_MON_MOVES 4
#define EOS 255
#define MOVES_COUNT 355
#define ITEMS_COUNT 377
#define MAX_LEVEL 100
#define LANGUAGE_JAPANESE 1
#define LANGUAGE_SPANISH 7
#define MON_DATA_SPECIES 0
#define MON_DATA_HELD_ITEM 1
#define MON_DATA_MOVE1 2
#define MON_DATA_EXP 6
#define MON_DATA_POKEBALL 9
#define LAST_BALL 12
#define MON_DATA_COOL_RIBBON 10
#define MON_DATA_TOUGH_RIBBON 14
#define MON_DATA_LANGUAGE 7
#define MON_DATA_NICKNAME 8
#define POKEMON_NAME_LENGTH 10
#define EC_EMPTY_WORD 65535
#define ITEM_NONE 0
#define MAX_GIFT_RIBBON 64
#define GIFT_RIBBONS_COUNT 11
#define BLOCK_REQ_SIZE_200 1
#define BLOCK_REQ_SIZE_220 2
#define BLOCK_REQ_SIZE_40 3
struct Pokemon { struct { u32 personality, otId; u8 nickname[10], otName[7], language;
 u8 hasSpecies,isBadEgg; u16 checksum; struct { u32 raw[12]; } secure; } box;
 u32 status; u8 level,mail; u16 hp,maxHP; u32 fields[7]; };
struct Mail { u16 words[9]; u8 playerName[8]; u16 species,itemId; };
u32 GetMonData(struct Pokemon *p,int f,...) { return f<7 ? p->fields[f] : 0; }
void SetMonData(struct Pokemon *p,int f,const void *v) {}
u16 MailSpeciesToSpecies(u16 n,u16 *letter) { return n; }
bool8 ItemIsMail(u16 n) { return n>=121 && n<=132; }
bool8 IsBardWordInvalid(u16 n) { return n>500; }
struct Pokemon gPlayerParty[6],gEnemyParty[6]; struct Mail gTradeMail[6];
struct { struct Mail mail[6]; u32 extra; u8 giftRibbons[11]; } save,*gSaveBlock1Ptr=&save;
struct { u8 bufferPartyState,timer,giftRibbons[11]; } menu,*sTradeMenu=&menu;
u16 gBlockRecvBuffer[2][256],gBlockSendBuffer[256];
u8 sText_ShedinjaJP[1],gSpeciesNames[412][11];
int GetMultiplayerId(void) { return 0; }
int IsLinkTradeTaskFinished(void) { return 1; }
int _GetBlockReceivedStatus(void) { return 3; }
int resets;
void TradeResetReceivedFlags(void) { resets++; receivedSizes[0]=receivedSizes[1]=0; }
void RequestLinkData(int n) {}
int StringCompareWithoutExtCtrlCodes(const u8 *a,const u8 *b) { return 1; }
''', r'''
int main(void) {
 // The protocol carries fixed request sizes, not sizeof the copied subset.
 for (int state=4; state<=20; state+=4) {
  int expected=state<=12 ? 200 : state==16 ? 220 : 40;
  for (int len=0; len<=256; len++) {
   if (len==expected) continue;
   memset(gBlockRecvBuffer,0,sizeof(gBlockRecvBuffer));
   receivedSizes[0]=expected; receivedSizes[1]=len;
   memset(gEnemyParty,0x5a,sizeof(gEnemyParty));
   memset(gTradeMail,0x5a,sizeof(gTradeMail)); memset(menu.giftRibbons,0x5a,11);
   menu.bufferPartyState=state; aborted=resets=0;
   assert(!BufferTradeParties() && aborted && !resets && menu.bufferPartyState==state);
   const u8 *party=(const u8 *)gEnemyParty, *mail=(const u8 *)gTradeMail;
   for(unsigned i=0;i<sizeof(gEnemyParty);i++) assert(party[i]==0x5a);
   for(unsigned i=0;i<sizeof(gTradeMail);i++) assert(mail[i]==0x5a);
   for(int i=0;i<11;i++) assert(menu.giftRibbons[i]==0x5a);
  }
  memset(gBlockRecvBuffer,0,sizeof(gBlockRecvBuffer));
  receivedSizes[0]=receivedSizes[1]=expected;
  menu.bufferPartyState=state; aborted=resets=0;
  assert(!BufferTradeParties() && !aborted && resets==1 && menu.bufferPartyState==state+1);
 }
 struct Pokemon pair[2]={0}; pair[0].fields[0]=1; pair[0].box.hasSpecies=1;
 pair[0].box.language=2; pair[0].level=5; pair[0].mail=255;
 for(int state=4;state<=12;state+=4) {
  receivedSizes[0]=receivedSizes[1]=200;
  memcpy(gBlockRecvBuffer[1],pair,sizeof(pair)); menu.bufferPartyState=state; aborted=0;
  assert(!BufferTradeParties() && !aborted && menu.bufferPartyState==state+1);
  memset(gEnemyParty,0x5a,sizeof(gEnemyParty)); struct Pokemon before[6]; memcpy(before,gEnemyParty,sizeof(before));
  receivedSizes[1]=200;
  pair[0].fields[0]=65535; memcpy(gBlockRecvBuffer[1],pair,sizeof(pair)); menu.bufferPartyState=state;
  assert(!BufferTradeParties() && aborted && menu.bufferPartyState==state);
  assert(!memcmp(before,gEnemyParty,sizeof(before))); pair[0].fields[0]=1;
 }
 receivedSizes[1]=220;
 memset(gBlockRecvBuffer,0,sizeof(gBlockRecvBuffer)); menu.bufferPartyState=16; aborted=0;
 ((struct Mail*)gBlockRecvBuffer[1])[0].itemId=65535;
 memset(gTradeMail,0x5a,sizeof(gTradeMail)); struct Mail before[6]; memcpy(before,gTradeMail,sizeof(before));
 assert(!BufferTradeParties() && aborted && !memcmp(before,gTradeMail,sizeof(before)));
 receivedSizes[1]=40;
 memset(gBlockRecvBuffer,0,sizeof(gBlockRecvBuffer)); menu.bufferPartyState=20; aborted=0;
 ((u8*)gBlockRecvBuffer[1])[0]=255; memset(menu.giftRibbons,0x5a,11);
 assert(!BufferTradeParties() && aborted && menu.giftRibbons[0]==0x5a);
 return 0;
}
''')

    def test_finish_commands_validate_length_before_state_or_reset(self):
        self.compile_run(['HandleLinkDataReceive'], COMMON + r'''
#define LINKCMD_CONFIRM_FINISH_TRADE 1
#define LINKCMD_READY_FINISH_TRADE 2
#define STATUS_READY 1
u16 gBlockRecvBuffer[2][128];
struct { int playerFinishStatus,partnerFinishStatus; } anim,*sTradeAnim=&anim;
int recvStatus,resets,callbacks;
void TradeGetMultiplayerId(void) {}
u8 GetBlockReceivedStatus(void) { return recvStatus; }
void CB2_TryLinkTradeEvolution(void) {}
void SetMainCallback2(void (*cb)(void)) { callbacks++; }
void ResetBlockReceivedFlag(int peer) { resets++; receivedSizes[peer]=0; }
''', r'''
int main(void) {
 for(int peer=0;peer<2;peer++) {
  for(int len=0;len<=256;len++) {
   recvStatus=1<<peer; receivedSizes[peer]=len;
   gBlockRecvBuffer[peer][0]=LINKCMD_READY_FINISH_TRADE;
   anim.playerFinishStatus=anim.partnerFinishStatus=99;
   aborted=resets=callbacks=0; HandleLinkDataReceive();
   if(len==20) {
    assert(!aborted && resets==1);
    assert((peer ? anim.partnerFinishStatus : anim.playerFinishStatus)==STATUS_READY);
   } else {
    assert(aborted && !resets && !callbacks);
    assert(anim.playerFinishStatus==99 && anim.partnerFinishStatus==99);
   }
  }
 }
 recvStatus=1; receivedSizes[0]=20; aborted=resets=callbacks=0;
 gBlockRecvBuffer[0][0]=LINKCMD_CONFIRM_FINISH_TRADE;
 HandleLinkDataReceive(); assert(!aborted && resets==1 && callbacks==1);
 // Absent flags do not consume or validate stale buffer data.
 recvStatus=0; receivedSizes[0]=receivedSizes[1]=0; aborted=resets=sizeReads=0;
 HandleLinkDataReceive(); assert(!aborted && !resets && !sizeReads);
 // Cable-only metadata is not consulted by non-native/wireless paths.
 active=0; recvStatus=3; aborted=resets=sizeReads=0;
 HandleLinkDataReceive(); assert(!aborted && resets==2 && !sizeReads);
 return 0;
}
''')

    def test_swap_rejects_mail_and_slots_before_mutation(self):
        self.compile_run(['TradeMons'], COMMON + r'''
#define MON_DATA_MAIL 1
#define MON_DATA_IS_EGG 2
#define MON_DATA_FRIENDSHIP 3
#define SWAP(a,b,t) do { (t)=(a); (a)=(b); (b)=(t); } while (0)
struct Pokemon { unsigned mail, marker; };
struct Mail { unsigned marker; };
struct Pokemon gPlayerParty[6], gEnemyParty[6];
struct Mail gTradeMail[6];
struct { struct Mail mail[20]; } save, *gSaveBlock1Ptr=&save;
struct { struct Pokemon tempMon; } anim, *sTradeAnim=&anim;
int gReceivedRemoteLinkPlayers, reads, writes;
int gPlayerPartyCount=1,gEnemyPartyCount=1;
unsigned GetMonData(struct Pokemon *p, int f) { reads++; return f==1 ? p->mail : 0; }
void SetMonData(struct Pokemon *p,int f,void *v) { writes++; }
void ClearMail(struct Mail *p) { writes++; p->marker=0; }
void GiveMailToMon(struct Pokemon *p, struct Mail *m) { writes++; save.mail[0]=*m; }
void UpdatePokedexForReceivedMon(int n) { writes++; }
void TryEnableNationalDexFromLinkPartner(void) {}
''' , r'''
int main(void) {
 gPlayerParty[0]=(struct Pokemon){255,10}; gEnemyParty[0]=(struct Pokemon){255,20};
 TradeMons(0,0); assert(!aborted && gPlayerParty[0].marker==20);
 for (int m=6;m<255;m++) {
  writes=reads=aborted=0; gEnemyParty[0].mail=m;
  TradeMons(0,0); assert(aborted && !writes);
 }
 aborted=reads=writes=0; TradeMons(6,0); assert(aborted && !reads && !writes);
 aborted=reads=writes=0; TradeMons(0,255); assert(aborted && !reads && !writes);
 aborted=reads=writes=0; TradeMons(1,0); assert(aborted && !reads && !writes);
 aborted=reads=writes=0; TradeMons(0,1); assert(aborted && !reads && !writes);
 aborted=writes=0; gEnemyParty[0].mail=255; gPlayerParty[0].mail=6;
 TradeMons(0,0); assert(aborted && !writes);
 gPlayerParty[0].mail=255; gEnemyParty[0].mail=5; aborted=writes=0;
 TradeMons(0,0); assert(!aborted && writes);
 return 0;
}
''')


COMMON = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define MAIL_NONE 255
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
int active=1, aborted, gLinkErrorOccurred;
u16 receivedSizes[2] = {20, 20};
int sizeReads;
u16 GetBlockReceivedSize(u8 peer) { sizeReads++; return receivedSizes[peer]; }
int NativeLink_IsActive(void) { return active; }
void NativeLink_Abort(void) { aborted++; }
static bool8 NativeTradeReject(void);
'''

if __name__ == '__main__':
    unittest.main()
