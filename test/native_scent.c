#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
#define ARRAY_COUNT(x) (sizeof(x)/sizeof((x)[0]))
#define MAP_OFFSET 7
#define POKEBLOCKS_COUNT 40
struct Pokeblock{u8 color,spicy,dry,sweet,bitter,sour,feel;};
struct{struct{unsigned mapGroup,mapNum;}location;struct{int x,y;}pos;}save,*gSaveBlock1Ptr=&save;
struct{u8 playerTrainerId[4];}save2,*gSaveBlock2Ptr=&save2;
struct{unsigned inBattle,vblankCounter1;void(*callback2)(void);}gMain;
struct{unsigned active;}gPaletteFade;
static int safari=1,kanto,connected=1,link,script,tile=1;static char sent[120];static unsigned sends;
int GetSafariZoneFlag(void){return safari;}int SafariZoneUsesFrlgRules(void){return kanto;}int WorldBridge_ConnectionActive(void){return connected;}int NativeLink_IsActive(void){return link;}int ScriptContext_IsEnabled(void){return script;}void CB2_Overworld(void){}
unsigned MapGridGetMetatileBehaviorAt(int x,int y){return tile&&x==31&&y==37?135:0;}int MetatileBehavior_IsPokeblockFeeder(unsigned b){return b==135;}
int LinkTransport_SafariFeedersSend(const char*line){strcpy(sent,line);sends++;return connected;}
#include "ACTUAL_SOURCE"
#if EW_SHARED_SAFARI_FEEDERS
static void ask(void){gMain.vblankCounter1=(gMain.vblankCounter1/60+1)*60;WorldSafariFeeders_Pump();assert(s.query);}
static void reply(unsigned ttl){char seq[20],life[20];snprintf(seq,sizeof(seq),"%u",s.query);snprintf(life,sizeof(life),"%u",ttl);char*t[]={"SF","SCENT",seq,"7","0114000000000a",life};WorldSafariFeeders_Line(6,t);}
#endif
int main(void){char hint[250];struct Pokeblock b={1,20,0,0,0,0,10};save.location.mapGroup=26;save.location.mapNum=3;save.pos.x=24;save.pos.y=31;gMain.callback2=CB2_Overworld;gMain.vblankCounter1=120;
 WorldSafariFeeders_Command("/safari-scents on",hint,sizeof(hint));
#if EW_SHARED_SAFARI_FEEDERS
 assert(s.on);WorldSafariFeeders_Prepared(2,3,31,37,&b);assert(s.prepared==7&&!s.queued);WorldSafariFeeders_Committed(3);assert(!s.queued);
 WorldSafariFeeders_Prepared(2,3,31,37,&b);WorldSafariFeeders_Committed(2);assert(s.queued==7);script=1;WorldSafariFeeders_Pump();assert(!sends);script=0;gMain.vblankCounter1++;WorldSafariFeeders_Pump();assert(!sends);gMain.vblankCounter1+=30;WorldSafariFeeders_Pump();assert(strstr(sent,"SF PUT")&&!s.queued);
 ask();reply(1);assert(WorldSafariFeeders_Active()->spicy==20);gMain.vblankCounter1+=60;assert(!WorldSafariFeeders_Active());
 ask();reply(600);save2.playerTrainerId[0]++;assert(!WorldSafariFeeders_Active());ask();assert(!WorldSafariFeeders_Active());reply(600);assert(WorldSafariFeeders_Active());
 tile=0;assert(!WorldSafariFeeders_Active());tile=1;connected=0;assert(!WorldSafariFeeders_Active());connected=1;save.pos.x=1;assert(!WorldSafariFeeders_Active());save.pos.x=24;
 ask();kanto=1;reply(600);assert(!WorldSafariFeeders_Active());kanto=0;ask();script=1;reply(600);assert(!WorldSafariFeeders_Active());script=0;
 ask();WorldSafariFeeders_VisitEnd();reply(600);assert(!WorldSafariFeeders_Active()&&s.on);WorldSafariFeeders_Reset();assert(!s.on);
#else
 WorldSafariFeeders_Prepared(2,3,31,37,&b);WorldSafariFeeders_Committed(2);WorldSafariFeeders_Pump();assert(!sends&&!WorldSafariFeeders_Active());
#endif
 return 0;}
