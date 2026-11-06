#include "stub.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
struct PlayerAvatar gPlayerAvatar;
void GetXYCoordsOneStepInFrontOfPlayer(s16 *x,s16 *y) { *x=11; *y=12; }
struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT]; struct Sprite gSprites[MAX_SPRITES];
struct Save save; struct Save *gSaveBlock1Ptr=&save; struct Layout layout={100,100};
struct Events events; struct Header gMapHeader={&layout,&events};
static int scripts, menus;
void RemoveObjectEvent(struct ObjectEvent *o) { gSprites[o->spriteId].inUse=0; o->active=0; }
int ScriptContext_IsEnabled(void) { return scripts; }
int FuncIsActiveTask(void (*f)(u8)) { (void)f; return menus; }
void Task_ShowStartMenu(u8 n) { (void)n; }
int MapGridGetElevationAt(int x,int y) { (void)x; (void)y; return 1; }
void MoveObjectEventToMapCoords(struct ObjectEvent *o,int x,int y) { o->currentCoords.x=x; o->currentCoords.y=y; }
void ObjectEventTurn(struct ObjectEvent *o,int d) { o->facingDirection=d; }
u8 SpawnSpecialObjectEventParameterized(int gfx,int movement,int local,int x,int y,int elev) {
    int i; (void)gfx; (void)movement; (void)elev;
    for (i=0;i<OBJECT_EVENTS_COUNT;i++) if (!gObjectEvents[i].active) {
        struct ObjectEvent *o=&gObjectEvents[i]; memset(o,0,sizeof *o); o->active=1; o->graphicsId=gfx; o->localId=local;
        o->mapGroup=save.location.mapGroup; o->mapNum=save.location.mapNum; o->spriteId=i;
        o->currentCoords.x=x; o->currentCoords.y=y; gSprites[i].inUse=1; gSprites[i].data[0]=i; return i;
    }
    return OBJECT_EVENTS_COUNT;
}
void ExpansionPeers_Update(int);
const char *ExpansionPeers_Facing(void);
u8 __wrap_GetObjectEventIdByPosition(u16,u16,u8);
u8 __real_GetObjectEventIdByPosition(u16 x,u16 y,u8 e) { (void)y; (void)e; return x; }
void __wrap_SaveObjectEvents(void);
void __wrap_CopyPartyAndObjectsToSave(void);
void __real_SaveObjectEvents(void) { memcpy(save.objectEvents,gObjectEvents,sizeof gObjectEvents); }
void __real_CopyPartyAndObjectsToSave(void) { __real_SaveObjectEvents(); }
int main(void) {
    char path[]="/tmp/ew-peers-XXXXXX"; int fd=mkstemp(path); assert(fd>=0); close(fd); assert(!setenv("EW_EXPANSION_PEERS",path,1));
    FILE *f=fopen(path,"w"); assert(f); fputs("EWPEERS 1\nAsh 0 0 4 5 2 1\n",f); fclose(f);
    ExpansionPeers_Update(1); assert(gObjectEvents[0].active); assert(gObjectEvents[0].currentCoords.x==11); assert(gObjectEvents[0].facingDirection==2); assert(!strcmp(ExpansionPeers_Facing(),"Ash"));
    gObjectEvents[1].active=1; gObjectEvents[1].localId=1;
    assert(__wrap_GetObjectEventIdByPosition(0,0,0)==OBJECT_EVENTS_COUNT);
    assert(__wrap_GetObjectEventIdByPosition(1,0,0)==1);
    __wrap_SaveObjectEvents(); assert(!save.objectEvents[0].active && save.objectEvents[1].active);
    __wrap_CopyPartyAndObjectsToSave(); assert(!save.objectEvents[0].active && save.objectEvents[1].active);
    f=fopen(path,"w"); assert(f); fputs("EWPEERS 1\nAsh 0 0 6 5 3 2\n",f); fclose(f);
    ExpansionPeers_Update(1); assert(gObjectEvents[0].active && gObjectEvents[0].graphicsId==2);
    assert(gObjectEvents[0].currentCoords.x==13 && gObjectEvents[0].facingDirection==3);
    scripts=1; ExpansionPeers_Update(1); assert(!gObjectEvents[0].active); scripts=0;
    f=fopen(path,"w"); assert(f); fputs("EWPEERS 1\nAsh 0 0 4 5 2 1\nAsh 0 0 4 5 2 1\n",f); fclose(f);
    ExpansionPeers_Update(1); assert(!gObjectEvents[0].active);
    unlink(path); return 0;
}
