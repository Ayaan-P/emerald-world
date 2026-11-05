#ifdef PORTABLE
#include "global.h"
#include "main.h"
#include "overworld.h"
#include "field_screen_effect.h"
#include "field_player_avatar.h"
#include "fieldmap.h"
#include "platform/world_bridge.h"
#include "platform/generated_map.h"
#include "constants/maps.h"
#include <string.h>

#if GENERATED_MAP_READY
/* 31x31 fits the stock backup-map buffer even with its view border. The
 * cave palette and metatiles come from the existing Cave of Origin layout. */
#define GEN_SIDE 31
#define GEN_CELLS (GEN_SIDE * GEN_SIDE)
#define GEN_FLOOR 0x3333
#define GEN_WALL 0x0722
#define GEN_EXIT 0x3323
#define GEN_MAX_NODES 225

static u16 sTiles[GEN_CELLS];
static u8 sTemplate[GEN_CELLS];
static bool8 sHasTemplate;
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
    return TRUE;
#else
    (void)cells; (void)size;
    return FALSE;
#endif
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

bool8 GeneratedMap_CanEnter(void)
{
#if GENERATED_MAP_READY
    s16 x, y;
    return gSaveBlock1Ptr && !GeneratedMap_IsInside() && !WorldBridge_Enabled()
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
     || !Platform_ReloadGeneratedMap()) return FALSE;
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
    if (!GeneratedMap_IsInside() || !sPrepared) return FALSE;
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
