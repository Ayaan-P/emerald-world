#ifndef CAVE_STUB_H
#define CAVE_STUB_H
#include <stdint.h>
#include <stddef.h>
typedef uint32_t u32; typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16; typedef int8_t s8; typedef int bool8;
#define TRUE 1
#define FALSE 0
#define MAP_OFFSET 7
#define NUM_TASKS 4
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
#define MAP_CAVE_OF_ORIGIN_ENTRANCE 0x0201
#define MAP_DYNAMIC 0x7f7f
#define MAP_GROUP(m) ((m)>>8)
#define MAP_NUM(m) ((m)&255)
#define WARP_ID_DYNAMIC 0x7f
#define WARP_ID_NONE -1
struct WarpData { s8 mapGroup,mapNum,warpId; s16 x,y; };
struct SaveBlock1 { struct WarpData location,dynamicWarp; }; extern struct SaveBlock1 *gSaveBlock1Ptr; extern void *gSaveBlock2Ptr;
struct MapLayout { int width,height; const u16 *map; };
struct WarpEvent { s16 x,y; u8 elevation,warpId,mapNum,mapGroup; };
struct MapEvents { u8 warpCount; const struct WarpEvent *warps; };
struct MapHeader { const struct MapLayout *mapLayout; const struct MapEvents *events; const u8 *mapScripts; void *connections; int mapType; int allowEscaping,allowCycling; };
extern struct MapHeader gMapHeader;
struct Main {void (*callback1)(void);void (*callback2)(void);int inBattle;}; extern struct Main gMain;
struct PaletteFade { int active; }; extern struct PaletteFade gPaletteFade;
struct Task {int isActive;}; extern struct Task gTasks[NUM_TASKS];
void CB1_Overworld(void);void CB2_Overworld(void);int ScriptContext_IsEnabled(void);int ArePlayerFieldControlsLocked(void);int IsMapTypeOutdoors(int);int TestPlayerAvatarFlags(int);void PlayerGetDestCoords(s16 *,s16 *);
void SetDynamicWarpWithCoords(int,s8,s8,s8,s8,s8);void SetWarpDestination(s8,s8,s8,s8,s8);void StoreInitialPlayerAvatarState(void);void DoWarp(void);
const struct MapHeader *Overworld_GetMapHeaderByGroupAndId(u16,u16);
#endif
#define SELECT_BUTTON 4
#define R_BUTTON 256
