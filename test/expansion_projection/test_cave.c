#include "stub.h"
#include <assert.h>
#include <string.h>
bool8 ExpansionCave_Leave(void);bool8 ExpansionCave_Stage(const uint8_t *,size_t);bool8 ExpansionCave_Enter(void);bool8 ExpansionCave_IsInside(void);const struct MapLayout *ExpansionCave_ResolveLayout(const struct MapLayout *);const struct MapHeader *ExpansionCave_Header(void);void ExpansionCave_Update(void);
static struct SaveBlock1 save={.location={1,2,0,4,5},.dynamicWarp={3,4,0,6,7}};struct SaveBlock1 *gSaveBlock1Ptr=&save;void *gSaveBlock2Ptr=&save;
static u16 original[100];static struct MapLayout base={10,10,original};struct MapHeader gMapHeader={.mapLayout=&base,.mapType=1};
void CB1_Overworld(void){} void CB2_Overworld(void){} struct Main gMain={CB1_Overworld,CB2_Overworld,0};struct PaletteFade gPaletteFade;struct Task gTasks[NUM_TASKS];
u32 flash_write_count(void){return 0;}u8 TrySavingData(u8 x){(void)x;return 255;}
int ScriptContext_IsEnabled(void){return 0;}int ArePlayerFieldControlsLocked(void){return 0;}int IsMapTypeOutdoors(int t){return t;}int TestPlayerAvatarFlags(int x){return x;}void PlayerGetDestCoords(s16 *x,s16 *y){*x=11;*y=12;}
void SetDynamicWarpWithCoords(int a,s8 g,s8 n,s8 w,s8 x,s8 y){(void)a;save.dynamicWarp=(struct WarpData){g,n,w,x,y};}
void SetWarpDestination(s8 g,s8 n,s8 w,s8 x,s8 y){save.location=(struct WarpData){g,n,w,x,y};}void StoreInitialPlayerAvatarState(void){}void DoWarp(void){}
const struct MapHeader *Overworld_GetMapHeaderByGroupAndId(u16 g,u16 n){(void)g;(void)n;return &gMapHeader;}
int main(void){uint8_t p[8+31*31];memset(p,'#',sizeof p);memcpy(p,"EWGMAP01",8);for(int y=1;y<30;y++)p[8+y*31+1]='.';for(int x=1;x<30;x++)p[8+28*31+x]='.';p[8+29*31+29]='.';
 assert(ExpansionCave_Stage(p,sizeof p));assert(ExpansionCave_Enter());assert(ExpansionCave_IsInside());const struct MapLayout *l=ExpansionCave_ResolveLayout(&base);assert(l->width==31&&l->height==31&&l->map[32]==0x3333);const struct MapHeader *h=ExpansionCave_Header();assert(h->events->warpCount==1&&h->events->warps[0].x==29);assert(!ExpansionCave_Enter());assert(ExpansionCave_Leave());assert(save.location.mapGroup==1&&save.location.mapNum==2);ExpansionCave_Update();assert(ExpansionCave_Header()->events->warpCount==1);assert(save.dynamicWarp.mapGroup==3&&save.dynamicWarp.mapNum==4);return 0;}
