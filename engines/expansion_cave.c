/* Experimental offline-only cave adapter, gated off by default. */
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include "global.h"
#include "global.fieldmap.h"
#include "fieldmap.h"
#include "field_player_avatar.h"
#include "field_screen_effect.h"
#include "overworld.h"
#include "main.h"
#include "palette.h"
#include "script.h"
#include "task.h"
#include "save.h"
#include "platform/flash.h"
#include "constants/maps.h"
#include "constants/event_objects.h"

/* The pinned donor has groups 0..74. The build must assert that before use. */
#define EXPANSION_CAVE_GROUP 75
#define EXPANSION_CAVE_NUM 0
#define CAVE_SIDE 31
#define CAVE_CELLS (CAVE_SIDE * CAVE_SIDE)
extern bool expansion_cave_decode(const uint8_t *, size_t, uint16_t *);
static u16 sTiles[CAVE_CELLS];
static struct MapLayout sLayout;
static struct MapHeader sHeader;
static struct MapEvents sEvents;
static struct WarpEvent sExit;
static struct WarpData sReturn, sPreviousDynamic;
static bool8 sStaged, sPrepared, sSeenInside, sHasHeader;

bool8 ExpansionCave_Stage(const uint8_t *wire, size_t size)
{
    if (sPrepared) return FALSE;
    if (!expansion_cave_decode(wire, size, sTiles)) return FALSE;
    sStaged = TRUE;
    return TRUE;
}
bool8 ExpansionCave_IsInside(void)
{
    return gSaveBlock1Ptr && gSaveBlock1Ptr->location.mapGroup == EXPANSION_CAVE_GROUP
        && gSaveBlock1Ptr->location.mapNum == EXPANSION_CAVE_NUM;
}
const struct MapHeader *ExpansionCave_Header(void)
{
    if (!sPrepared && !sHasHeader) { fputs("Unprepared Expansion generated cave.\n", stderr); abort(); }
    sHasHeader = TRUE;
    const struct MapHeader *base = Overworld_GetMapHeaderByGroupAndId(MAP_GROUP(MAP_CAVE_OF_ORIGIN_ENTRANCE), MAP_NUM(MAP_CAVE_OF_ORIGIN_ENTRANCE));
    sHeader = *base;
    sExit = (struct WarpEvent){ .x=29, .y=29, .elevation=3, .warpId=WARP_ID_DYNAMIC,
        .mapNum=MAP_NUM(MAP_DYNAMIC), .mapGroup=MAP_GROUP(MAP_DYNAMIC) };
    sEvents = (struct MapEvents){ .warpCount=1, .warps=&sExit };
    sHeader.events = &sEvents;
    sHeader.mapScripts = NULL;
    sHeader.connections = NULL;
    sHeader.allowEscaping = FALSE;
    sHeader.allowCycling = FALSE;
    return &sHeader;
}
const struct MapLayout *ExpansionCave_ResolveLayout(const struct MapLayout *base)
{
    if (!base || !sPrepared || !ExpansionCave_IsInside()) return base;
    sSeenInside = TRUE;
    sLayout = *base;
    sLayout.width = CAVE_SIDE; sLayout.height = CAVE_SIDE; sLayout.map = sTiles;
    return &sLayout;
}
void ExpansionCave_Update(void)
{
    static bool8 audited;
    if (getenv("EW_CAVE_SAVE_AUDIT") && !audited && sPrepared && ExpansionCave_IsInside()) {
        u32 before=flash_write_count();
        u8 status=TrySavingData(SAVE_NORMAL);
        u32 after=flash_write_count();
        fprintf(stderr,"cave save audit: status=%u writes_before=%u writes_after=%u\n",status,before,after);
        audited=TRUE;
    }
    if (sPrepared && sSeenInside && !ExpansionCave_IsInside()) {
        if (gSaveBlock1Ptr) gSaveBlock1Ptr->dynamicWarp = sPreviousDynamic;
        sPrepared = sSeenInside = sStaged = FALSE;
    }
}
/* Only call after staging in an explicitly opted-in offline session.
 * The synthetic-map and save guards still require end-to-end verification. */
bool8 ExpansionCave_Enter(void)
{
    s16 x,y; bool8 taskAvailable=FALSE;
    if (!sStaged || sPrepared || !gSaveBlock1Ptr || !gSaveBlock2Ptr
        || gMain.callback1 != CB1_Overworld || gMain.callback2 != CB2_Overworld
        || gMain.inBattle || gPaletteFade.active || ScriptContext_IsEnabled()
        || ArePlayerFieldControlsLocked() || !gMapHeader.mapLayout
        || !IsMapTypeOutdoors(gMapHeader.mapType)
        || !TestPlayerAvatarFlags(PLAYER_AVATAR_FLAG_ON_FOOT)) return FALSE;
    for (unsigned i=0;i<NUM_TASKS;i++) if (!gTasks[i].isActive) {taskAvailable=TRUE; break;}
    if (!taskAvailable) return FALSE;
    PlayerGetDestCoords(&x,&y); x -= MAP_OFFSET; y -= MAP_OFFSET;
    if (x<0 || y<0 || x>127 || y>127 || x>=gMapHeader.mapLayout->width || y>=gMapHeader.mapLayout->height) return FALSE;
    sReturn = gSaveBlock1Ptr->location;
    sReturn.warpId=WARP_ID_NONE; sReturn.x=x; sReturn.y=y;
    sPreviousDynamic=gSaveBlock1Ptr->dynamicWarp;
    SetDynamicWarpWithCoords(0,sReturn.mapGroup,sReturn.mapNum,WARP_ID_NONE,x,y);
    sPrepared=TRUE; sSeenInside=FALSE;
    SetWarpDestination(EXPANSION_CAVE_GROUP,EXPANSION_CAVE_NUM,WARP_ID_NONE,1,1);
    StoreInitialPlayerAvatarState(); DoWarp();
    return TRUE;
}

bool8 ExpansionCave_Leave(void)
{
    if (!sPrepared || !ExpansionCave_IsInside() || gMain.callback2 != CB2_Overworld
        || gMain.inBattle || gPaletteFade.active || ScriptContext_IsEnabled()
        || ArePlayerFieldControlsLocked()) return FALSE;
    bool8 taskAvailable=FALSE;
    for (unsigned i=0;i<NUM_TASKS;i++) if (!gTasks[i].isActive) {taskAvailable=TRUE; break;}
    if (!taskAvailable) return FALSE;
    SetWarpDestination(sReturn.mapGroup,sReturn.mapNum,WARP_ID_NONE,sReturn.x,sReturn.y);
    StoreInitialPlayerAvatarState(); DoWarp(); return TRUE;
}

/* Only local offline sessions may opt in. No network, event script or
 * arbitrary program content is accepted in the generated template. */
static bool8 CaveEnabled(void)
{
    const char *flag=getenv("EW_EXPERIMENTAL_EXPANSION_CAVE");
    const char *offline=getenv("EW_EXPANSION_OFFLINE");
    return flag && !strcmp(flag,"1") && offline && !strcmp(offline,"1")
        && !getenv("EW_EXPANSION_LINK_CONFIG");
}
static bool8 LoadTemplate(void)
{
    const char *path=getenv("EW_EXPANSION_CAVE_TEMPLATE");
    uint8_t wire[8+CAVE_CELLS]; struct stat st; size_t offset=0;
    if (!path || path[0]!='/') return FALSE;
    int fd=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);
    if (fd<0) return FALSE;
    if (fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_size != sizeof wire) {close(fd); return FALSE;}
    while (offset<sizeof wire) {
        ssize_t n=read(fd,wire+offset,sizeof wire-offset);
        if (n<0 && errno==EINTR) continue;
        if (n<=0) {close(fd); return FALSE;}
        offset += n;
    }
    close(fd);
    return ExpansionCave_Stage(wire,sizeof wire);
}
bool8 ExpansionCave_HandleInput(u16 newKeys,u16 heldKeys)
{
    if (getenv("EW_CAVE_DIAGNOSTIC") && (newKeys & SELECT_BUTTON))
        fprintf(stderr, "cave input: new=%u held=%u enabled=%d\n",newKeys,heldKeys,CaveEnabled());
    if (!CaveEnabled() || !(newKeys & SELECT_BUTTON) || !(heldKeys & R_BUTTON)) return FALSE;
    if (ExpansionCave_IsInside()) return ExpansionCave_Leave();
    bool8 loaded=LoadTemplate();
    bool8 entered=loaded && ExpansionCave_Enter();
    if (getenv("EW_CAVE_DIAGNOSTIC"))
        fprintf(stderr, "cave stage=%d entered=%d callbacks=%d/%d battle=%d fade=%d script=%d locked=%d outdoor=%d foot=%d\n", loaded,entered,
            gMain.callback1==CB1_Overworld,gMain.callback2==CB2_Overworld,gMain.inBattle,gPaletteFade.active,ScriptContext_IsEnabled(),ArePlayerFieldControlsLocked(),IsMapTypeOutdoors(gMapHeader.mapType),TestPlayerAvatarFlags(PLAYER_AVATAR_FLAG_ON_FOOT));
    return entered;
}
