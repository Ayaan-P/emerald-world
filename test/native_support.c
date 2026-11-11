#include <assert.h>
#include <string.h>
typedef unsigned char u8;typedef unsigned short u16;typedef short s16;
#define PARTY_SIZE 6
#define B_TRAINER_PLAYER 0
#define MON_DATA_SPECIES 0
#define MON_DATA_HP 1
#define MON_DATA_IS_EGG 2
#define MON_DATA_SANITY_IS_BAD_EGG 3
#define MON_DATA_MOVE1 4
#define MON_DATA_PP1 8
#define MON_DATA_MAX_HP 12
#define MOVE_HEAL_PULSE 99
#define MAP_ROUTE101 16
#define MAP_ROUTE134 49
#define MAP_GROUP(x) ((x)>>8)
#define MAP_NUM(x) ((x)&255)
#define MAP_TYPE_ROUTE 3
struct Pokemon{unsigned data[13];}gParties[1][6];
struct {unsigned inBattle,vblankCounter1;void(*callback2)(void);}gMain;
struct {unsigned active;}gPaletteFade;
struct {unsigned mapType;}gMapHeader;
struct SB1{struct{unsigned mapGroup,mapNum;}location;}b1,*gSaveBlock1Ptr=&b1;
struct SB2{u8 playerTrainerId[4];}b2,*gSaveBlock2Ptr=&b2;
static int connected=1,script,link,generated,ui,queue=1;static s16 x,y;static char sent[120];
void CB2_Overworld(void){}
int WorldBridge_ConnectionActive(void){return connected;}
const char*LinkTransport_TagPeer(void){return "partner";}
int ScriptContext_IsEnabled(void){return script;}int NativeLink_IsActive(void){return link;}int GeneratedMap_IsInside(void){return generated;}int WorldFieldUI_Active(void){return ui;}
void PlayerGetDestCoords(s16*a,s16*b){*a=x;*b=y;}
unsigned GetMonData(struct Pokemon*p,unsigned k){return p->data[k];}
void SetMonData(struct Pokemon*p,unsigned k,const void*v){p->data[k]=k==MON_DATA_HP?*(const u16*)v:*(const u8*)v;}
void PlayCry_Normal(unsigned a,unsigned b){(void)a;(void)b;}
int LinkTransport_FieldSupportSend(const char*p){strcpy(sent,p);return queue;}
#include "ACTUAL_SOURCE"
#if EW_FIELD_SUPPORT
static void base(void){memset(&care,0,sizeof(care));memset(gParties,0,sizeof(gParties));connected=queue=1;script=link=generated=ui=0;x=y=0;gMain.callback2=CB2_Overworld;gMain.inBattle=0;gMain.vblankCounter1=0;b1.location.mapNum=16;gMapHeader.mapType=3;gParties[0][0].data[0]=1;gParties[0][0].data[1]=10;gParties[0][0].data[12]=100;gParties[0][0].data[4]=99;gParties[0][0].data[8]=3;sent[0]=0;}
static void line(const char*p){char b[120],*t[8];unsigned n=0;strcpy(b,p);char*c=strtok(b," ");while(c&&n<8){t[n++]=c;c=strtok(0," ");}WorldSupport_Line(n,t);}
static void offer(void){base();line("FS OFFER 0123456789abcdef partner");assert(WorldSupport_Pending());assert(!WorldSupport_Active());assert(WorldSupport_Open());WorldSupport_Key(1);WorldSupport_Key(2);assert(care.state==TARGET_WAIT);}
int main(void){char ready[100];base();assert(WorldSupport_Begin(0,0,99));WorldSupport_Key(2);assert(!care.state);assert(gParties[0][0].data[8]==3);
assert(WorldSupport_Begin(0,0,99));WorldSupport_Key(-1);WorldSupport_Key(2);assert(care.state==SOURCE_WAIT);snprintf(ready,sizeof(ready),"FS PENDING %u 0123456789abcdef",care.seq);line(ready);snprintf(ready,sizeof(ready),"FS READY %u 0123456789abcdef",care.seq);line(ready);line(ready);assert(gParties[0][0].data[8]==2&&care.state==PAID);connected=0;WorldSupport_Pump();assert(care.notice==2);
offer();line("FS APPLY 0123456789abcdef");assert(gParties[0][0].data[1]==60&&care.notice==3);line("FS APPLY 0123456789abcdef");assert(gParties[0][0].data[1]==60);WorldSupport_Reset();assert(care.notice==3);
offer();gParties[0][0].data[1]=9;line("FS APPLY 0123456789abcdef");assert(gParties[0][0].data[1]==9&&care.notice==0);assert(strstr(sent,"ACK 0123456789abcdef 0"));
offer();x=1;line("FS APPLY 0123456789abcdef");assert(gParties[0][0].data[1]==10);
base();line("FS OFFER 0123456789abcdef partner");x=1;WorldSupport_Pump();assert(!WorldSupport_Active()&&!WorldSupport_Pending());
base();b1.location.mapNum=0;assert(!WorldSupport_Begin(0,0,99));base();gParties[0][0].data[8]=0;assert(!WorldSupport_Begin(0,0,99));return 0;}
#else
int main(void){assert(!WorldSupport_Available(0)&&!WorldSupport_Begin(0,0,99)&&!WorldSupport_Active());return 0;}
#endif
