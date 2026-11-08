"""Compile WORLD's real state machine with fixture backends, no SDL or sockets.

The fixture checks input ownership, actionable text and real font-width bounds.
It does not render pixels or establish native gameplay/build acceptance.
Set EW_RC7_ENGINE to run the same checks against a reconstructed RC9 engine.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path(os.environ.get('EW_RC7_ENGINE', ROOT))
NATIVE = ENGINE / ('src/world' if 'EW_RC7_ENGINE' in os.environ else 'src/platform')

PREAMBLE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
#define FONT_SMALL 0
#define TEXT_SKIP_DRAW 0
#define COPYWIN_FULL 0
#define PIXEL_FILL(x) (x)
#define WINDOW_NONE 255
#define WORLD_CHAT_HEIGHT 64
#define PARTY_SIZE 6
#define MON_DATA_SPECIES 0
#define MON_DATA_IS_EGG 1
#define MON_DATA_HP 2
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
#define OBJECT_EVENTS_COUNT 16
#define MAP_OFFSET 7
#define ELEVATION_DEFAULT 3
#define MAP_RUSTBORO_CITY_GYM 0x102
#define MAP_GROUP(x) ((x)>>8)
#define MAP_NUM(x) ((x)&255)
#define FLAG_BADGE01_GET 1
#define FLAG_DEFEATED_RUSTBORO_GYM 2
#define FLAG_VISITED_RUSTBORO_CITY 3
#define VAR_RUSTBORO_CITY_STATE 1
#define TRAINER_ROXANNE_1 1
#define TRAINER_JOSH 2
#define TRAINER_TOMMY 3
#define TRAINER_MARC 4
#define A_BUTTON 1
#define B_BUTTON 2
#define START_BUTTON 4
#define SELECT_BUTTON 8
#define L_BUTTON 16
#define R_BUTTON 32
#define DPAD_UP 64
#define DPAD_DOWN 128
#define DPAD_LEFT 256
#define DPAD_RIGHT 512
#define DPAD_ANY (DPAD_UP|DPAD_DOWN|DPAD_LEFT|DPAD_RIGHT)
#define JOY_NEW(x) (gMain.newKeys & (x))
#define JOY_REPEAT(x) (gMain.newKeys & (x))
#define JOY_HELD(x) (gMain.heldKeys & (x))
struct Save {struct {unsigned mapGroup, mapNum;} location;};
struct ObjectEvent {bool8 active,isPlayer;struct {int x,y;} currentCoords;int currentElevation;};
struct Pokemon {unsigned fields[3];};
struct WindowTemplate {int bg,x,y,width,height,palette,base;};
static struct Save save, *gSaveBlock1Ptr=&save;
static int save2, *gSaveBlock2Ptr=&save2;
static struct {void (*callback1)(void);void (*callback2)(void);int inBattle;unsigned newKeys,heldKeys;} gMain;
static struct {int active;} gPaletteFade;
static struct {int tileTransitionState;unsigned objectEventId;} gPlayerAvatar;
static struct {int mapType;} gMapHeader;
static unsigned gWirelessCommType, gPlayerPartyCount;
static struct ObjectEvent gObjectEvents[16];
static struct Pokemon gPlayerParty[6];
static int enabled, fresh, inside, canEnter, partyReady, onFoot, caveReady, dexReady;
static int locked, frozen, script, nativeLink, activity, travel, flight, overworldLink, allocationFails;
static int calls, drawCalls, windowRemovals, enterResult, guildResult, dexResult;
static int visited, trainersReady, badge, autoJoin, shuffle, returnPoint, rallyOnline;
static unsigned shuffleSeed;
void CB1_Overworld(void) {}
void CB2_Overworld(void) {}
int ScriptContext_IsEnabled(void) {return script;}
int IsOverworldLinkActive(void) {return overworldLink;}
int NativeLink_IsActive(void) {return nativeLink;}
int WorldActivity_OwnsFieldInput(void) {return activity;}
int WorldTravel_OwnsFieldInput(void) {return travel;}
int WorldTravel_NativeFlyRunning(void) {return flight;}
int ArePlayerFieldControlsLocked(void) {return locked;}
void UnlockPlayerFieldControls(void) {locked=0;}
void LockPlayerFieldControls(void) {locked=1;}
void FreezeObjectEvents(void) {frozen=1;}
void UnfreezeObjectEvents(void) {frozen=0;}
void ClearStdWindowAndFrame(unsigned id,int clear) {(void)id;(void)clear;}
void RemoveWindow(unsigned id) {(void)id;windowRemovals++;}
unsigned AddWindow(const struct WindowTemplate *window) {(void)window;return allocationFails?WINDOW_NONE:1;}
void SetStandardWindowBorderStyle(unsigned id,int clear) {(void)id;(void)clear;}
void FillWindowPixelBuffer(unsigned id,int fill) {(void)id;(void)fill;}
void CopyWindowToVram(unsigned id,int mode) {(void)id;(void)mode;drawCalls++;}
int FlagGet(unsigned flag) {return flag==FLAG_VISITED_RUSTBORO_CITY?visited:badge;}
int VarGet(unsigned var) {(void)var;return 0;}
int HasTrainerBeenFought(unsigned trainer) {return trainer==TRAINER_ROXANNE_1?badge:trainersReady;}
unsigned GetMonData(const struct Pokemon *mon,unsigned field) {assert(field<3);return mon->fields[field];}
int IsMapTypeOutdoors(int type) {return type==1;}
int TestPlayerAvatarFlags(int flags) {(void)flags;return onFoot;}
int GeneratedMap_IsInside(void) {return inside;}
int GeneratedMap_CanEnter(void) {return canEnter;}
int GeneratedMap_HasUsableParty(void) {return partyReady;}
int GeneratedMap_Enter(void) {calls++;return enterResult;}
int GeneratedMap_Leave(void) {calls++;return enterResult;}
int WorldBridge_Enabled(void) {return enabled;}
int WorldBridge_ConnectionActive(void) {return fresh;}
int WorldBridge_GeneratedCaveReady(void) {return caveReady;}
const char *WorldBridge_TrainerName(void) {return enabled?"Alice":NULL;}
int DexNavNative_Available(void) {return dexReady;}
int DexNav_RequestOpen(void) {calls++;return dexResult;}
void WorldTravel_RequestMenu(void) {calls++;}
int WorldChat_OpenGuild(void) {calls++;return guildResult;}
int WildShuffle_Enabled(void) {return shuffle;}
unsigned WildShuffle_Seed(void) {return shuffleSeed;}
void WildShuffle_Toggle(void) {shuffle=!shuffle;}
void WildShuffle_NextSeed(void) {shuffleSeed++;}
int WorldRally_HasReturn(void) {return returnPoint;}
int WorldRally_GetAutoJoin(void) {return autoJoin;}
void WorldRally_SetAutoJoin(int value) {autoJoin=value;}
int WorldRally_Request(unsigned scene,unsigned scope) {(void)scene;(void)scope;calls++;return 1;}
int WorldRally_Choose(unsigned action) {(void)action;calls++;return 1;}
const char *WorldRally_Status(void) {return "Waiting for a rally.";}
'''

MAIN = r'''
static void Reset(void)
{
    memset(&sMenu,0,sizeof(sMenu));sMenu.window=WINDOW_NONE;
    memset(&live,0,sizeof(live));
    enabled=fresh=inside=canEnter=locked=frozen=script=nativeLink=activity=travel=flight=overworldLink=0;
    calls=drawCalls=windowRemovals=allocationFails=badge=autoJoin=shuffle=returnPoint=0;
    visited=trainersReady=onFoot=partyReady=caveReady=dexReady=enterResult=guildResult=dexResult=rallyOnline=1;
    shuffleSeed=1;gPlayerPartyCount=1;gPlayerParty[0]=(struct Pokemon){{1,0,10}};
    gMain.callback1=CB1_Overworld;gMain.callback2=CB2_Overworld;
    gMain.inBattle=gMain.newKeys=gMain.heldKeys=gPaletteFade.active=gWirelessCommType=0;
    gPlayerAvatar.tileTransitionState=0;gPlayerAvatar.objectEventId=0;
    gObjectEvents[0]=(struct ObjectEvent){1,1,{12,10},3};
    save.location.mapGroup=1;save.location.mapNum=2;gMapHeader.mapType=1;
}
static void Open(void)
{
    WorldMenu_RequestOpen();WorldMenu_Update();
    assert(sMenu.state==FEATURES&&locked&&frozen);
}
static void Press(unsigned key)
{
    gMain.newKeys=key;WorldMenu_Update();gMain.newKeys=0;
}
static void DrawAction(enum Action action)
{
    struct Row rows[ACTION_COUNT];
    unsigned count=Rows(rows,&live,rallyOnline),i;
    for(i=0;i<count&&rows[i].action!=action;i++);
    assert(i<count);sMenu.focus=action;Draw(rows,count,i,&live,rallyOnline);
}
static int ScreenHas(const char *needle)
{
    char text[SCREEN_LINES*TEXT_BYTES]={0};
    for(unsigned i=0;i<SCREEN_LINES;i++){strcat(text,sMenu.drawn.lines[i]);strcat(text," ");}
    return strstr(text,needle)!=NULL;
}
static void CheckHelpFits(enum Action action)
{
    struct Screen screen={0};
    char actual[SCREEN_LINES*TEXT_BYTES]={0};
    Wrap(&screen,9,SCREEN_LINES,ActionHelp(action));
    for(unsigned i=9;i<SCREEN_LINES&&screen.lines[i][0];i++){
        if(actual[0])strcat(actual," ");
        strcat(actual,screen.lines[i]);
    }
    assert(!strcmp(actual,ActionHelp(action)));
}
int main(void)
{
    Reset();Open();
#if GENERATED_MAP_READY
    assert(sMenu.focus==GEN_CAVE);
#else
    assert(sMenu.focus==FRIENDS);
#endif
    assert(ScreenHas("Solo"));
    enabled=1;WorldMenu_Update();assert(ScreenHas("No connection"));
    fresh=1;WorldMenu_Update();assert(ScreenHas("Online"));
    DrawAction(FRIENDS);assert(ScreenHas("Fly to a friend")&&ScreenHas("co-op"));
    fresh=0;DrawAction(FRIENDS);assert(ScreenHas("Connection lost"));
    Press(A_BUTTON);assert(calls==0&&sMenu.state==FEATURES);
    /* A disabled choice's error must not follow focus onto another feature. */
    fresh=1;sMenu.focus=GUILDS;DrawAction(GUILDS);assert(!ScreenHas("Connection lost"));
    assert(ScreenHas("map visits")&&ScreenHas("not generated"));
    sMenu.notice="Old failure";sMenu.noticeAction=GUILDS;Press(DPAD_DOWN);assert(!sMenu.notice);
    DrawAction(SHUFFLE);assert(ScreenHas("Wild shuffle: OFF"));
    Press(A_BUTTON);assert(sMenu.state==SHUFFLE_MENU);Press(A_BUTTON);assert(shuffle);
    Press(B_BUTTON);WorldMenu_Update();assert(sMenu.state==FEATURES&&sMenu.focus==SHUFFLE&&ScreenHas("Wild shuffle: ON"));
    for(unsigned a=0;a<ACTION_COUNT;a++)CheckHelpFits(a);
    /* Page identity is visible, while roster/action focus remains unchanged. */
    DrawAction(STORY);Press(A_BUTTON);WorldMenu_Update();assert(sMenu.state==RALLY&&ScreenHas("Actions  1/3"));
    Press(DPAD_RIGHT);assert(sMenu.page==ROSTER&&ScreenHas("Trainers  2/3"));
    Press(DPAD_RIGHT);assert(sMenu.page==STATUS&&ScreenHas("Status  3/3"));
    Press(DPAD_LEFT);assert(sMenu.page==ROSTER);Press(B_BUTTON);WorldMenu_Update();
    assert(sMenu.state==FEATURES&&sMenu.focus==STORY);
    /* Action identity remains stable when a live roster adds or removes rows. */
    sMenu.state=RALLY;sMenu.page=CONTROLS;sMenu.focus=GO;
    live.id=7;live.phase=WORLD_RALLY_GATHER;strcpy(live.owner,"Alice");WorldMenu_Update();assert(sMenu.focus==GO);
    live.phase=WORLD_RALLY_ACTIVE;WorldMenu_Update();assert(sMenu.focus==BACK);
    live.count=WORLD_RALLY_ROSTER;
    for(unsigned i=0;i<live.count;i++){
        strcpy(live.members[i].name,"ABCDEFGHIJKLMNOPQRSTUVWX");live.members[i].slot=i;
        live.members[i].state=WORLD_RALLY_READY;
    }
    for(unsigned phase=0;phase<=WORLD_RALLY_RETURN;phase++){
        live.phase=phase;
        for(unsigned page=0;page<PAGE_COUNT;page++){
            sMenu.page=page;WorldMenu_Update();
        }
    }
#if GENERATED_MAP_READY
    sMenu.notice="Generated area unavailable";sMenu.noticeAction=GEN_CAVE;
    sMenu.page=STATUS;WorldMenu_Update();assert(!ScreenHas("Generated area unavailable"));
#endif
    Press(B_BUTTON);WorldMenu_Update();Press(B_BUTTON);assert(sMenu.state==CLOSED&&!locked&&!frozen);
#if GENERATED_MAP_READY
    Reset();inside=1;Open();assert(sMenu.focus==GEN_CAVE&&ScreenHas("Leave generated area"));
    assert(ScreenHas("save normally"));Press(A_BUTTON);assert(sMenu.state==DISPATCH&&!locked&&!frozen);
    WorldMenu_Update();assert(calls==0);WorldMenu_Update();assert(calls==1&&sMenu.state==CLOSED);
    /* A held/repeated click cannot dispatch a second entry or exit. */
    Press(A_BUTTON);assert(calls==1);
    Reset();Open();Press(A_BUTTON);assert(sMenu.state==FEATURES&&!calls); /* no safe area */
    canEnter=1;Press(A_BUTTON);assert(sMenu.state==DISPATCH);Press(DPAD_RIGHT);assert(sMenu.state==CLOSED&&!calls);
#endif
    Reset();enabled=fresh=1;Open();DrawAction(FRIENDS);Press(A_BUTTON);
    assert(sMenu.state==DISPATCH&&!locked);nativeLink=1;WorldMenu_Update();WorldMenu_Update();assert(!calls);
    nativeLink=0;WorldMenu_Update();WorldMenu_Update();assert(calls==1);
    /* Revalidate a queued rally identity and do not claim server approval. */
    Reset();enabled=fresh=1;Open();sMenu.state=RALLY;sMenu.page=CONTROLS;
    live.id=7;live.phase=WORLD_RALLY_GATHER;strcpy(live.owner,"Alice");
    DrawAction(READY);Press(A_BUTTON);live.id=8;WorldMenu_Update();WorldMenu_Update();
    assert(!calls&&sMenu.state==CLOSED&&strstr(sMenu.notice,"changed"));
    /* Offline return recovery remains available even with no live roster. */
    Reset();returnPoint=1;rallyOnline=0;Open();sMenu.state=RALLY;sMenu.page=CONTROLS;
    DrawAction(RETURN);assert(!ScreenHas("X Return"));Press(A_BUTTON);
    WorldMenu_Update();WorldMenu_Update();assert(calls==1);
    /* Reset/scene replacement owns its windows and lock; never tear it down. */
    Reset();Open();script=1;WorldMenu_Update();assert(sMenu.state==CLOSED&&locked&&!windowRemovals);
    Reset();allocationFails=1;WorldMenu_RequestOpen();WorldMenu_Update();assert(sMenu.state==CLOSED&&!locked);
    puts("WORLD state and text assertions completed");fflush(stdout);
    return 0;
}
'''


def compile_run(test, source, flags=()):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / 'fixture.c').write_text(source)
        command = ['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                   '-fno-omit-frame-pointer', '-g', '-DPORTABLE',
                   '-iquote', str(ENGINE / 'include'), *flags,
                   str(path / 'fixture.c'), '-o', str(path / 'fixture')]
        build = subprocess.run(command, capture_output=True, text=True)
        test.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(path / 'fixture')], capture_output=True, text=True,
                             env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1',
                                  'UBSAN_OPTIONS': 'print_stacktrace=1'})
        test.assertEqual(run.returncode, 0, run.stdout + run.stderr)


class NativeWorldMenu(unittest.TestCase):
    def test_active_connection_is_not_just_configuration(self):
        source = function((NATIVE / 'world_bridge.c').read_text(), 'WorldBridge_ConnectionActive')
        compile_run(self, '''#include <assert.h>\n#include <stdio.h>\ntypedef int bool8;
static struct {int enabled,connected;unsigned snapshotAge;} sWorld;
''' + source + '''
int main(void) {
 assert(!WorldBridge_ConnectionActive());sWorld.enabled=1;
 assert(!WorldBridge_ConnectionActive());sWorld.connected=1;
 assert(WorldBridge_ConnectionActive());sWorld.snapshotAge=180;
 assert(WorldBridge_ConnectionActive());sWorld.snapshotAge=181;
 assert(!WorldBridge_ConnectionActive());sWorld.snapshotAge=0;sWorld.enabled=0;
 assert(!WorldBridge_ConnectionActive());puts("Connection assertions completed");fflush(stdout);return 0;
}''')

    def test_real_menu_input_and_text_layout(self):
        menu = (NATIVE / 'world_menu.c').read_text()
        menu = re.sub(r'^#include "[^"]+"\n', '', menu, flags=re.M)
        rally = (ENGINE / 'include/platform/world_rally.h').read_text()
        # Keep actual enum/struct declarations, use instrumented backend functions.
        rally = rally[rally.index('#define WORLD_RALLY_ROSTER'):rally.index('/* Main/game thread')]
        widths = re.search(r'gFontSmallLatinGlyphWidths\[\]\s*=\s*(\{.*?\});',
                           (ENGINE / 'src/fonts.c').read_text(), re.S).group(1)
        pre = PREAMBLE + rally + '\n#include "constants/characters.h"\n' + r'''
static struct WorldRallySnapshot live;
int WorldRally_GetSnapshot(struct WorldRallySnapshot *out) {*out=live;return rallyOnline;}
static const unsigned widths[] = ''' + widths + r''';
unsigned GetStringWidth(unsigned font,const u8 *text,int spacing)
{
    unsigned width=0;(void)font;(void)spacing;
    for(;*text!=EOS;text++){assert(*text<sizeof(widths)/sizeof(widths[0]));width+=widths[*text];}
    return width;
}
void AddTextPrinterParameterized(unsigned window,unsigned font,const u8 *text,unsigned x,unsigned y,int speed,void *cb)
{
    (void)window;(void)font;(void)speed;(void)cb;
    assert(x+GetStringWidth(font,text,0)<=224);assert(y+12<=144);
}
'''
        for generated in (0, 1):
            with self.subTest(generated=generated):
                compile_run(self, pre + menu + MAIN, [f'-DGENERATED_MAP_READY={generated}'])


if __name__ == '__main__':
    unittest.main()
