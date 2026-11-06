#ifdef PORTABLE
#include "global.h"
#include "main.h"
#include "overworld.h"
#include "field_screen_effect.h"
#include "field_player_avatar.h"
#include "fieldmap.h"
#include "task.h"
#include "platform/world_bridge.h"
#include "platform/link_transport.h"
#include "platform/world_rally.h"
#include "platform/generated_map.h"
#if GENERATED_WORLD_XL && GENERATED_WILDS_EVENTS
#include "platform/xl_progress_store.h"
#endif
#if GENERATED_WILDS_EVENTS
#include "field_camera.h"
#include "event_data.h"
#endif
#include "constants/maps.h"
#if GENERATED_WILDS_GUIDE
#include "constants/event_object_movement.h"
#endif
#if GENERATED_CAVE_WILDLIFE
#include "wild_encounter.h"
#include "constants/species.h"
#endif
#include <string.h>

/* The native-only script references this fixed-size literal buffer even when
 * the optional feature is disabled. It never contains control codes. */
u8 gGeneratedWildsGuideText[58] = {0xFF};
u8 gGeneratedWildsCastText2[58] = {0xFF};
u8 gGeneratedWildsCastText3[58] = {0xFF};
u8 gGeneratedEventText[58] = {0xFF};

#if GENERATED_MAP_READY
/* Both supported sizes fit the native backup-map buffer with the view border.
 * Cave palette and metatiles come from the existing Cave of Origin layout. */
#define GEN_SIDE 31
#define GEN_CELLS (GEN_SIDE * GEN_SIDE)
#define GEN_FLOOR 0x3333
#define GEN_WALL 0x0722
#define GEN_EXIT 0x3323
#define GEN_AUTOFLOOR 0x331b
#define GEN_MAX_NODES 225

static u16 sTiles[GEN_CELLS];
static u8 sTemplate[GEN_CELLS];
#if GENERATED_MAP_LARGE
#define LARGE_SIDE 63
#define LARGE_CELLS (LARGE_SIDE * LARGE_SIDE)
static u16 sLargeTiles[LARGE_CELLS];
static u8 sLargeTemplate[LARGE_CELLS];
static bool8 sLargeStaged, sLargeActive, sLargeShared;
#if GENERATED_MAP_WILDS
static bool8 sLargeWilds;
#if GENERATED_WILDS_GUIDE
static bool8 sGuideStaged, sGuideActive, sGuideShared;
static u8 sGuideGfx, sGuideMetadata[GENERATED_GUIDE_BYTES];
static struct MapEvents sGuideEvents;
static struct ObjectEventTemplate sGuideObjects[OBJECT_EVENT_TEMPLATES_COUNT];
extern const u8 GeneratedWorld_Wilds_EventScript_Guide[];
#if GENERATED_WILDS_CAST
static bool8 sCastStaged, sCastActive;
#if GENERATED_WILDS_EVENTS
static bool8 sEventStaged, sEventActive;
static u8 sEventState, sEventData[GENERATED_EVENT_BYTES], sEventRuntime[GENERATED_EVENT_BYTES];
#if GENERATED_WILDS_SHARED_TERRAIN
static u8 sSharedTerrain[GENERATED_TERRAIN_MAX_BYTES];static u16 sSharedTerrainSize;
#if GENERATED_WILDS_SHARED_GEOMETRY
static u8 sSharedWalk[LARGE_CELLS];
#endif
#endif
extern const u8 GeneratedWorld_Wilds_EventScript_Graph[];
#endif
static u8 sCastMetadata[GENERATED_CAST_BYTES];
extern const u8 GeneratedWorld_Wilds_EventScript_Cast2[], GeneratedWorld_Wilds_EventScript_Cast3[];
#endif
#endif
#endif
#endif
#if GENERATED_WORLD_XL
#define XL_SIDE 127
#define XL_CELLS (XL_SIDE*XL_SIDE)
static u16 sXLTiles[XL_CELLS];static u8 sXLTemplate[XL_CELLS];
static bool8 sXLStaged,sXLActive;
#if GENERATED_WILDS_CAST
static bool8 sXLCastStaged;
#endif
static struct WarpEvent sXLWarp;static struct MapEvents sXLEvents;
#if GENERATED_WILDS_EVENTS
#define XL_PROGRESS_SLOTS 4
static struct {bool8 valid;u8 trainer[4],state,events[GENERATED_EVENT_BYTES],cast[GENERATED_CAST_BYTES],cells[XL_CELLS];} sXLProgress[XL_PROGRESS_SLOTS];
static u8 sXLProgressCurrent=0xFF,sXLProgressNext;
#define XL_PROGRESS_SLOT_BYTES (6 + GENERATED_EVENT_BYTES + GENERATED_CAST_BYTES + XL_CELLS)
#define XL_PROGRESS_PAYLOAD_BYTES (1 + XL_PROGRESS_SLOTS * XL_PROGRESS_SLOT_BYTES)
static u8 sXLProgressPayload[XL_PROGRESS_PAYLOAD_BYTES];static bool8 sXLProgressDurable;
static void XLProgressPack(void)
{
    unsigned i;u8 *p=sXLProgressPayload;*p++=sXLProgressNext;
    for(i=0;i<XL_PROGRESS_SLOTS;i++){*p++=sXLProgress[i].valid;memcpy(p,sXLProgress[i].trainer,4);p+=4;*p++=sXLProgress[i].state;
        memcpy(p,sXLProgress[i].events,GENERATED_EVENT_BYTES);p+=GENERATED_EVENT_BYTES;memcpy(p,sXLProgress[i].cast,GENERATED_CAST_BYTES);p+=GENERATED_CAST_BYTES;memcpy(p,sXLProgress[i].cells,XL_CELLS);p+=XL_CELLS;}
}
static bool8 XLProgressUnpack(void)
{
    unsigned i;const u8 *p=sXLProgressPayload;
    if(*p>=XL_PROGRESS_SLOTS)return FALSE;
    for(i=0;i<XL_PROGRESS_SLOTS;i++){const u8 *r=p+1+i*XL_PROGRESS_SLOT_BYTES;if(r[0]>1 || r[5]>15)return FALSE;}
    sXLProgressNext=*p++;
    for(i=0;i<XL_PROGRESS_SLOTS;i++){sXLProgress[i].valid=*p++;memcpy(sXLProgress[i].trainer,p,4);p+=4;sXLProgress[i].state=*p++;
        memcpy(sXLProgress[i].events,p,GENERATED_EVENT_BYTES);p+=GENERATED_EVENT_BYTES;memcpy(sXLProgress[i].cast,p,GENERATED_CAST_BYTES);p+=GENERATED_CAST_BYTES;memcpy(sXLProgress[i].cells,p,XL_CELLS);p+=XL_CELLS;}
    return TRUE;
}
bool8 GeneratedMap_InitXLProgress(const char *savePath,bool8 enabled)
{
    if(!enabled)return TRUE;
    if(!XLProgressStore_Init(savePath,TRUE,sXLProgressPayload,sizeof(sXLProgressPayload)))return FALSE;
    if(!XLProgressUnpack()){XLProgressStore_Close();return FALSE;}
    sXLProgressDurable=TRUE;return TRUE;
}
static void XLProgressPersist(void)
{
    if(sXLProgressDurable){XLProgressPack();if(!XLProgressStore_Save(sXLProgressPayload,sizeof(sXLProgressPayload)))sXLProgressDurable=FALSE;}
}
static void XLRestoreEventProgress(void)
{
    unsigned i;const u8 *trainer;
    sXLProgressCurrent=0xFF;
    if(!sXLActive || !sEventActive || WorldBridge_Enabled() || !gSaveBlock2Ptr)return;
    trainer=gSaveBlock2Ptr->playerTrainerId;
    for(i=0;i<XL_PROGRESS_SLOTS;i++)if(sXLProgress[i].valid && !memcmp(sXLProgress[i].trainer,trainer,4)
       && !memcmp(sXLProgress[i].events,sEventData,GENERATED_EVENT_BYTES) && !memcmp(sXLProgress[i].cast,sCastMetadata,GENERATED_CAST_BYTES)
       && !memcmp(sXLProgress[i].cells,sXLTemplate,XL_CELLS)) {sXLProgressCurrent=i;sEventState=sXLProgress[i].state;return;}
    i=sXLProgressNext;sXLProgressNext=(sXLProgressNext+1)%XL_PROGRESS_SLOTS;
    memcpy(sXLProgress[i].trainer,trainer,4);memcpy(sXLProgress[i].events,sEventData,GENERATED_EVENT_BYTES);
    memcpy(sXLProgress[i].cast,sCastMetadata,GENERATED_CAST_BYTES);memcpy(sXLProgress[i].cells,sXLTemplate,XL_CELLS);
    sXLProgress[i].state=sEventState;sXLProgress[i].valid=TRUE;sXLProgressCurrent=i;
}
static void XLRememberEventProgress(void)
{
    if(sXLProgressCurrent<XL_PROGRESS_SLOTS && gSaveBlock2Ptr && !memcmp(sXLProgress[sXLProgressCurrent].trainer,gSaveBlock2Ptr->playerTrainerId,4))
    {sXLProgress[sXLProgressCurrent].state=sEventState;XLProgressPersist();}
}
#endif
#endif
#if !(GENERATED_WORLD_XL && GENERATED_WILDS_EVENTS)
bool8 GeneratedMap_InitXLProgress(const char *savePath,bool8 enabled){(void)savePath;return !enabled;}
#endif
static bool8 sHasTemplate;
#if GENERATED_CAVE_PROFILES
static u8 sEncounterProfile;
static bool8 sSharedEncounterProfile;
#endif
#if GENERATED_CAVE_WILDLIFE
static struct WildPokemon sWildlifeMons[12];
static struct WildPokemonInfo sWildlifeInfo;
static bool8 sHasWildlife, sSharedWildlife;
static u8 sWildlifeRaw[GENERATED_WILDLIFE_BYTES];
#endif
static struct MapLayout sLayout;
static struct WarpData sReturn, sPreviousDynamicWarp;
static bool8 sPrepared, sSeenInside;
static u32 sRandom;

static u32 NextRandom(void)
{
    sRandom ^= sRandom << 13;
    sRandom ^= sRandom >> 17;
    sRandom ^= sRandom << 5;
    return sRandom;
}

static void BuildMaze(u32 seed)
{
    u16 stack[GEN_MAX_NODES];
    u16 count = 0, i;
    sRandom = seed ? seed : 0x6d2b79f5;
    for (i = 0; i < GEN_CELLS; i++) sTiles[i] = GEN_WALL;
    stack[count++] = GEN_SIDE + 1;
    sTiles[GEN_SIDE + 1] = GEN_FLOOR;
    while (count)
    {
        s16 x = stack[count - 1] % GEN_SIDE, y = stack[count - 1] / GEN_SIDE;
        s8 dx[4] = { 0, 2, 0, -2 }, dy[4] = { -2, 0, 2, 0 };
        u8 options[4], n = 0, d;
        for (d = 0; d < 4; d++)
        {
            s16 nx = x + dx[d], ny = y + dy[d];
            if (nx > 0 && nx < GEN_SIDE - 1 && ny > 0 && ny < GEN_SIDE - 1
             && sTiles[ny * GEN_SIDE + nx] == GEN_WALL) options[n++] = d;
        }
        if (!n) { count--; continue; }
        d = options[NextRandom() % n];
        sTiles[(y + dy[d] / 2) * GEN_SIDE + x + dx[d] / 2] = GEN_FLOOR;
        x += dx[d]; y += dy[d];
        sTiles[y * GEN_SIDE + x] = GEN_FLOOR;
        stack[count++] = y * GEN_SIDE + x;
    }
    /* The south-facing cave exit is reachable from the north. All odd
     * interior cells belong to the same maze component. */
    sTiles[28 * GEN_SIDE + 29] = GEN_FLOOR;
    sTiles[29 * GEN_SIDE + 29] = GEN_EXIT;
}
#if GENERATED_MAP_AUTOTILE
/* Cave of Origin's common wall edges, indexed by walkable neighbors N/E/S/W.
 * Shape only: each selected wall remains blocked, with the same elevation.
 * A separate pass prevents the chosen art from affecting neighbor masks. */
static void GeneratedMap_Autotile(void)
{
    static const u16 originWalls[16] = {
        0x322, 0x332, 0x322, 0x31a, 0x329, 0x329, 0x32a, 0x330,
        0x320, 0x318, 0x322, 0x330, 0x328, 0x330, 0x330, 0x330
    };
    const u16 *walls = originWalls;
    u16 floor = GEN_AUTOFLOOR, exit = GEN_EXIT;
#if GENERATED_CAVE_BIOMES
    /* All three visual sets use the existing general/cave tilesets. Meteor
     * uses the Origin-inspired set; granite and victory share stone art. */
    static const u16 stoneWalls[16] = {
        0x211, 0x209, 0x212, 0x20a, 0x219, 0x219, 0x21a, 0x20a,
        0x210, 0x208, 0x212, 0x202, 0x218, 0x208, 0x203, 0x202
    };
    static const u16 iceWalls[16] = {
        0x381, 0x379, 0x382, 0x37a, 0x389, 0x389, 0x38a, 0x37d,
        0x380, 0x37d, 0x382, 0x37a, 0x388, 0x37d, 0x37e, 0x37d
    };
    if (sEncounterProfile == 2) {
        walls = iceWalls; floor = 0x3385; exit = 0x3386;
    } else if (sEncounterProfile == 0 || sEncounterProfile == 3) {
        walls = stoneWalls; floor = 0x3201; exit = 0x3207;
    }
#endif
#if GENERATED_MAP_LARGE
    u8 walkable[LARGE_CELLS];
    u16 *tiles = sLargeActive ? sLargeTiles : sTiles;
    const unsigned side = sLargeActive ? LARGE_SIDE : GEN_SIDE;
#else
    u8 walkable[GEN_CELLS];
    u16 *tiles = sTiles;
    const unsigned side = GEN_SIDE;
#endif
    u16 i;
    for (i = 0; i < (side * side); i++)
        walkable[i] = tiles[i] == GEN_FLOOR || tiles[i] == GEN_EXIT;
    for (i = 0; i < (side * side); i++)
    {
        unsigned x = i % side, y = i / side, mask = 0;
        if (walkable[i])
        {
            tiles[i] = tiles[i] == GEN_EXIT ? exit : floor;
            continue;
        }
        if (y > 0 && walkable[i - side]) mask |= 1;
        if (x + 1 < side && walkable[i + 1]) mask |= 2;
        if (y + 1 < side && walkable[i + side]) mask |= 4;
        if (x > 0 && walkable[i - 1]) mask |= 8;
        tiles[i] = 0x400 | walls[mask];
    }
}
#endif

#endif

/* Accept only inert, bounded geometry. Stage atomically after validating the
 * closed perimeter and reachability of every floor and the south-facing exit. */
bool8 GeneratedMap_StageTemplate(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY
    u8 seen[GEN_CELLS] = {0};
    u16 queue[GEN_CELLS], head = 0, tail = 0, i;
    if (!cells || size != GEN_CELLS) return FALSE;
    for (i = 0; i < GEN_CELLS; i++)
    {
        u8 x = i % GEN_SIDE, y = i / GEN_SIDE;
        if (cells[i] != '.' && cells[i] != '#') return FALSE;
        if ((x == 0 || y == 0 || x == GEN_SIDE - 1 || y == GEN_SIDE - 1) && cells[i] != '#') return FALSE;
    }
    if (cells[GEN_SIDE + 1] != '.' || cells[28 * GEN_SIDE + 29] != '.'
     || cells[29 * GEN_SIDE + 29] != '.') return FALSE;
    queue[tail++] = GEN_SIDE + 1;
    seen[GEN_SIDE + 1] = TRUE;
    while (head < tail)
    {
        u16 pos = queue[head++];
        s16 neighbor[4] = { pos - GEN_SIDE, pos + 1, pos + GEN_SIDE, pos - 1 };
        u8 d;
        for (d = 0; d < 4; d++)
        {
            s16 next = neighbor[d];
            if (next >= 0 && next < GEN_CELLS && cells[next] == '.' && !seen[next])
            {
                seen[next] = TRUE;
                queue[tail++] = next;
            }
        }
    }
    for (i = 0; i < GEN_CELLS; i++)
        if (cells[i] == '.' && !seen[i]) return FALSE;
    memcpy(sTemplate, cells, sizeof(sTemplate));
    sHasTemplate = TRUE;
#if GENERATED_MAP_LARGE
    sLargeStaged = sLargeShared = FALSE;
#if GENERATED_WORLD_XL
    sXLStaged = FALSE;
#endif
#if GENERATED_MAP_WILDS
    sLargeWilds = FALSE;
#if GENERATED_WILDS_GUIDE
    sGuideStaged = sGuideShared = FALSE;
#if GENERATED_WILDS_CAST
    sCastStaged = FALSE;
#if GENERATED_WILDS_EVENTS
    sEventStaged = FALSE;
#if GENERATED_WILDS_SHARED_TERRAIN
    sSharedTerrainSize = 0;
#endif
#endif
#endif
#endif
#endif
#endif
#if GENERATED_CAVE_PROFILES
    sEncounterProfile = 0;
    sSharedEncounterProfile = FALSE;
#endif
#if GENERATED_CAVE_WILDLIFE
    sHasWildlife = sSharedWildlife = FALSE;
#endif
    return TRUE;
#else
    (void)cells; (void)size;
    return FALSE;
#endif
}

bool8 GeneratedMap_StageXLWilds(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WORLD_XL
    u8 seen[XL_CELLS]={0};u16 queue[XL_CELLS],head=0,tail=0,i;
    if(!cells || size!=XL_CELLS || WorldBridge_Enabled() || GeneratedMap_IsInside() || GeneratedMap_EntryPending())return FALSE;
    for(i=0;i<XL_CELLS;i++){unsigned x=i%XL_SIDE,y=i/XL_SIDE;
        if((cells[i]!='.' && cells[i]!='#') || ((x==0||y==0||x==XL_SIDE-1||y==XL_SIDE-1) && cells[i]!='#'))return FALSE;
    }
    if(cells[XL_SIDE+1]!='.' || cells[124*XL_SIDE+125]!='.' || cells[125*XL_SIDE+125]!='.')return FALSE;
    queue[tail++]=XL_SIDE+1;seen[XL_SIDE+1]=TRUE;
    while(head<tail){s16 pos=queue[head++],next[4]={pos-XL_SIDE,pos+1,pos+XL_SIDE,pos-1};unsigned d;
        for(d=0;d<4;d++)if(next[d]>=0 && next[d]<XL_CELLS && cells[next[d]]=='.' && !seen[next[d]]){seen[next[d]]=TRUE;queue[tail++]=next[d];}
    }
    for(i=0;i<XL_CELLS;i++)if(cells[i]=='.' && !seen[i])return FALSE;
    memcpy(sXLTemplate,cells,XL_CELLS);sXLStaged=TRUE;
#if GENERATED_WILDS_CAST
    sXLCastStaged=FALSE;
#if GENERATED_WILDS_EVENTS
    sEventStaged=FALSE;
#endif
#endif
    sLargeStaged=FALSE;sLargeShared=FALSE;sHasTemplate=FALSE;sLargeWilds=FALSE;
#if GENERATED_CAVE_PROFILES
    sEncounterProfile=0;sSharedEncounterProfile=FALSE;
#endif
#if GENERATED_CAVE_WILDLIFE
    sHasWildlife=sSharedWildlife=FALSE;
#endif
    return TRUE;
#else
    (void)cells;(void)size;return FALSE;
#endif
}

/* Validate all geometry before staging. Shared input is accepted only from
 * the version-negotiated, integrity-checked authority path. */
#if GENERATED_MAP_READY && GENERATED_MAP_LARGE
static bool8 StageLarge(const u8 *cells, u32 size, bool8 shared)
{
    u8 seen[LARGE_CELLS] = {0};
    u16 queue[LARGE_CELLS], head = 0, tail = 0, i;
    if (!cells || size != LARGE_CELLS || (shared != WorldBridge_Enabled())) return FALSE;
    if (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        return shared && sLargeActive && sLargeShared && !memcmp(cells, sLargeTemplate, LARGE_CELLS);
    for (i = 0; i < LARGE_CELLS; i++) {
        unsigned x = i % LARGE_SIDE, y = i / LARGE_SIDE;
        if ((cells[i] != '.' && cells[i] != '#') ||
            ((x == 0 || y == 0 || x == LARGE_SIDE - 1 || y == LARGE_SIDE - 1) && cells[i] != '#')) return FALSE;
    }
    if (cells[LARGE_SIDE + 1] != '.' || cells[60 * LARGE_SIDE + 61] != '.' || cells[61 * LARGE_SIDE + 61] != '.') return FALSE;
    queue[tail++] = LARGE_SIDE + 1; seen[LARGE_SIDE + 1] = TRUE;
    while (head < tail) {
        s16 pos = queue[head++], neighbor[4] = {pos - LARGE_SIDE, pos + 1, pos + LARGE_SIDE, pos - 1};
        unsigned d;
        for (d = 0; d < 4; d++) {
            s16 next = neighbor[d];
            if (next >= 0 && next < LARGE_CELLS && cells[next] == '.' && !seen[next]) {
                seen[next] = TRUE; queue[tail++] = next;
            }
        }
    }
    for (i = 0; i < LARGE_CELLS; i++) if (cells[i] == '.' && !seen[i]) return FALSE;
    memcpy(sLargeTemplate, cells, LARGE_CELLS);
    sLargeStaged = TRUE; sLargeShared = shared; sHasTemplate = FALSE;
#if GENERATED_WORLD_XL
    sXLStaged = FALSE;
#endif
#if GENERATED_MAP_WILDS
    sLargeWilds = FALSE;
#if GENERATED_WILDS_GUIDE
    sGuideStaged = sGuideShared = FALSE;
#if GENERATED_WILDS_CAST
    sCastStaged = FALSE;
#if GENERATED_WILDS_EVENTS
    sEventStaged = FALSE;
#if GENERATED_WILDS_SHARED_TERRAIN
    sSharedTerrainSize = 0;
#endif
#endif
#endif
#endif
#endif
#if GENERATED_CAVE_PROFILES
    sEncounterProfile = 0; sSharedEncounterProfile = FALSE;
#endif
#if GENERATED_CAVE_WILDLIFE
    sHasWildlife = sSharedWildlife = FALSE;
#endif
    return TRUE;
}
#endif
bool8 GeneratedMap_StageLargeTemplate(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_MAP_LARGE
    return StageLarge(cells, size, FALSE);
#else
    (void)cells; (void)size; return FALSE;
#endif
}
bool8 GeneratedMap_StageWildsTemplate(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_MAP_WILDS
    if (!StageLarge(cells, size, FALSE)) return FALSE;
    sLargeWilds = TRUE;
    return TRUE;
#else
    (void)cells; (void)size; return FALSE;
#endif
}
#if GENERATED_MAP_READY && GENERATED_WILDS_GUIDE
static bool8 ValidateGuideText(const u8 *meta, u32 size)
{
    unsigned i, n, line = 0, lines = 1, visible = 0;
    if (!meta || size != GENERATED_GUIDE_BYTES || (meta[0] != 7 && meta[0] != 8)) return FALSE;
    n = meta[1]; if (!n || n > 57) return FALSE;
    for (i = 0; i < n; i++) {
        u8 c = meta[2 + i];
        if (c == '\n') { if (!line || !visible || ++lines > 2) return FALSE; line = visible = 0; }
        else {
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
                  || c == ' ' || c == '.' || c == ',' || c == '!' || c == '?' || c == '\'' || c == '-')) return FALSE;
            if (++line > 28) return FALSE;
            if (c != ' ') visible++;
        }
    }
    if (!line || !visible) return FALSE;
    for (i = n; i < 57; i++) if (meta[2 + i]) return FALSE;
    return TRUE;
}
static bool8 ValidateGuideGeometry(const u8 *cells, u32 size)
{
    u8 seen[LARGE_CELLS] = {0}; u16 queue[LARGE_CELLS], head=0, tail=0, i;
    const unsigned guide = LARGE_SIDE + 2;
    if (!cells || size != LARGE_CELLS || cells[guide] != '.' || cells[2 * LARGE_SIDE + 1] != '.') return FALSE;
    queue[tail++] = LARGE_SIDE + 1; seen[LARGE_SIDE + 1] = TRUE;
    while (head < tail) {
        s16 pos=queue[head++], neighbors[4]={pos-LARGE_SIDE,pos+1,pos+LARGE_SIDE,pos-1}; unsigned d;
        for (d=0;d<4;d++) { s16 next=neighbors[d];
            if (next>=0 && next<LARGE_CELLS && next!=(s16)guide && cells[next]=='.' && !seen[next]) {
                seen[next]=TRUE; queue[tail++]=next;
            }
        }
    }
    for (i=0;i<LARGE_CELLS;i++) if (i!=guide && cells[i]=='.' && !seen[i]) return FALSE;
    return TRUE;
}
static void EncodeGuideText(const u8 *meta, u8 *out)
{
    unsigned i;
    for (i=0;i<meta[1];i++) {
        u8 c=meta[2+i], v=0;
        if(c>='A' && c<='Z') v=0xBB+c-'A';
        else if(c>='a' && c<='z') v=0xD5+c-'a';
        else if(c>='0' && c<='9') v=0xA1+c-'0';
        else switch(c) {case '\n':v=0xFE;break;case '.':v=0xAD;break;case ',':v=0xB8;break;
            case '!':v=0xAB;break;case '?':v=0xAC;break;case '\'':v=0xB4;break;case '-':v=0xAE;break;default:break;}
        out[i]=v;
    }
    out[meta[1]]=0xFF;
}
#endif
bool8 GeneratedMap_StageXLCast(const u8 *meta,u32 metaSize,const u8 *cells,u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WORLD_XL && GENERATED_WILDS_CAST
    u8 seen[XL_CELLS]={0},blocked[XL_CELLS]={0},guide[GENERATED_GUIDE_BYTES];u16 queue[XL_CELLS],head=0,tail=0,i;unsigned n,j,d;
    u8 *texts[3]={gGeneratedWildsGuideText,gGeneratedWildsCastText2,gGeneratedWildsCastText3};
    if(!meta || metaSize!=GENERATED_CAST_BYTES || !cells || size!=XL_CELLS || WorldBridge_Enabled() || GeneratedMap_IsInside() || GeneratedMap_EntryPending())return FALSE;
    n=meta[0];if(!n || n>3)return FALSE;
    for(j=0;j<3;j++){const u8 *r=meta+1+j*61;unsigned x=r[1],y=r[2];
        if(j>=n){for(d=0;d<61;d++)if(r[d])return FALSE;continue;}
        if(!x || x>=126 || !y || y>=126 || (x==1 && y==1) || (x==125 && (y==124 || y==125)))return FALSE;
        i=y*XL_SIDE+x;if(cells[i]!='.' || blocked[i])return FALSE;blocked[i]=TRUE;
        guide[0]=r[0];guide[1]=r[3];memcpy(guide+2,r+4,57);if(!ValidateGuideText(guide,sizeof(guide)))return FALSE;
    }
    queue[tail++]=XL_SIDE+1;seen[XL_SIDE+1]=TRUE;
    while(head<tail){s16 pos=queue[head++],next[4]={pos-XL_SIDE,pos+1,pos+XL_SIDE,pos-1};
        for(d=0;d<4;d++)if(next[d]>=0 && next[d]<XL_CELLS && !blocked[next[d]] && cells[next[d]]=='.' && !seen[next[d]]){seen[next[d]]=TRUE;queue[tail++]=next[d];}}
    for(i=0;i<XL_CELLS;i++)if(cells[i]=='.' && !blocked[i] && !seen[i])return FALSE;
    for(j=0;j<n;j++){const u8 *r=meta+1+j*61;unsigned pos=r[2]*XL_SIDE+r[1];
        if(!seen[pos-XL_SIDE] && !seen[pos+1] && !seen[pos+XL_SIDE] && !seen[pos-1])return FALSE;}
    if(!GeneratedMap_StageXLWilds(cells,size))return FALSE;
    memcpy(sCastMetadata,meta,GENERATED_CAST_BYTES);sXLCastStaged=TRUE;
    for(j=0;j<n;j++){const u8 *r=meta+1+j*61;guide[0]=r[0];guide[1]=r[3];memcpy(guide+2,r+4,57);EncodeGuideText(guide,texts[j]);}
    return TRUE;
#else
    (void)meta;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
#if GENERATED_MAP_READY && GENERATED_WILDS_GUIDE
static bool8 StageGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size, bool8 shared)
{
    if (!ValidateGuideText(metadata,metaSize) || !ValidateGuideGeometry(cells,size)) return FALSE;
    if (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        return shared && sGuideActive && sGuideShared && !memcmp(metadata,sGuideMetadata,GENERATED_GUIDE_BYTES)
            && !memcmp(cells,sLargeTemplate,LARGE_CELLS);
    if (!StageLarge(cells,size,shared)) return FALSE;
    sLargeWilds=TRUE; sGuideStaged=TRUE; sGuideShared=shared; sGuideGfx=metadata[0];
    memcpy(sGuideMetadata,metadata,GENERATED_GUIDE_BYTES); EncodeGuideText(metadata,gGeneratedWildsGuideText);
    return TRUE;
}
#endif
bool8 GeneratedMap_StageGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_GUIDE
    return StageGuidedWilds(metadata,metaSize,cells,size,FALSE);
#else
    (void)metadata;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_StageSharedGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_GUIDE
    return StageGuidedWilds(metadata,metaSize,cells,size,TRUE);
#else
    (void)metadata;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_MatchesPreparedGuidedWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_GUIDE
    return metadata && metaSize==GENERATED_GUIDE_BYTES && cells && size==LARGE_CELLS && sGuideActive && sPrepared
        && (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        && !memcmp(metadata,sGuideMetadata,GENERATED_GUIDE_BYTES) && !memcmp(cells,sLargeTemplate,LARGE_CELLS);
#else
    (void)metadata;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
#if GENERATED_MAP_READY && GENERATED_WILDS_CAST
static bool8 ValidateCast(const u8 *meta, u32 metaSize, const u8 *cells, u32 size)
{
    static const u8 xs[3]={2,20,40}, ys[3]={1,20,40};
    u8 seen[LARGE_CELLS]={0}, blocked[LARGE_CELLS]={0}, guide[GENERATED_GUIDE_BYTES];
    u16 queue[LARGE_CELLS],head=0,tail=0,i; unsigned n,j,d;
    if (!meta || metaSize!=GENERATED_CAST_BYTES || !cells || size!=LARGE_CELLS) return FALSE;
    n=meta[0]; if (!n || n>3) return FALSE;
    for (j=0;j<3;j++) {
        const u8 *record=meta+1+j*61;
        if (j>=n) { for (d=0;d<61;d++) if(record[d]) return FALSE; continue; }
        if(record[1]!=xs[j] || record[2]!=ys[j]) return FALSE;
        guide[0]=record[0];guide[1]=record[3];memcpy(guide+2,record+4,57);
        if(!ValidateGuideText(guide,sizeof(guide))) return FALSE;
        i=ys[j]*LARGE_SIDE+xs[j]; if(cells[i]!='.') return FALSE; blocked[i]=TRUE;
    }
    if(cells[LARGE_SIDE+1]!='.') return FALSE;
    queue[tail++]=LARGE_SIDE+1;seen[LARGE_SIDE+1]=TRUE;
    while(head<tail) {
        s16 pos=queue[head++],neighbors[4]={pos-LARGE_SIDE,pos+1,pos+LARGE_SIDE,pos-1};
        for(d=0;d<4;d++) {s16 next=neighbors[d];
            if(next>=0 && next<LARGE_CELLS && !blocked[next] && cells[next]=='.' && !seen[next]) {
                seen[next]=TRUE;queue[tail++]=next;
            }
        }
    }
    for(i=0;i<LARGE_CELLS;i++) if(cells[i]=='.' && !blocked[i] && !seen[i]) return FALSE;
    for(j=0;j<n;j++) if(!seen[ys[j]*LARGE_SIDE+xs[j]-1]) return FALSE;
    return TRUE;
}
#endif
#if GENERATED_MAP_READY && GENERATED_WILDS_CAST
static bool8 StageCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size, bool8 shared)
{
    u8 guide[GENERATED_GUIDE_BYTES];u8 *texts[3]={gGeneratedWildsGuideText,gGeneratedWildsCastText2,gGeneratedWildsCastText3};unsigned j;
    if(!ValidateCast(metadata,metaSize,cells,size)) return FALSE;
    if (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        return shared && sCastActive && sLargeShared && !memcmp(metadata,sCastMetadata,GENERATED_CAST_BYTES) && !memcmp(cells,sLargeTemplate,LARGE_CELLS);
    if(!StageLarge(cells,size,shared)) return FALSE;
    sLargeWilds=TRUE;sCastStaged=TRUE;memcpy(sCastMetadata,metadata,GENERATED_CAST_BYTES);
    for(j=0;j<metadata[0];j++) {const u8 *record=metadata+1+j*61;
        guide[0]=record[0];guide[1]=record[3];memcpy(guide+2,record+4,57);EncodeGuideText(guide,texts[j]);
    }
    return TRUE;
}
#endif
bool8 GeneratedMap_StageCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_CAST
    return StageCastWilds(metadata,metaSize,cells,size,FALSE);
#else
    (void)metadata;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
static bool8 ValidateEventRules(const u8 *events,u32 eventSize,const u8 *cast,u32 castSize)
{
    u8 guide[GENERATED_GUIDE_BYTES], used[16][3]={{0}};unsigned j,k,n;
    if(!events || eventSize!=GENERATED_EVENT_BYTES || !cast || castSize!=GENERATED_CAST_BYTES || events[0]>15) return FALSE;
    n=events[1];if(!n || n>24 || !cast[0] || cast[0]>3)return FALSE;
    guide[0]=7;
    for(j=0;j<24;j++) {const u8 *r=events+2+j*61;
        if(j>=n) {for(k=0;k<61;k++)if(r[k])return FALSE;continue;}
        if(r[0]>15 || !r[1] || r[1]>cast[0] || r[2]>15 || used[r[0]][r[1]-1])return FALSE;
        used[r[0]][r[1]-1]=TRUE;guide[1]=r[3];memcpy(guide+2,r+4,57);
        if(!ValidateGuideText(guide,sizeof(guide)))return FALSE;
    }
    return TRUE;
}
static bool8 StageEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size, bool8 shared)
{
    if(!cells || size!=LARGE_CELLS || !ValidateEventRules(events,eventSize,cast,castSize))return FALSE;
    if (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        return shared && sEventActive && sLargeShared && !memcmp(events,sEventData,GENERATED_EVENT_BYTES)
            && !memcmp(cast,sCastMetadata,GENERATED_CAST_BYTES) && !memcmp(cells,sLargeTemplate,LARGE_CELLS);
    if(!StageCastWilds(cast,castSize,cells,size,shared))return FALSE;
    memcpy(sEventData,events,GENERATED_EVENT_BYTES);sEventStaged=TRUE;return TRUE;
}
#endif
bool8 GeneratedMap_StageXLEvents(const u8 *events,u32 eventSize,const u8 *cast,u32 castSize,const u8 *cells,u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WORLD_XL && GENERATED_WILDS_EVENTS
    if(!ValidateEventRules(events,eventSize,cast,castSize) || !GeneratedMap_StageXLCast(cast,castSize,cells,size))return FALSE;
    memcpy(sEventData,events,GENERATED_EVENT_BYTES);sEventStaged=TRUE;return TRUE;
#else
    (void)events;(void)eventSize;(void)cast;(void)castSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_StageEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    return StageEventWilds(events,eventSize,cast,castSize,cells,size,FALSE);
#else
    (void)events;(void)eventSize;(void)cast;(void)castSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_StageSharedEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    return StageEventWilds(events,eventSize,cast,castSize,cells,size,TRUE);
#else
    (void)events;(void)eventSize;(void)cast;(void)castSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_MatchesPreparedEventWilds(const u8 *events, u32 eventSize, const u8 *cast, u32 castSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    return events && eventSize==GENERATED_EVENT_BYTES && cast && castSize==GENERATED_CAST_BYTES && cells && size==LARGE_CELLS
        && sEventActive && sPrepared && (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        && !memcmp(events,sEventData,GENERATED_EVENT_BYTES) && !memcmp(cast,sCastMetadata,GENERATED_CAST_BYTES) && !memcmp(cells,sLargeTemplate,LARGE_CELLS);
#else
    (void)events;(void)eventSize;(void)cast;(void)castSize;(void)cells;(void)size;return FALSE;
#endif
}
void GeneratedMap_RunEvent(void)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    const u8 *fallback[3]={gGeneratedWildsGuideText,gGeneratedWildsCastText2,gGeneratedWildsCastText3};
    unsigned j,npc=gSpecialVar_LastTalked;u8 guide[GENERATED_GUIDE_BYTES];
    if(!sEventActive || !npc || npc>sCastMetadata[0]) {gGeneratedEventText[0]=0xFF;return;}
    memcpy(gGeneratedEventText,fallback[npc-1],58);
    for(j=0;j<sEventRuntime[1];j++) {const u8 *r=sEventRuntime+2+j*61;
        if(r[0]==sEventState && r[1]==npc) {guide[0]=7;guide[1]=r[3];memcpy(guide+2,r+4,57);
            EncodeGuideText(guide,gGeneratedEventText);sEventState=r[2];
#if GENERATED_WORLD_XL
            if(sXLActive && !WorldBridge_Enabled())XLRememberEventProgress();
#endif
            break;}
    }
#endif
}
u8 GeneratedMap_EventState(void)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    return sEventActive ? sEventState : 0;
#else
    return 0;
#endif
}
bool8 GeneratedMap_SetSharedEventState(u8 state)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    if(state>15 || !sEventActive || !sLargeShared || !GeneratedMap_IsInside())return FALSE;
    sEventState=state;return TRUE;
#else
    (void)state;return FALSE;
#endif
}
bool8 GeneratedMap_SetSharedEventRule(const u8 *rule, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    u8 guide[GENERATED_GUIDE_BYTES];unsigned j,n;
    if(!rule || size!=61 || !sEventActive || !sLargeShared || !GeneratedMap_IsInside()
       || rule[0]>15 || !rule[1] || rule[1]>sCastMetadata[0] || rule[2]>15) return FALSE;
    guide[0]=7;guide[1]=rule[3];memcpy(guide+2,rule+4,57);
    if(!ValidateGuideText(guide,sizeof(guide)))return FALSE;
    n=sEventRuntime[1];
    for(j=0;j<n;j++) {u8 *r=sEventRuntime+2+j*61;if(r[0]==rule[0] && r[1]==rule[1])break;}
    if(j==n && n>=24)return FALSE;
    memcpy(sEventRuntime+2+j*61,rule,61);if(j==n)sEventRuntime[1]=n+1;
    return TRUE;
#else
    (void)rule;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_SetSharedEventTile(unsigned x, unsigned y, unsigned terrain)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    u16 tile;
    if(terrain>1 || !sEventActive || !sLargeShared || !GeneratedMap_IsInside()
       || !GeneratedMap_SharedCoordValid(x,y) || (x==1 && y==1) || (x==61 && (y==60 || y==61)))return FALSE;
    tile=terrain ? 0x300d : 0x3001;
    sLargeTiles[y*LARGE_SIDE+x]=tile;
    MapGridSetMetatileEntryAt(x+MAP_OFFSET,y+MAP_OFFSET,tile);
    CurrentMapDrawMetatileAt(x+MAP_OFFSET,y+MAP_OFFSET);
    return TRUE;
#else
    (void)x;(void)y;(void)terrain;return FALSE;
#endif
}
bool8 GeneratedMap_SetSharedEventTiles(const u8 *patch, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_EVENTS
    unsigned i,j,n,x,y,t;
    if(!patch || !size || !(n=patch[0]) || n>64 || size!=1+3*n || !sEventActive || !sLargeShared || !GeneratedMap_IsInside())return FALSE;
    for(i=0;i<n;i++) {x=patch[1+i*3];y=patch[2+i*3];t=patch[3+i*3];
        if(t>1 || !GeneratedMap_SharedCoordValid(x,y) || (x==1 && y==1) || (x==61 && (y==60 || y==61)))return FALSE;
        for(j=0;j<i;j++)if(patch[1+j*3]==x && patch[2+j*3]==y)return FALSE;
    }
    for(i=0;i<n;i++)GeneratedMap_SetSharedEventTile(patch[1+i*3],patch[2+i*3],patch[3+i*3]);
    return TRUE;
#else
    (void)patch;(void)size;return FALSE;
#endif
}
#if GENERATED_MAP_READY && GENERATED_WILDS_SHARED_GEOMETRY
static bool8 TerrainHeader(const u8 *patch,u32 size,unsigned *count,unsigned *offset)
{
    unsigned n,off;if(!patch || !size)return FALSE;
#if GENERATED_WILDS_LARGE_TERRAIN
    if(patch[0]==255){if(size<3)return FALSE;n=patch[1]|((unsigned)patch[2]<<8);off=3;if(n<=64 || n>512)return FALSE;}
    else
#endif
    {n=patch[0];off=1;if(n>64)return FALSE;}
    if(size!=off+3*n)return FALSE;
    *count=n;*offset=off;return TRUE;
}
#endif
#if GENERATED_MAP_READY && GENERATED_WILDS_SHARED_GEOMETRY
static bool8 BuildSharedWalk(const u8 *patch, u32 size, u8 *walk)
{
    u8 seen[LARGE_CELLS]={0};u16 queue[LARGE_CELLS],head=0,tail=0,i;unsigned n,off,j,lastX=0,lastY=0,d;
    if(!walk || !TerrainHeader(patch,size,&n,&off) || !sLargeStaged || !sLargeShared || !sLargeWilds || !sEventStaged)return FALSE;
    for(i=0;i<LARGE_CELLS;i++)walk[i]=sLargeTemplate[i]=='.';
    walk[LARGE_SIDE+2]=FALSE;if(sCastMetadata[0]>=2)walk[20*LARGE_SIDE+20]=FALSE;if(sCastMetadata[0]>=3)walk[40*LARGE_SIDE+40]=FALSE;
    for(j=0;j<n;j++){unsigned x=patch[off+3*j],y=patch[off+3*j+1],kind=patch[off+3*j+2];
        if(kind>2 || !x || x>=62 || !y || y>=62 || (x==1 && y==1) || (x==61 && (y==60 || y==61))
         || (x==2 && y==1) || (sCastMetadata[0]>=2 && x==20 && y==20) || (sCastMetadata[0]>=3 && x==40 && y==40)
         || (j && (x<lastX || (x==lastX && y<=lastY))))return FALSE;
        walk[y*LARGE_SIDE+x]=kind!=2;lastX=x;lastY=y;
    }
    if(!walk[LARGE_SIDE+1] || !walk[60*LARGE_SIDE+61] || !walk[61*LARGE_SIDE+61])return FALSE;
    for(j=0;j<sCastMetadata[0];j++){unsigned x=sCastMetadata[2+j*61],y=sCastMetadata[3+j*61],pos=y*LARGE_SIDE+x;
        if(!walk[pos-LARGE_SIDE] && !walk[pos+1] && !walk[pos+LARGE_SIDE] && !walk[pos-1])return FALSE;
    }
    queue[tail++]=LARGE_SIDE+1;seen[LARGE_SIDE+1]=TRUE;
    while(head<tail){s16 pos=queue[head++],neighbors[4]={pos-LARGE_SIDE,pos+1,pos+LARGE_SIDE,pos-1};
        for(d=0;d<4;d++){s16 next=neighbors[d];if(next>=0 && next<LARGE_CELLS && walk[next] && !seen[next]){seen[next]=TRUE;queue[tail++]=next;}}
    }
    for(i=0;i<LARGE_CELLS;i++)if(walk[i] && !seen[i])return FALSE;
    return TRUE;
}
#endif
bool8 GeneratedMap_ValidateSharedTerrain(const u8 *patch, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_SHARED_GEOMETRY
    u8 walk[LARGE_CELLS];return BuildSharedWalk(patch,size,walk);
#elif GENERATED_MAP_READY && GENERATED_WILDS_SHARED_TERRAIN
    unsigned n,i,lastX=0,lastY=0;
    if(!patch || !size || (n=patch[0])>64 || size!=1+3*n || !sLargeStaged || !sLargeShared || !sLargeWilds || !sEventStaged)return FALSE;
    for(i=0;i<n;i++){unsigned x=patch[1+3*i],y=patch[2+3*i],kind=patch[3+3*i];
        if(kind>1 || !GeneratedMap_SharedCoordValid(x,y) || (x==1 && y==1) || (x==61 && (y==60 || y==61))
           || (i && (x<lastX || (x==lastX && y<=lastY))))return FALSE;
        lastX=x;lastY=y;
    }
    return TRUE;
#else
    (void)patch;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_SharedTerrainNeedsGeometry(const u8 *patch, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_SHARED_GEOMETRY
    unsigned i,n,off;if(!GeneratedMap_ValidateSharedTerrain(patch,size) || !TerrainHeader(patch,size,&n,&off))return TRUE;
    for(i=0;i<n;i++){unsigned x=patch[off+3*i],y=patch[off+3*i+1];if(patch[off+3*i+2]==2 || sLargeTemplate[y*LARGE_SIDE+x]!='.')return TRUE;}
    return FALSE;
#else
    (void)patch;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_StageSharedTerrain(const u8 *patch, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_SHARED_TERRAIN
    if(GeneratedMap_IsInside() || GeneratedMap_EntryPending() || !GeneratedMap_ValidateSharedTerrain(patch,size))return FALSE;
#if GENERATED_WILDS_SHARED_GEOMETRY
    if(!BuildSharedWalk(patch,size,sSharedWalk))return FALSE;
#endif
    memcpy(sSharedTerrain,patch,size);sSharedTerrainSize=size;return TRUE;
#else
    (void)patch;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_ApplySharedTerrain(const u8 *patch, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_SHARED_GEOMETRY
    u8 walk[LARGE_CELLS];unsigned i,n,off;
    if(!GeneratedMap_IsInside() || !BuildSharedWalk(patch,size,walk) || !TerrainHeader(patch,size,&n,&off) || memcmp(walk,sSharedWalk,LARGE_CELLS))return FALSE;
    for(i=0;i<n;i++)if(patch[off+3*i+2]!=2 && !GeneratedMap_SetSharedEventTile(patch[off+3*i],patch[off+3*i+1],patch[off+3*i+2]))return FALSE;
    memcpy(sSharedTerrain,patch,size);sSharedTerrainSize=size;return TRUE;
#elif GENERATED_MAP_READY && GENERATED_WILDS_SHARED_TERRAIN
    if(!GeneratedMap_IsInside() || !GeneratedMap_ValidateSharedTerrain(patch,size))return FALSE;
    if(patch[0] && !GeneratedMap_SetSharedEventTiles(patch,size))return FALSE;
    memcpy(sSharedTerrain,patch,size);sSharedTerrainSize=size;return TRUE;
#else
    (void)patch;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_StageSharedCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_CAST
    return StageCastWilds(metadata,metaSize,cells,size,TRUE);
#else
    (void)metadata;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_MatchesPreparedCastWilds(const u8 *metadata, u32 metaSize, const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_WILDS_CAST
    return metadata && metaSize==GENERATED_CAST_BYTES && cells && size==LARGE_CELLS && sCastActive && sPrepared
#if GENERATED_WILDS_EVENTS
        && !sEventActive
#endif
        && (GeneratedMap_IsInside() || GeneratedMap_EntryPending()) && !memcmp(metadata,sCastMetadata,GENERATED_CAST_BYTES)
        && !memcmp(cells,sLargeTemplate,LARGE_CELLS);
#else
    (void)metadata;(void)metaSize;(void)cells;(void)size;return FALSE;
#endif
}
bool8 GeneratedMap_StageSharedWildsTemplate(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_MAP_WILDS
    if (!StageLarge(cells, size, TRUE)) return FALSE;
    sLargeWilds = TRUE;
    return TRUE;
#else
    (void)cells; (void)size; return FALSE;
#endif
}
bool8 GeneratedMap_MatchesPreparedWilds(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_MAP_WILDS
    return cells && size == LARGE_CELLS && sLargeWilds && sLargeActive && sPrepared
#if GENERATED_WILDS_GUIDE
        && !sGuideActive
#if GENERATED_WILDS_CAST
        && !sCastActive
#endif
#endif
        && (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        && !memcmp(cells, sLargeTemplate, LARGE_CELLS);
#else
    (void)cells; (void)size; return FALSE;
#endif
}
bool8 GeneratedMap_StageSharedLargeTemplate(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_MAP_LARGE
    return StageLarge(cells, size, TRUE);
#else
    (void)cells; (void)size; return FALSE;
#endif
}
bool8 GeneratedMap_MatchesPreparedLarge(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_MAP_LARGE
    return cells && size == LARGE_CELLS && sLargeActive && sPrepared
#if GENERATED_MAP_WILDS
        && !sLargeWilds
#endif
#if GENERATED_CAVE_WILDLIFE
        && !sHasWildlife
#endif
        && (GeneratedMap_IsInside() || GeneratedMap_EntryPending())
        && !memcmp(cells, sLargeTemplate, LARGE_CELLS);
#else
    (void)cells; (void)size; return FALSE;
#endif
}

bool8 GeneratedMap_MatchesPreparedLargeWildlife(const u8 *cells, u32 size, u8 profile, const u8 *data, u32 dataSize)
{
#if GENERATED_MAP_READY && GENERATED_MAP_LARGE && GENERATED_CAVE_WILDLIFE
    return cells && size == LARGE_CELLS && sLargeActive && sPrepared && sHasWildlife
#if GENERATED_MAP_WILDS
        && !sLargeWilds
#endif
        && (GeneratedMap_IsInside() || GeneratedMap_EntryPending()) && profile == sEncounterProfile
        && data && dataSize == GENERATED_WILDLIFE_BYTES && !memcmp(data, sWildlifeRaw, GENERATED_WILDLIFE_BYTES)
        && !memcmp(cells, sLargeTemplate, LARGE_CELLS);
#else
    (void)cells; (void)size; (void)profile; (void)data; (void)dataSize; return FALSE;
#endif
}

/* Profiles are bounded native table choices, not executable data. */
bool8 GeneratedMap_SetEncounterProfile(u8 profile)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_PROFILES
    if ((!sHasTemplate
#if GENERATED_MAP_LARGE
         && !sLargeStaged
#endif
        ) || profile > 3) return FALSE;
    sEncounterProfile = profile;
    sSharedEncounterProfile = FALSE;
    return TRUE;
#else
    (void)profile;
    return FALSE;
#endif
}

bool8 GeneratedMap_SetSharedEncounterProfile(u8 profile)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_PROFILES
    if ((!sHasTemplate
#if GENERATED_MAP_LARGE
         && !sLargeStaged
#endif
        ) || profile > 3) return FALSE;
    sEncounterProfile = profile;
    sSharedEncounterProfile = TRUE;
    return TRUE;
#else
    (void)profile;
    return FALSE;
#endif
}

u8 GeneratedMap_EncounterProfile(void)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_PROFILES
    if (sPrepared && (sHasTemplate
#if GENERATED_MAP_LARGE
        || sLargeStaged
#endif
        ) && GeneratedMap_IsInside()
     && (!WorldBridge_Enabled() || sSharedEncounterProfile))
        return sEncounterProfile;
#endif
    return 0;
}

/* Versioned wildlife is bounded data, never scripts or pointers from a file. */
bool8 GeneratedMap_ValidateWildlife(const u8 *data, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_WILDLIFE
    unsigned i;
    if (!data || size != GENERATED_WILDLIFE_BYTES || data[0] < 1 || data[0] > 100) return FALSE;
    for (i = 0; i < 12; i++) {
        unsigned offset = 1 + i * 3;
        u16 species = data[offset] | ((u16)data[offset + 1] << 8);
        u8 level = data[offset + 2];
        if (!species || species >= SPECIES_EGG
         || (species >= SPECIES_OLD_UNOWN_B && species <= SPECIES_OLD_UNOWN_Z)
         || level < 1 || level > 100) return FALSE;
    }
    return TRUE;
#else
    (void)data; (void)size;
    return FALSE;
#endif
}

bool8 GeneratedMap_SetWildlife(const u8 *data, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_WILDLIFE
    unsigned i;
    if ((!sHasTemplate
#if GENERATED_MAP_LARGE
         && !sLargeStaged
#endif
        ) || !GeneratedMap_ValidateWildlife(data, size)) return FALSE;
    for (i = 0; i < 12; i++) {
        unsigned offset = 1 + i * 3;
        sWildlifeMons[i].species = data[offset] | ((u16)data[offset + 1] << 8);
        sWildlifeMons[i].minLevel = sWildlifeMons[i].maxLevel = data[offset + 2];
    }
    sWildlifeInfo.encounterRate = data[0];
    sWildlifeInfo.wildPokemon = sWildlifeMons;
    memcpy(sWildlifeRaw, data, GENERATED_WILDLIFE_BYTES);
    sSharedWildlife = FALSE;
    sHasWildlife = TRUE;
    return TRUE;
#else
    (void)data; (void)size;
    return FALSE;
#endif
}

bool8 GeneratedMap_SetSharedWildlife(const u8 *data, u32 size)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_WILDLIFE
    if (!GeneratedMap_SetWildlife(data, size)) return FALSE;
    sSharedWildlife = TRUE;
    return TRUE;
#else
    (void)data; (void)size; return FALSE;
#endif
}

const struct WildPokemonInfo *GeneratedMap_Wildlife(void)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_WILDLIFE
    if (sHasWildlife && sPrepared && (sHasTemplate
#if GENERATED_MAP_LARGE
        || sLargeStaged
#endif
        ) && GeneratedMap_IsInside() && (!WorldBridge_Enabled() || sSharedWildlife))
        return &sWildlifeInfo;
#endif
    return NULL;
}

bool8 GeneratedMap_IsInside(void)
{
#if GENERATED_MAP_READY
    return gSaveBlock1Ptr && ((gSaveBlock1Ptr->location.mapGroup == MAP_GROUP(MAP_GENERATED_WORLD_CAVE)
        && gSaveBlock1Ptr->location.mapNum == MAP_NUM(MAP_GENERATED_WORLD_CAVE))
#if GENERATED_MAP_WILDS
        || (gSaveBlock1Ptr->location.mapGroup == MAP_GROUP(MAP_GENERATED_WORLD_WILDS)
        && gSaveBlock1Ptr->location.mapNum == MAP_NUM(MAP_GENERATED_WORLD_WILDS))
#endif
        );
#else
    return FALSE;
#endif
}

#if GENERATED_MAP_READY
static bool8 HasFreeWarpTask(void)
{
    u8 i;
    for (i = 0; i < NUM_TASKS; i++) if (!gTasks[i].isActive) return TRUE;
    return FALSE;
}

static bool8 GetReturnCoords(s16 *x, s16 *y)
{
    if (!gSaveBlock1Ptr || !gMapHeader.mapLayout || !x || !y) return FALSE;
    PlayerGetDestCoords(x, y);
    *x -= MAP_OFFSET;
    *y -= MAP_OFFSET;
    return *x >= 0 && *y >= 0 && *x <= 127 && *y <= 127
        && *x < gMapHeader.mapLayout->width && *y < gMapHeader.mapLayout->height;
}
#endif

bool8 GeneratedMap_EntryPending(void)
{
#if GENERATED_MAP_READY
    return sPrepared && !sSeenInside && !GeneratedMap_IsInside();
#else
    return FALSE;
#endif
}

bool8 GeneratedMap_MatchesPrepared(const u8 *cells, u32 size)
{
#if GENERATED_MAP_READY
    u16 i;
#if GENERATED_MAP_LARGE
    if (sLargeActive) return FALSE;
#endif
    if (!cells || size != GEN_CELLS || !sPrepared
     || (!GeneratedMap_IsInside() && !GeneratedMap_EntryPending())) return FALSE;
    for (i = 0; i < GEN_CELLS; i++)
        if ((cells[i] == '.') != (sTiles[i] == GEN_FLOOR || sTiles[i] == GEN_EXIT
#if GENERATED_MAP_AUTOTILE
                               || sTiles[i] == GEN_AUTOFLOOR
#endif
#if GENERATED_CAVE_BIOMES
                               || sTiles[i] == 0x3201 || sTiles[i] == 0x3207
                               || sTiles[i] == 0x3385 || sTiles[i] == 0x3386
#endif
                               )) return FALSE;
    return TRUE;
#else
    (void)cells; (void)size;
    return FALSE;
#endif
}

bool8 GeneratedMap_MatchesPreparedProfile(const u8 *cells, u32 size, u8 profile)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_PROFILES
#if GENERATED_CAVE_WILDLIFE
    if (sHasWildlife) return FALSE;
#endif
    return profile <= 3 && profile == sEncounterProfile && GeneratedMap_MatchesPrepared(cells, size);
#else
    return profile == 0 && GeneratedMap_MatchesPrepared(cells, size);
#endif
}

bool8 GeneratedMap_MatchesPreparedWildlife(const u8 *cells, u32 size, u8 profile, const u8 *data, u32 dataSize)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_WILDLIFE
    return sHasWildlife && profile == sEncounterProfile && data && dataSize == GENERATED_WILDLIFE_BYTES
        && !memcmp(sWildlifeRaw, data, GENERATED_WILDLIFE_BYTES) && GeneratedMap_MatchesPrepared(cells, size);
#else
    (void)cells; (void)size; (void)profile; (void)data; (void)dataSize; return FALSE;
#endif
}

bool8 GeneratedMap_SharedCoordValid(unsigned x, unsigned y)
{
#if GENERATED_MAP_READY
#if GENERATED_MAP_LARGE
    if (sLargeStaged && sLargeShared)
        return x < LARGE_SIDE && y < LARGE_SIDE
#if GENERATED_WILDS_GUIDE
            && !(sGuideStaged && sGuideShared && x == 2 && y == 1)
#if GENERATED_WILDS_CAST
            && !(sCastStaged && ((x==2 && y==1) || (sCastMetadata[0]>=2 && x==20 && y==20) || (sCastMetadata[0]>=3 && x==40 && y==40)))
#endif
#endif
#if GENERATED_WILDS_SHARED_GEOMETRY
            && (sSharedTerrainSize ? sSharedWalk[y*LARGE_SIDE+x] : sLargeTemplate[y*LARGE_SIDE+x]=='.');
#else
            && sLargeTemplate[y * LARGE_SIDE + x] == '.';
#endif
#endif
    return sHasTemplate && x < GEN_SIDE && y < GEN_SIDE && sTemplate[y * GEN_SIDE + x] == '.';
#else
    (void)x; (void)y;
    return FALSE;
#endif
}

bool8 GeneratedMap_CanEnter(void)
{
#if GENERATED_MAP_READY
    s16 x, y;
    struct WorldRallySnapshot rally;
    if (WorldRally_HasReturn() || (WorldRally_GetSnapshot(&rally) && rally.id)) return FALSE;
    return gSaveBlock1Ptr && !sPrepared && !GeneratedMap_IsInside() && HasFreeWarpTask()
        && !LinkTransport_TagPeer()
        && !LinkTransport_PendingTag() && !LinkTransport_PendingInvitation()
        && (!WorldBridge_Enabled() || (WorldBridge_GeneratedCaveReady() && (sHasTemplate
#if GENERATED_MAP_LARGE
            || (sLargeStaged && sLargeShared)
#endif
        )))
        && IsMapTypeOutdoors(gMapHeader.mapType)
        && TestPlayerAvatarFlags(PLAYER_AVATAR_FLAG_ON_FOOT)
        && GetReturnCoords(&x, &y);
#else
    return FALSE;
#endif
}

bool8 GeneratedMap_Enter(void)
{
#if GENERATED_MAP_READY
    s16 x, y;
    if (!GeneratedMap_CanEnter() || !GetReturnCoords(&x, &y)
     || (!WorldBridge_Enabled() && !Platform_ReloadGeneratedMap())) return FALSE;
    sReturn = gSaveBlock1Ptr->location;
    sReturn.warpId = WARP_ID_NONE;
    sReturn.x = x;
    sReturn.y = y;
    sPreviousDynamicWarp = gSaveBlock1Ptr->dynamicWarp;
    SetDynamicWarpWithCoords(0, sReturn.mapGroup, sReturn.mapNum, WARP_ID_NONE, sReturn.x, sReturn.y);
    sSeenInside = FALSE;
#if GENERATED_WORLD_XL
    sXLActive=sXLStaged && !WorldBridge_Enabled();
#endif
#if GENERATED_MAP_LARGE
    sLargeActive = sLargeStaged && (!WorldBridge_Enabled() || sLargeShared);
#if GENERATED_WILDS_GUIDE
    sGuideActive = sLargeActive && sLargeWilds && sGuideStaged;
#if GENERATED_WILDS_CAST
    sCastActive = (sLargeActive && sLargeWilds && sCastStaged)
#if GENERATED_WORLD_XL
        || (sXLActive && sXLCastStaged)
#endif
        ;
#if GENERATED_WILDS_EVENTS
    sEventActive = sCastActive && sEventStaged;
    if(sEventActive) {sEventState=sEventData[0];memcpy(sEventRuntime,sEventData,GENERATED_EVENT_BYTES);
#if GENERATED_WORLD_XL
        XLRestoreEventProgress();
#endif
    }
#endif
#endif
#endif
#if GENERATED_WORLD_XL
    if(sXLActive) {u16 i;for(i=0;i<XL_CELLS;i++){unsigned x=i%XL_SIDE,y=i/XL_SIDE;
        sXLTiles[i]=sXLTemplate[i]=='.' ? (((x*13+y*7)%5) ? 0x300d : 0x3001) : 0x0487;}
        sXLTiles[XL_SIDE+1]=0x3001;sXLTiles[125*XL_SIDE+125]=0x3024;
    } else
#endif
    if (sLargeActive) {
        u16 i;
#if GENERATED_MAP_WILDS
        if (sLargeWilds) {
            for (i = 0; i < LARGE_CELLS; i++) {
                unsigned x = i % LARGE_SIDE, y = i / LARGE_SIDE;
                /* Deterministic walkable path and grass. Blocked cells are water. */
                sLargeTiles[i] = sLargeTemplate[i] == '.' ? (((x * 13 + y * 7) % 5) ? 0x300d : 0x3001) : 0x0487;
            }
            sLargeTiles[LARGE_SIDE + 1] = 0x3001;
            sLargeTiles[61 * LARGE_SIDE + 61] = 0x3024;
#if GENERATED_WILDS_SHARED_TERRAIN
            if(sSharedTerrainSize) {unsigned j,n,off;
#if GENERATED_WILDS_SHARED_GEOMETRY
                if(TerrainHeader(sSharedTerrain,sSharedTerrainSize,&n,&off))
#else
                n=sSharedTerrain[0];off=1;
#endif
                for(j=0;j<n;j++) {unsigned x=sSharedTerrain[off+3*j],y=sSharedTerrain[off+3*j+1],kind=sSharedTerrain[off+3*j+2];
                    sLargeTiles[y*LARGE_SIDE+x]=kind==2 ? 0x0487 : kind ? 0x300d : 0x3001;
                }
            }
#endif
        } else
#endif
        {
            for (i = 0; i < LARGE_CELLS; i++) sLargeTiles[i] = sLargeTemplate[i] == '.' ? GEN_FLOOR : GEN_WALL;
            sLargeTiles[61 * LARGE_SIDE + 61] = GEN_EXIT;
        }
    } else
#endif
    if (sHasTemplate)
    {
        u16 i;
        for (i = 0; i < GEN_CELLS; i++) sTiles[i] = sTemplate[i] == '.' ? GEN_FLOOR : GEN_WALL;
        sTiles[29 * GEN_SIDE + 29] = GEN_EXIT;
    }
    else
        BuildMaze(gMain.vblankCounter1 ^ ((u32)sReturn.mapGroup << 24) ^ ((u32)sReturn.mapNum << 16));
#if GENERATED_MAP_AUTOTILE
#if GENERATED_MAP_WILDS
    if (!sLargeActive || !sLargeWilds)
#endif
#if GENERATED_WORLD_XL
    if (!sXLActive)
#endif
        GeneratedMap_Autotile();
#endif
    sPrepared = TRUE;
#if GENERATED_MAP_WILDS
    if ((sLargeActive && sLargeWilds)
#if GENERATED_WORLD_XL
        || sXLActive
#endif
       )
        SetWarpDestination(MAP_GROUP(MAP_GENERATED_WORLD_WILDS), MAP_NUM(MAP_GENERATED_WORLD_WILDS), WARP_ID_NONE, 1, 1);
    else
#endif
        SetWarpDestination(MAP_GROUP(MAP_GENERATED_WORLD_CAVE), MAP_NUM(MAP_GENERATED_WORLD_CAVE), WARP_ID_NONE, 1, 1);
    StoreInitialPlayerAvatarState();
    DoWarp();
    return TRUE;
#else
    return FALSE;
#endif
}

bool8 GeneratedMap_Leave(void)
{
#if GENERATED_MAP_READY
    if (!GeneratedMap_IsInside() || !sPrepared || !HasFreeWarpTask()) return FALSE;
    SetWarpDestination(sReturn.mapGroup, sReturn.mapNum, WARP_ID_NONE, sReturn.x, sReturn.y);
    StoreInitialPlayerAvatarState();
    DoWarp();
    return TRUE;
#else
    return FALSE;
#endif
}

const struct MapLayout *GeneratedMap_ResolveLayout(const struct MapLayout *base)
{
#if GENERATED_MAP_READY
    if (base && sPrepared && GeneratedMap_IsInside())
    {
        sSeenInside = TRUE;
        sLayout = *base;
#if GENERATED_WORLD_XL
        if(sXLActive && gMapHeader.events && gMapHeader.events->warpCount==1 && gMapHeader.events->warps) {
            sXLEvents=*gMapHeader.events;sXLWarp=gMapHeader.events->warps[0];sXLWarp.x=125;sXLWarp.y=125;sXLEvents.warps=&sXLWarp;
#if GENERATED_WILDS_CAST
            if(sCastActive && sXLCastStaged) {unsigned j;const u8 *scripts[3]={GeneratedWorld_Wilds_EventScript_Guide,GeneratedWorld_Wilds_EventScript_Cast2,GeneratedWorld_Wilds_EventScript_Cast3};
                memset(sGuideObjects,0,sizeof(sGuideObjects));for(j=0;j<sCastMetadata[0];j++){const u8 *r=sCastMetadata+1+j*61;
                    sGuideObjects[j].localId=j+1;sGuideObjects[j].graphicsId=r[0];sGuideObjects[j].x=r[1];sGuideObjects[j].y=r[2];sGuideObjects[j].elevation=3;sGuideObjects[j].movementType=MOVEMENT_TYPE_FACE_LEFT;sGuideObjects[j].script=scripts[j];
#if GENERATED_WILDS_EVENTS
                    if(sEventActive)sGuideObjects[j].script=GeneratedWorld_Wilds_EventScript_Graph;
#endif
                }
                sXLEvents.objectEventCount=sCastMetadata[0];sXLEvents.objectEvents=sGuideObjects;
            }
#endif
            gMapHeader.events=&sXLEvents;
        }
#endif
#if GENERATED_WILDS_GUIDE
#if GENERATED_WILDS_CAST
        if (sCastActive && sLargeWilds && gMapHeader.events) {
            static const u8 *const scripts[3]={GeneratedWorld_Wilds_EventScript_Guide,GeneratedWorld_Wilds_EventScript_Cast2,GeneratedWorld_Wilds_EventScript_Cast3};
            unsigned j;
            sGuideEvents=*gMapHeader.events;memset(sGuideObjects,0,sizeof(sGuideObjects));
            for(j=0;j<sCastMetadata[0];j++) {const u8 *record=sCastMetadata+1+j*61;
                sGuideObjects[j].localId=j+1;sGuideObjects[j].graphicsId=record[0];
                sGuideObjects[j].x=record[1];sGuideObjects[j].y=record[2];sGuideObjects[j].elevation=3;
                sGuideObjects[j].movementType=MOVEMENT_TYPE_FACE_LEFT;sGuideObjects[j].script=scripts[j];
#if GENERATED_WILDS_EVENTS
                if(sEventActive)sGuideObjects[j].script=GeneratedWorld_Wilds_EventScript_Graph;
#endif
            }
            sGuideEvents.objectEventCount=sCastMetadata[0];sGuideEvents.objectEvents=sGuideObjects;gMapHeader.events=&sGuideEvents;
        } else
#endif
        if (sGuideActive && sLargeWilds && gMapHeader.events) {
            sGuideEvents = *gMapHeader.events;
            memset(sGuideObjects, 0, sizeof(sGuideObjects));
            sGuideObjects[0].localId = 1;
            sGuideObjects[0].graphicsId = sGuideGfx;
            sGuideObjects[0].x = 2; sGuideObjects[0].y = 1; sGuideObjects[0].elevation = 3;
            sGuideObjects[0].movementType = MOVEMENT_TYPE_FACE_LEFT;
            sGuideObjects[0].script = GeneratedWorld_Wilds_EventScript_Guide;
            sGuideEvents.objectEventCount = 1; sGuideEvents.objectEvents = sGuideObjects;
            gMapHeader.events = &sGuideEvents;
        }
#endif
#if GENERATED_MAP_LARGE
#if GENERATED_WORLD_XL
        sLayout.width = sLayout.height = sXLActive ? XL_SIDE : sLargeActive ? LARGE_SIDE : GEN_SIDE;
        sLayout.map = sXLActive ? sXLTiles : sLargeActive ? sLargeTiles : sTiles;
#else
        sLayout.width = sLayout.height = sLargeActive ? LARGE_SIDE : GEN_SIDE;
        sLayout.map = sLargeActive ? sLargeTiles : sTiles;
#endif
#else
        sLayout.width = sLayout.height = GEN_SIDE;
        sLayout.map = sTiles;
#endif
        return &sLayout;
    }
    if (sPrepared && sSeenInside && !GeneratedMap_IsInside())
    {
        gSaveBlock1Ptr->dynamicWarp = sPreviousDynamicWarp;
        sPrepared = sSeenInside = FALSE;
    }
#endif
    return base;
}
#endif
