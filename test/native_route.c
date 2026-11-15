#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
#define MAP_ROUTE101 16
#define MAP_ROUTE134 49
#define MAP_GROUP(x) ((x)>>8)
#define MAP_NUM(x) ((x)&255)
#define MAP_TYPE_ROUTE 3
struct B1{struct{unsigned mapGroup,mapNum;}location;}b1,*gSaveBlock1Ptr=&b1;
struct B2{u8 playerTrainerId[4];}b2,*gSaveBlock2Ptr=&b2;
struct{unsigned mapType;}gMapHeader;
struct{unsigned inBattle,vblankCounter1;void(*callback2)(void);}gMain;
struct{unsigned active;}gPaletteFade;
static int connected=1,script,link,generated;
void CB2_Overworld(void){}
int WorldBridge_ConnectionActive(void){return connected;}int ScriptContext_IsEnabled(void){return script;}int NativeLink_IsActive(void){return link;}int GeneratedMap_IsInside(void){return generated;}
int LinkTransport_RouteTrainersSend(const char*p){(void)p;return 1;}
#include "ACTUAL_SOURCE"
#if EW_ROUTE_TRAINERS
static void response(unsigned mode){char seq[20],text[3];snprintf(seq,sizeof(seq),"%u",d.pending);snprintf(text,sizeof(text),"%u",mode);char*t[]={"TD","OFFER",seq,"0","16","1",text,"15","526f757465206368616e6765"};WorldRouteTrainers_Line(9,t);}
int main(void){b1.location.mapNum=16;gMapHeader.mapType=3;gMain.callback2=CB2_Overworld;gMain.vblankCounter1=120;WorldRouteTrainers_Pump();response(1);assert(WorldRouteTrainers_Range(4)==4);WorldRouteTrainers_Toggle();assert(WorldRouteTrainers_Range(4)==4);gMain.vblankCounter1+=120;assert(WorldRouteTrainers_Range(4)==0);assert(WorldRouteTrainers_Range(0)==0);link=1;assert(WorldRouteTrainers_Range(4)==4);link=0;WorldRouteTrainers_Pump();response(2);gMain.vblankCounter1+=120;assert(WorldRouteTrainers_Range(4)==6&&WorldRouteTrainers_Range(7)==8&&WorldRouteTrainers_Range(10)==10);script=1;assert(WorldRouteTrainers_Range(4)==4);script=0;gMain.vblankCounter1+=901;assert(WorldRouteTrainers_Range(4)==4);WorldRouteTrainers_Reset();assert(WorldRouteTrainers_Range(4)==4);return 0;}
#else
int main(void){WorldRouteTrainers_Toggle();assert(WorldRouteTrainers_Range(4)==4);return 0;}
#endif
