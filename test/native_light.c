#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
#define MAP_GRANITE_CAVE_B1F 0x1802
#define MAP_GRANITE_CAVE_B2F 0x1803
#define MAP_GROUP(m) ((m)>>8)
#define MAP_NUM(m) ((m)&255)
#define FLAG_SYS_USE_FLASH 7
struct SB1{struct{unsigned mapGroup,mapNum;}location;}b1,*gSaveBlock1Ptr=&b1;
struct SB2{u8 playerTrainerId[4];}b2,*gSaveBlock2Ptr=&b2;
struct{unsigned cave;}gMapHeader;
struct{unsigned inBattle,vblankCounter1;void(*callback2)(void);}gMain;
struct{unsigned active;}gPaletteFade;
static int script,link,generated,connected=1,flash=1,flag,bright,calls;static char sent[90];
void CB2_Overworld(void){}
int ScriptContext_IsEnabled(void){return script;}int NativeLink_IsActive(void){return link;}int GeneratedMap_IsInside(void){return generated;}int WorldBridge_ConnectionActive(void){return connected;}unsigned GetFlashLevel(void){return flash;}int FlagGet(int f){(void)f;return flag;}
int WorldLight_Render(int b){bright=b;calls++;return 1;}
int LinkTransport_CaveLightSend(const char*p){strcpy(sent,p);return 1;}
#include "ACTUAL_SOURCE"
#if EW_SHARED_CAVE_LIGHT
static void base(void){memset(&light,0,sizeof(light));b1.location.mapGroup=24;b1.location.mapNum=2;gMapHeader.cave=1;gMain.callback2=CB2_Overworld;gMain.vblankCounter1=30;script=flag=bright=0;flash=connected=1;WorldLight_Pump();}
static void receive(const char*value){char epoch[20];snprintf(epoch,sizeof(epoch),"%u",light.epoch);char*t[]={"FL","LIGHT",epoch,(char*)value};WorldLight_Line(4,t);}
int main(void){base();WorldLight_Toggle();receive("1");WorldLight_Pump();assert(bright&&WorldLight_Shining()&&flash==1&&!flag);gMain.vblankCounter1+=91;WorldLight_Pump();assert(!bright&&flash==1);receive("1");WorldLight_Pump();assert(bright);WorldLight_Toggle();WorldLight_Pump();assert(!bright&&!flag);
base();WorldLight_Toggle();WorldLight_FlashStarted();flag=1;script=1;flash=0;WorldLight_Pump();assert(!light.lit);script=0;WorldLight_Pump();assert(light.lit&&strstr(sent," 1 1"));b1.location.mapNum=3;WorldLight_Pump();assert(!light.lit&&!light.pending);
base();WorldLight_Toggle();receive("1");WorldLight_Pump();connected=0;WorldLight_Pump();assert(!bright&&flash==1&&!flag);
base();WorldLight_Toggle();receive("1");WorldLight_Pump();script=1;WorldLight_Pump();assert(!bright);script=0;WorldLight_Pump();assert(!bright);return 0;}
#else
int main(void){WorldLight_Toggle();WorldLight_FlashStarted();WorldLight_Pump();assert(!WorldLight_Enabled()&&!calls);return 0;}
#endif
