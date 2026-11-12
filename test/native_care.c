#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
#define MAP_ROUTE104 19
#define MAP_GROUP(x) ((x)>>8)
#define MAP_NUM(x) ((x)&255)
struct BerryTree {unsigned berry,stage,watered,berryYield,minutesUntilNextStage,regrowthCount;};
struct B1 {struct{unsigned mapGroup,mapNum;}location;struct{int x,y;}pos;struct BerryTree berryTrees[128];unsigned bag;}b1,*gSaveBlock1Ptr=&b1;
struct B2{u8 playerTrainerId[4];}b2,*gSaveBlock2Ptr=&b2;
struct{unsigned inBattle,vblankCounter1;void(*callback2)(void);}gMain;
struct{unsigned active;}gPaletteFade;
static int connected=1,script,link,generated,dir=2;static char sent[64];
void CB2_Overworld(void){}
int WorldBridge_ConnectionActive(void){return connected;}int ScriptContext_IsEnabled(void){return script;}int NativeLink_IsActive(void){return link;}int GeneratedMap_IsInside(void){return generated;}unsigned GetPlayerFacingDirection(void){return dir;}
int LinkTransport_BerryCareSend(const char*p){snprintf(sent,sizeof(sent),"%s",p);return 1;}
#include "ACTUAL_SOURCE"
#if EW_SHARED_SOIL_CARE
static void ask(void){gMain.vblankCounter1+=120;WorldBerryCare_Pump();assert(c.pending);}
static void reply(void){char seq[20];snprintf(seq,sizeof(seq),"%u",c.pending);char*t[]={"BC","CARE",seq,"8","1"};WorldBerryCare_Line(5,t);}
int main(void){b1.location.mapNum=19;b1.pos.x=34;b1.pos.y=7;gMain.callback2=CB2_Overworld;gMain.vblankCounter1=120;b1.berryTrees[8]=(struct BerryTree){1,1,0,2,60,0};b1.bag=9;
 WorldBerryCare_Pump();assert(!c.pending);WorldBerryCare_Toggle();ask();reply();assert(b1.berryTrees[8].watered==1&&b1.berryTrees[8].berryYield==2&&b1.bag==9);reply();assert(b1.berryTrees[8].watered==1);
 b1.berryTrees[8].watered=0;ask();b1.berryTrees[8].berry=2;reply();assert(!b1.berryTrees[8].watered);
 ask();b1.pos.x++;reply();assert(!b1.berryTrees[8].watered);b1.pos.x--;
 ask();connected=0;reply();assert(!b1.berryTrees[8].watered);connected=1;
 ask();b2.playerTrainerId[0]++;reply();assert(!b1.berryTrees[8].watered);
 ask();script=1;reply();assert(!b1.berryTrees[8].watered);script=0;
 ask();gMain.vblankCounter1+=181;reply();assert(!b1.berryTrees[8].watered);
 gMain.vblankCounter1=1200;script=1;WorldBerryCare_Watered(8,1);assert(c.queued==8);WorldBerryCare_Pump();assert(c.queued);script=0;gMain.vblankCounter1++;WorldBerryCare_Pump();assert(!c.queued&&strstr(sent,"BC WATER"));
 WorldBerryCare_Watered(8,1);WorldBerryCare_Reset();assert(!c.queued&&!c.pending);assert(b1.bag==9);
 return 0;}
#else
int main(void){WorldBerryCare_Toggle();WorldBerryCare_Watered(8,1);WorldBerryCare_Pump();assert(!sent[0]);return 0;}
#endif
