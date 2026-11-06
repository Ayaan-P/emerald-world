#ifndef MOCK_H
#define MOCK_H
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16;
#define OBJECT_EVENTS_COUNT 16
#define MAX_SPRITES 64
#define MAP_OFFSET 7
#define OBJ_EVENT_GFX_BOY_1 1
#define OBJ_EVENT_GFX_GIRL_1 2
#define MOVEMENT_TYPE_NONE 0
struct Coord { s16 x,y; };
struct ObjectEvent { int active,isPlayer,graphicsId,localId,mapGroup,mapNum,spriteId, currentElevation,previousElevation,facingDirection; struct Coord currentCoords,initialCoords; };
struct Sprite { int inUse; s16 data[8]; };
struct ObjectEventTemplate { int localId; };
struct Save { struct { int mapGroup,mapNum; } location; struct ObjectEventTemplate objectEventTemplates[64]; struct ObjectEvent objectEvents[OBJECT_EVENTS_COUNT]; };
struct Layout { int width,height; }; struct Events { int objectEventCount; };
struct Header { struct Layout *mapLayout; struct Events *events; };
extern struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT]; extern struct Sprite gSprites[MAX_SPRITES];
extern struct Save *gSaveBlock1Ptr; extern struct Header gMapHeader;
void RemoveObjectEvent(struct ObjectEvent *); int ScriptContext_IsEnabled(void); int FuncIsActiveTask(void (*)(u8)); void Task_ShowStartMenu(u8);
u8 SpawnSpecialObjectEventParameterized(int,int,int,int,int,int); int MapGridGetElevationAt(int,int);
void MoveObjectEventToMapCoords(struct ObjectEvent *,int,int); void ObjectEventTurn(struct ObjectEvent *,int);
#endif
