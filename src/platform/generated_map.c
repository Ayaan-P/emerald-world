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
#include "constants/maps.h"
#if GENERATED_CAVE_WILDLIFE
#include "wild_encounter.h"
#include "constants/species.h"
#endif
#include <string.h>

#if GENERATED_MAP_READY
/* 31x31 fits the stock backup-map buffer even with its view border. The
 * cave palette and metatiles come from the existing Cave of Origin layout. */
#define GEN_SIDE 31
#define GEN_CELLS (GEN_SIDE * GEN_SIDE)
#define GEN_FLOOR 0x3333
#define GEN_WALL 0x0722
#define GEN_EXIT 0x3323
#define GEN_AUTOFLOOR 0x331b
#define GEN_MAX_NODES 225

static u16 sTiles[GEN_CELLS];
static u8 sTemplate[GEN_CELLS];
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
    u8 walkable[GEN_CELLS];
    u16 i;
    for (i = 0; i < GEN_CELLS; i++)
        walkable[i] = sTiles[i] == GEN_FLOOR || sTiles[i] == GEN_EXIT;
    for (i = 0; i < GEN_CELLS; i++)
    {
        unsigned x = i % GEN_SIDE, y = i / GEN_SIDE, mask = 0;
        if (walkable[i])
        {
            sTiles[i] = sTiles[i] == GEN_EXIT ? exit : floor;
            continue;
        }
        if (y > 0 && walkable[i - GEN_SIDE]) mask |= 1;
        if (x + 1 < GEN_SIDE && walkable[i + 1]) mask |= 2;
        if (y + 1 < GEN_SIDE && walkable[i + GEN_SIDE]) mask |= 4;
        if (x > 0 && walkable[i - 1]) mask |= 8;
        sTiles[i] = 0x400 | walls[mask];
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

/* Profiles are bounded native table choices, not executable data. */
bool8 GeneratedMap_SetEncounterProfile(u8 profile)
{
#if GENERATED_MAP_READY && GENERATED_CAVE_PROFILES
    if (!sHasTemplate || profile > 3) return FALSE;
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
    if (!sHasTemplate || profile > 3) return FALSE;
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
    if (sPrepared && sHasTemplate && GeneratedMap_IsInside()
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
    if (!sHasTemplate || !GeneratedMap_ValidateWildlife(data, size)) return FALSE;
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
    if (sHasWildlife && sPrepared && sHasTemplate && GeneratedMap_IsInside() && (!WorldBridge_Enabled() || sSharedWildlife))
        return &sWildlifeInfo;
#endif
    return NULL;
}

bool8 GeneratedMap_IsInside(void)
{
#if GENERATED_MAP_READY
    return gSaveBlock1Ptr && gSaveBlock1Ptr->location.mapGroup == MAP_GROUP(MAP_GENERATED_WORLD_CAVE)
        && gSaveBlock1Ptr->location.mapNum == MAP_NUM(MAP_GENERATED_WORLD_CAVE);
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
        && (!WorldBridge_Enabled() || (WorldBridge_GeneratedCaveReady() && sHasTemplate))
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
    if (sHasTemplate)
    {
        u16 i;
        for (i = 0; i < GEN_CELLS; i++) sTiles[i] = sTemplate[i] == '.' ? GEN_FLOOR : GEN_WALL;
        sTiles[29 * GEN_SIDE + 29] = GEN_EXIT;
    }
    else
        BuildMaze(gMain.vblankCounter1 ^ ((u32)sReturn.mapGroup << 24) ^ ((u32)sReturn.mapNum << 16));
#if GENERATED_MAP_AUTOTILE
    GeneratedMap_Autotile();
#endif
    sPrepared = TRUE;
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
        sLayout.width = sLayout.height = GEN_SIDE;
        sLayout.map = sTiles;
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
