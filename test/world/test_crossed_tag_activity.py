"""Run the production activity update for a crossed, fragmented tag offer.

This component test does not launch the native game. Window and engine services
are fixtures. The activity state machine is extracted unchanged from production.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from test.world.test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]
PREAMBLE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint8_t bool8; typedef int8_t s8;
#define MENU_NOTHING_CHOSEN -2
static int menuChoice, accepted, acceptOk = 1;
static int Menu_ProcessInputNoWrap(void) {return menuChoice;}
#define TradeStorageFieldReady() 0
#define TradeStorageLocation(group,num) 0
#define ScriptContext_SetupScript(script) assert(0)
#define LinkTransport_TagEnd() assert(0)
#define LinkTransport_TagOffer(peer) 0
#define LinkTransport_Accept(id) 0
static int LinkTransport_TagAccept(uint64_t id) {assert(id==100);if(acceptOk)++accepted;return acceptOk;}
typedef void (*MainCallback)(void);
#define TRUE 1
#define FALSE 0
#define WINDOW_NONE 255
#define TASK_NONE 255
#define NATIVE_LINK_COOP 4
#define NATIVE_LINK_SINGLE 1
#define NATIVE_LINK_DOUBLE 2
#define NATIVE_LINK_TRADE 3
#define LINKTYPE_TRADE_SETUP 1
#define LINKTYPE_DOUBLE_BATTLE 2
#define LINKTYPE_SINGLE_BATTLE 3
#define USING_TRADE_CENTER 1
#define TRADE_PLAYER 0
#define TRADE_PARTNER 1
struct LinkTransportInvitation { uint64_t id; unsigned mode; char name[25]; };
static struct LinkTransportInvitation incoming;
static unsigned shown, closed, rejected, ready = 1, partyReady = 1, showOk = 1, outgoing = 1;
static int native, privateRewards;
static int WorldCoop_IsPrivateRewards(void) {return privateRewards;}
static void CB2_ReturnToFieldFromMultiplayer(void) {}
static struct { MainCallback callback2; } gMain;
static unsigned gWirelessCommType, gLinkType, gFieldLinkPlayerCount, gLocalLinkPlayerId;
static unsigned gReceivedRemoteLinkPlayers, gBattleTypeFlags, gSpecialVar_0x8004;
static unsigned gSelectedTradeMonPositions[2];
static int NativeLink_IsActive(void) {return native;}
static void DexNavNative_PrepareNativeActivity(bool8 preserveEncounter) {(void)preserveEncounter;}
static unsigned LinkTransport_Mode(void) {return 0;}
static const char *LinkTransport_TagPeer(void) {return NULL;}
static int FieldReady(void) {return ready;}
static int ActivityPartyReady(unsigned mode) {(void)mode;return partyReady;}
static const struct LinkTransportInvitation *LinkTransport_PendingTag(void) {return incoming.id?&incoming:NULL;}
static const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void) {return NULL;}
static int LinkTransport_TagReject(uint64_t id) {assert(id==incoming.id);++rejected;incoming.id=0;return 1;}
static int LinkTransport_Ready(void) {return 1;}
static int LinkTransport_TagOfferPending(void) {return outgoing;}
static int WorldActivity_IsEncounterPending(void) {return 0;}
static int LinkTransport_TagInRange(void) {return 0;}
static int LinkTransport_OfferPending(void) {return 0;}
static int LinkTransport_Offer(const char *s,unsigned m) {(void)s;(void)m;assert(0);return 0;}
static int LinkTransport_Reject(uint64_t id) {(void)id;assert(0);return 0;}
#define LockPlayerFieldControls() assert(0)
#define FreezeObjectEvents() assert(0)
#define StopPlayerAvatar() assert(0)
#define OpenLink() assert(0)
#define ResetLinkPlayers() assert(0)
#define HasLinkErrorOccurred() 0
#define GetLinkPlayerCount_2() 0
#define IsLinkMaster() 0
#define CheckShouldAdvanceLinkState() assert(0)
#define IsLinkPlayerDataExchangeComplete() 0
#define GetMultiplayerId() 0
#define SaveLinkPlayers(n) assert(0)
#define SetDynamicWarp(a,b,c,d) assert(0)
#define ClearLinkCallback_2() assert(0)
#define LinkTransport_CoopOwner() 0
#define WorldCoop_StartBattle(owner) 0
#define CleanupOverworldWindowsAndTilemaps() assert(0)
#define SetMainCallback2(cb) assert(0)
#define WorldActivity_StartNativeBattle(mode) 0
#define WorldActivity_ReturnToField() assert(0)
'''
HELPERS = r'''
static void CloseMenu(void) {++closed;}
static int ShowMenu(int yesNo) {assert(yesNo);++shown;sActivity.timer=0;return showOk;}
static void ShowWaiting(const char *s) {(void)s;assert(0);}
static void Stop(const char *s) {sActivity.state=IDLE;sActivity.status=s;}
static void reset(void) {
    memset(&sActivity,0,sizeof(sActivity));
    memset(&incoming,0,sizeof(incoming));
    sActivity.state=WAIT_TAG;sActivity.timer=12;
    strcpy(sActivity.peer,"alice");
    incoming.id=100;strcpy(incoming.name,"alice");
    shown=closed=rejected=accepted=0;ready=partyReady=showOk=outgoing=acceptOk=1;
    menuChoice=MENU_NOTHING_CHOSEN;
}
'''
MAIN = r'''
int main(void) {
    (void)WorldCoop_IsPrivateRewards;
    reset();
    WorldActivity_Update(); /* incoming OFFER delivered; BUSY not yet received */
    assert(outgoing); /* no fabricated response or implicit acceptance */
    assert(sActivity.state==INVITATION && sActivity.tagInvitation);
    assert(sActivity.invitation==100 && !strcmp(sActivity.peer,"alice"));
    assert(shown==1 && closed==1 && rejected==0 && sActivity.timer==0);
    WorldActivity_Update();
    assert(shown==1 && sActivity.state==INVITATION); /* no duplicate menu */
    reset();ready=0;WorldActivity_Update();assert(rejected==1 && shown==0);
    reset();partyReady=0;WorldActivity_Update();assert(rejected==1 && shown==0);
    reset();showOk=0;WorldActivity_Update();assert(rejected==1 && sActivity.state==IDLE);
    reset();incoming.id=0;WorldActivity_Update();assert(sActivity.state==WAIT_TAG && shown==0);
    reset();sActivity.state=IDLE;WorldActivity_Update();assert(sActivity.state==INVITATION && shown==1);
    /* Actual menu task must discard the opening A, not accept a cross. */
    reset();WorldActivity_Update();menuChoice=0;Task_Menu(0);
    assert(!accepted && !rejected && sActivity.state==INVITATION);
    Task_Menu(0);assert(accepted==1 && !rejected && sActivity.state==IDLE);
    reset();WorldActivity_Update();menuChoice=1;Task_Menu(0);Task_Menu(0);
    assert(!accepted && rejected==1 && sActivity.state==IDLE);
    reset();WorldActivity_Update();menuChoice=-1;Task_Menu(0);Task_Menu(0);
    assert(!accepted && rejected==1 && sActivity.state==IDLE);
    /* Readiness must be checked at Yes as well as at prompt creation. */
    reset();WorldActivity_Update();sActivity.timer=1;ready=0;menuChoice=0;Task_Menu(0);
    assert(!accepted && rejected==1 && sActivity.state==IDLE);
    reset();WorldActivity_Update();sActivity.timer=1;partyReady=0;menuChoice=0;Task_Menu(0);
    assert(!accepted && rejected==1 && sActivity.state==IDLE);
    reset();WorldActivity_Update();sActivity.timer=1;acceptOk=0;menuChoice=0;Task_Menu(0);
    assert(!accepted && rejected==1 && sActivity.state==IDLE);
    /* Authority expiry/disconnect must retire the prompt immediately. */
    reset();WorldActivity_Update();incoming.id=0;WorldActivity_Update();
    assert(sActivity.state==IDLE && !accepted);
    /* Proposer and recipient both follow authority END, not emulated frames. */
    reset();incoming.id=0;
    for (unsigned frame=0;frame<7200;frame++) {
        WorldActivity_Update();
        assert(sActivity.state==WAIT_TAG && !accepted);
    }
    outgoing=0;WorldActivity_Update();assert(sActivity.state==IDLE);
    /* Link inactivity during private EXP/evolution is intentional, not a failure.
     * Neither case may release field ownership or fabricate readiness. */
    reset();incoming.id=0;sActivity.state=NATIVE;sActivity.mode=NATIVE_LINK_COOP;
    native=0;privateRewards=1;ready=0;
    WorldActivity_Update();
    assert(sActivity.state==NATIVE && !ready && !native);
    assert(!strcmp(sActivity.status,"tagged encounter complete; finishing private rewards"));
    privateRewards=0;WorldActivity_Update();
    assert(strstr(sActivity.status,"connection lost") && sActivity.state==NATIVE);
    privateRewards=1;sActivity.mode=NATIVE_LINK_SINGLE;WorldActivity_Update();
    assert(strstr(sActivity.status,"connection lost"));
    sActivity.mode=NATIVE_LINK_TRADE;WorldActivity_Update();
    assert(strstr(sActivity.status,"connection lost"));
    sActivity.state=RETURNING;WorldActivity_Update();assert(sActivity.state==RETURNING);
    ready=1;WorldActivity_Update();assert(sActivity.state==IDLE);
    assert(!strcmp(sActivity.status,"native activity returned"));
    return 0;
}
'''

class CrossedTagActivity(unittest.TestCase):
    def test_pending_crossed_offer_opens_explicit_consent_before_busy(self):
        source = Path(os.environ.get('EW_ACTIVITY_SOURCE', ROOT/'src/platform/world_activity.c')).read_text()
        state = source[source.index('enum { IDLE,'):source.index('static int CopyPeer(')]
        code = PREAMBLE + state + function(source, 'CopyPeer') + HELPERS
        code += function(source, 'Task_Menu') + function(source, 'WorldActivity_Update') + MAIN
        with tempfile.TemporaryDirectory(prefix='crossed-tag-activity-') as directory:
            d = Path(directory)
            (d/'test.c').write_text(code)
            result = subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                                     '-fsanitize=address,undefined', str(d/'test.c'), '-o', str(d/'test')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(d/'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
