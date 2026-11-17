#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int16_t s16;typedef int bool8;typedef int bool32;
#define TRUE 1
#define FALSE 0
#define OBJECT_EVENTS_COUNT 8
#define SAVED_OBJECT_EVENTS_COUNT 8
#define MAP_OFFSET 7
#define MOVEMENT_TYPE_NONE 0
#define MOVEMENT_TYPE_FOLLOW_PLAYER 1
#define COLLISION_NONE 0
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
#define MAP_GROUP(x) 34
#define MAP_GENERATED_WORLD_CAVE 1
#define DIR_EAST 1
#define DIR_WEST 2
#define DIR_SOUTH 3
#define DIR_NORTH 4
#define OBJ_EVENT_ID_FOLLOWER 250
#define OBJ_EVENT_MON 32768
#define OWE_GENERATED 1
#define GENERATED_MAP_READY 0
struct Coords16{s16 x,y;};
struct ObjectEvent {u8 active,isPlayer,localId,mapGroup,mapNum,trainerRange_berryTreeId,currentElevation,singleMovementActive,heldMovementActive,heldMovementFinished,movementType,spriteId;u16 graphicsId;struct Coords16 currentCoords,previousCoords;};
struct ObjectEventTemplate{u8 localId,elevation,movementType,trainerRange_berryTreeId;u16 graphicsId;s16 x,y;const u8*script;};
struct WarpEvent{s16 x,y;};
static struct ObjectEvent gObjectEvents[8];
static struct {u8 warpCount,objectEventCount;struct WarpEvent warps[8];} events;
static struct {typeof(events)*events;} gMapHeader={&events};
static struct {struct{u8 mapGroup,mapNum;}location;struct ObjectEvent objectEvents[8];struct ObjectEventTemplate objectEventTemplates[8];} save,*gSaveBlock1Ptr=&save;
static struct {u8 objectEventId;}gPlayerAvatar;
static void CB2_Overworld(void){}static void otherCallback(void){}
static struct {bool8 inBattle;void(*callback2)(void);}gMain;
static unsigned removes,spawns,moves,spawnFail,collision,onFoot=1,ready=1,busy=0,script=0,stockFollower=0,terrain=0,elevation=3,blockedTile=0;
const u8 WorldApprenticeOuting_EventScript_Companion[]={2};
static bool8 WorldApprentice_WalkingReady(u8*id){*id=2;return ready;}
static bool8 ScriptContext_IsEnabled(void){return script;}
static bool8 WorldActivity_OwnsFieldInput(void){return busy;}
static bool8 PlayerHasFollowerNPC(void){return stockFollower;}
static bool8 TestPlayerAvatarFlags(unsigned f){return onFoot;}
#define ARRAY_COUNT(x) (sizeof(x)/sizeof((x)[0]))
#define NUM_APPRENTICES 16
static const struct {u8 facilityClass;} gApprentices[16]={[2]={4}};
static const struct {u8 class;u16 gfxId;} gTowerMaleFacilityClasses[]={{1,24}};
static const struct {u8 class;u16 gfxId;} gTowerFemaleFacilityClasses[]={{4,25}};
ACTUAL_GRAPHICS
static u8 MapGridGetCollisionAt(s16 x,s16 y){return blockedTile;}
static u8 MapGridGetElevationAt(s16 x,s16 y){return elevation;}
static u8 MapGridGetMetatileBehaviorAt(s16 x,s16 y){return terrain;}
static bool8 MetatileBehavior_IsSurfableWaterOrUnderwater(u8 b){return b==1;}
static bool8 MetatileBehavior_IsDoor(u8 b){return b==2;}
static bool8 MetatileBehavior_IsWarpDoor(u8 b){return b==3;}
static bool8 MetatileBehavior_IsEscalator(u8 b){return b==4;}
static bool8 MetatileBehavior_IsLadder(u8 b){return b==5;}
static bool8 MetatileBehavior_IsNonAnimDoor(u8 b){return b==6;}
static void RemoveObjectEvent(struct ObjectEvent*o){assert(o>=gObjectEvents&&o<gObjectEvents+8);assert(o->active);o->active=0;removes++;}
static unsigned SpawnSpecialObjectEvent(struct ObjectEventTemplate*t){spawns++;if(spawnFail)return 8;for(unsigned i=1;i<8;i++)if(!gObjectEvents[i].active){gObjectEvents[i]=(struct ObjectEvent){.active=1,.localId=t->localId,.mapGroup=save.location.mapGroup,.mapNum=save.location.mapNum,.graphicsId=t->graphicsId,.trainerRange_berryTreeId=t->trainerRange_berryTreeId,.currentElevation=t->elevation,.currentCoords={t->x+7,t->y+7},.previousCoords={t->x+7,t->y+7}};return i;}return 8;}
static bool8 ObjectEventClearHeldMovementIfFinished(struct ObjectEvent*o){if(!o->heldMovementFinished)return 0;o->heldMovementActive=0;return 1;}
static unsigned GetCollisionAtCoords(struct ObjectEvent*o,s16 x,s16 y,u8 dir){return collision;}
static u8 GetWalkNormalMovementAction(u8 dir){return dir;}
static bool8 ObjectEventSetHeldMovement(struct ObjectEvent*o,u8 dir){moves++;o->previousCoords=o->currentCoords;if(dir==1)o->currentCoords.x++;if(dir==2)o->currentCoords.x--;if(dir==3)o->currentCoords.y++;if(dir==4)o->currentCoords.y--;o->heldMovementActive=1;o->heldMovementFinished=1;return 0;}
#include "ACTUAL_SOURCE"
static void WorldBridge_PrepareSave(void){}
static bool8 IsOverworldWildEncounter(struct ObjectEvent*o,unsigned t){return 0;}
static void ClearNativeOWEEncounter(void*p){}
static void SetMinimumOWESpawnTimer(void){}
static bool8 FollowerNPC_IsCollisionExempt(struct ObjectEvent*a,struct ObjectEvent*b){return 0;}
static bool8 AreElevationsCompatible(u8 a,u8 b){return a==b;}
static bool8 DespawnOWEDueToNPCCollision(struct ObjectEvent*a,struct ObjectEvent*b){return 0;}
static void TryTriggerOverworldWildEncounter(struct ObjectEvent*a,struct ObjectEvent*b){}
ACTUAL_SAVE_COLLISION
static void reset(void){WorldApprenticeWalk_Forget();memset(gObjectEvents,0,sizeof(gObjectEvents));memset(&save,0,sizeof(save));memset(&events,0,sizeof(events));gMain.callback2=CB2_Overworld;gMain.inBattle=0;gObjectEvents[0]=(struct ObjectEvent){.active=1,.isPlayer=1,.currentElevation=3,.currentCoords={10,10},.previousCoords={10,10}};ready=onFoot=1;busy=script=stockFollower=terrain=blockedTile=spawnFail=collision=removes=spawns=moves=0;elevation=3;}
static void step(void){gObjectEvents[0].previousCoords=gObjectEvents[0].currentCoords;gObjectEvents[0].currentCoords.x++;WorldApprenticeWalk_Update();}
int main(void){assert(Apprentice_GetOutingGraphics(2)==25);assert(Apprentice_GetOutingGraphics(16)==0xFFFF);reset();WorldApprenticeWalk_Update();step();
#if !EW_APPRENTICE_WALKING
assert(!sWalk.spawned&&!spawns);return 0;
#else
assert(sWalk.spawned&&spawns==1);unsigned slot=sWalk.slot;assert(gObjectEvents[slot].currentCoords.x==10);assert(WorldApprenticeWalk_Template(159,0,0));assert(!WorldApprenticeWalk_Template(159,1,0));
assert(GetObjectObjectCollidesWith(&gObjectEvents[0],10,10,0)==8);gObjectEvents[2]=(struct ObjectEvent){.active=1,.currentElevation=3,.currentCoords={12,10},.previousCoords={12,10}};assert(GetObjectObjectCollidesWith(&gObjectEvents[slot],12,10,0)==2);gObjectEvents[2].active=0;
step();assert(moves==1&&gObjectEvents[slot].currentCoords.x==11);assert(sWalk.spawned);gObjectEvents[3]=(struct ObjectEvent){.active=1,.localId=30,.graphicsId=99,.currentCoords={40,40},.previousCoords={40,40}};struct ObjectEvent unrelated=gObjectEvents[3];SaveObjectEvents();struct ObjectEvent zero={0};assert(!memcmp(&save.objectEvents[slot],&zero,sizeof(zero)));assert(gObjectEvents[slot].active);LoadObjectEvents();assert(!sWalk.spawned&&!gObjectEvents[slot].active);assert(gObjectEvents[3].active&&gObjectEvents[3].graphicsId==unrelated.graphicsId&&gObjectEvents[3].localId==30);
reset();WorldApprenticeWalk_Update();spawnFail=1;step();assert(!sWalk.spawned);spawnFail=0;WorldApprenticeWalk_Update();assert(sWalk.spawned);slot=sWalk.slot;gObjectEvents[slot].trainerRange_berryTreeId=0;WorldApprenticeWalk_LeaveField();assert(gObjectEvents[slot].active&&!removes);
reset();WorldApprenticeWalk_Update();events.objectEventCount=1;save.objectEventTemplates[0].localId=159;step();assert(!spawns);
reset();WorldApprenticeWalk_Update();step();save.location.mapNum=1;gObjectEvents[1].active=0;WorldApprenticeWalk_Update();assert(!sWalk.spawned&&!removes);step();assert(sWalk.spawned);
reset();WorldApprenticeWalk_Update();step();onFoot=0;WorldApprenticeWalk_Update();assert(!sWalk.spawned&&removes==1);
reset();WorldApprenticeWalk_Update();step();ready=0;WorldApprenticeWalk_Update();assert(!sWalk.spawned&&removes==1);
reset();WorldApprenticeWalk_Update();step();WorldApprenticeWalk_LeaveField();assert(!sWalk.spawned&&removes==1);gMain.inBattle=1;WorldApprenticeWalk_Update();assert(removes==1);
reset();WorldApprenticeWalk_Update();terrain=1;step();assert(!spawns);terrain=0;blockedTile=1;WorldApprenticeWalk_Update();assert(!spawns);blockedTile=0;events.warpCount=1;events.warps[0]=(struct WarpEvent){3,3};WorldApprenticeWalk_Update();assert(!spawns);
reset();WorldApprenticeWalk_Update();step();gObjectEvents[0].currentCoords.x+=2;WorldApprenticeWalk_Update();assert(!sWalk.spawned&&removes==1);
reset();WorldApprenticeWalk_Update();step();gMain.callback2=otherCallback;WorldApprenticeWalk_Update();assert(!removes);gMain.callback2=CB2_Overworld;script=1;WorldApprenticeWalk_Update();assert(!removes&&sWalk.spawned);script=0;ready=0;WorldApprenticeWalk_Update();assert(removes==1);
puts("walking, slot failure, native save/load and native collision checks passed");return 0;
#endif
}
