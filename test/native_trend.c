#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;typedef unsigned short u16;typedef int bool8;
struct DewfordTrend{unsigned trendiness,maxTrendiness,gainingTrendiness,rand;u16 words[2];};
struct{struct{unsigned mapGroup,mapNum;}location;struct DewfordTrend dewfordTrends[5];}save,*gSaveBlock1Ptr=&save;
struct{u8 playerTrainerId[4];}save2,*gSaveBlock2Ptr=&save2;
struct{unsigned inBattle,vblankCounter1;void(*callback2)(void);}gMain;
struct{unsigned active;}gPaletteFade;
unsigned gSpecialVar_LastTalked=5;static int connected=1,link,script;static char sent[120];static unsigned sends;
int WorldBridge_ConnectionActive(void){return connected;}int NativeLink_IsActive(void){return link;}int ScriptContext_IsEnabled(void){return script;}void CB2_Overworld(void){}
int IsBardWordInvalid(unsigned w){return w>10000;}
void ConvertEasyChatWordsToString(u8*out,const u16*w,unsigned c,unsigned r){(void)w;(void)c;(void)r;out[0]=0xbb;out[1]=0xff;}
int LinkTransport_DewfordTrendsSend(const char*l){strcpy(sent,l);sends++;return connected;}
#include "ACTUAL_SOURCE"
#if EW_SHARED_DEWFORD_TRENDS
static void reply(unsigned seed,unsigned rev){char seq[20],v[20],r[20];snprintf(seq,sizeof(seq),"%u",s.query);snprintf(v,sizeof(v),"%u",seed);snprintf(r,sizeof(r),"%u",rev);char*t[]={"DT","TREND",seq,"512","513",v,r};WorldDewfordTrends_Line(7,t);}
#endif
int main(void){char hint[250];save.location.mapGroup=0;save.location.mapNum=11;gMain.callback2=CB2_Overworld;gMain.vblankCounter1=100;save.dewfordTrends[0].words[0]=512;save.dewfordTrends[0].words[1]=513;save.dewfordTrends[0].rand=42;
 WorldDewfordTrends_Command("/trend share on",hint,sizeof(hint));WorldDewfordTrends_Accepted();
#if EW_SHARED_DEWFORD_TRENDS
 assert(s.pending&&s.share&&!sends);script=1;WorldDewfordTrends_Pump();assert(!sends);script=0;WorldDewfordTrends_Pump();gMain.vblankCounter1+=30;WorldDewfordTrends_Pump();assert(strstr(sent,"DT PUT")&&!s.pending);
 WorldDewfordTrends_Command("/trend follow",hint,sizeof(hint));assert(s.query);reply(777,5);assert(s.follow);assert(WorldDewfordTrends_Seed(42)==42);save.location.mapNum=34;assert(WorldDewfordTrends_Seed(42)==777);
 /* New unsolicited revision cannot silently reroll fishing; immutable adoption. */
 reply(888,6);assert(WorldDewfordTrends_Seed(42)==777);gMain.vblankCounter1+=50000;assert(WorldDewfordTrends_Seed(42)==777);assert(save.dewfordTrends[0].rand==42);
 WorldDewfordTrends_Command("/trend follow",hint,sizeof(hint));script=1;reply(888,6);assert(WorldDewfordTrends_Seed(42)==777);script=0;
 WorldDewfordTrends_Command("/trend follow",hint,sizeof(hint));gMain.vblankCounter1+=180;reply(888,6);assert(WorldDewfordTrends_Seed(42)==777);
 WorldDewfordTrends_Command("/trend follow",hint,sizeof(hint));reply(888,6);assert(WorldDewfordTrends_Seed(42)==888);link=1;assert(WorldDewfordTrends_Seed(42)==42);link=0;
 WorldDewfordTrends_Command("/trend share off",hint,sizeof(hint));assert(!s.share&&s.follow);WorldDewfordTrends_Command("/trend status",hint,sizeof(hint));assert(strstr(hint,"Following A"));
 save2.playerTrainerId[0]++;assert(WorldDewfordTrends_Seed(42)==42);WorldDewfordTrends_Pump();assert(!s.follow);save2.playerTrainerId[0]--;
 WorldDewfordTrends_Command("/trend share on",hint,sizeof(hint));save.location.mapNum=11;gSpecialVar_LastTalked=4;WorldDewfordTrends_Accepted();assert(!s.pending);gSpecialVar_LastTalked=5;WorldDewfordTrends_Accepted();assert(s.pending);connected=0;WorldDewfordTrends_Pump();assert(!s.share&&!s.pending);connected=1;
 WorldDewfordTrends_Command("/trend follow",hint,sizeof(hint));reply(999,7);WorldDewfordTrends_Command("/trend off",hint,sizeof(hint));save.location.mapNum=34;assert(WorldDewfordTrends_Seed(42)==42);
#else
 WorldDewfordTrends_Pump();assert(!sends&&WorldDewfordTrends_Seed(42)==42);
#endif
 return 0;}
