#include <assert.h>
#include <string.h>
#include <stdlib.h>
typedef unsigned char u8;typedef short s16;typedef int s32;
#define OBJECT_EVENTS_COUNT 16
#define MAP_ROUTE101 16
#define MAP_ROUTE134 49
#define MAP_GROUP(m) ((m)>>8)
#define MAP_NUM(m) ((m)&255)
#define MAP_TYPE_ROUTE 3
#define PLAYER_AVATAR_FLAG_ON_FOOT 1
#define PLAYER_AVATAR_FLAG_BIKE 6
#define PLAYER_AVATAR_FLAG_SURFING 8
#define PLAYER_AVATAR_FLAG_UNDERWATER 16
#define PLAYER_AVATAR_FLAG_FORCED_MOVE 64
#define PLAYER_AVATAR_FLAG_DASH 128
#define MOVE_SMOKESCREEN 1
#define MOVE_MIST 2
#define MOVE_HAZE 3
#define MOVE_CAMOUFLAGE 4
#define MOVE_DOUBLE_TEAM 5
#define MOVE_MINIMIZE 6
#define PARTY_SIZE 6
#define B_TRAINER_PLAYER 0
#define MON_DATA_SPECIES 0
#define MON_DATA_HP 1
#define MON_DATA_IS_EGG 2
#define MON_DATA_SANITY_IS_BAD_EGG 3
#define MON_DATA_MOVE1 4
#define MON_DATA_PP1 8
#define TRAINER_TYPE_NORMAL 1
#define FLDEFF_QUESTION_MARK_ICON 7
#define FLDEFF_EXCLAMATION_MARK_ICON 8
struct Pokemon {unsigned data[12];}gParties[1][6];
struct ObjectEvent {unsigned trainerType;}gObjectEvents[16];
struct {unsigned inBattle,vblankCounter1;void (*callback2)(void);}gMain;
struct {unsigned active;}gPaletteFade;
struct {unsigned mapType;}gMapHeader;
struct {unsigned flags;}gPlayerAvatar;
struct SB1 {struct {unsigned mapGroup,mapNum;}location;}b1,*gSaveBlock1Ptr=&b1;
struct SB2 {u8 playerTrainerId[4];}b2,*gSaveBlock2Ptr=&b2;
s32 gFieldEffectArguments[8];
static int script,link,generated,icons,cries;static s16 x,y;
void CB2_Overworld(void){}
int ScriptContext_IsEnabled(void){return script;}int NativeLink_IsActive(void){return link;}int GeneratedMap_IsInside(void){return generated;}
unsigned GetMonData(struct Pokemon *p,unsigned k){return p->data[k];}
void SetMonData(struct Pokemon *p,unsigned k,const void *v){p->data[k]=*(const u8*)v;}
void PlayCry_Normal(unsigned a,unsigned b){(void)a;(void)b;cries++;}
void PlayerGetDestCoords(s16 *a,s16 *b){*a=x;*b=y;}
int FieldEffectActiveListContains(unsigned i){(void)i;return 0;}
void FieldEffectStart(unsigned i){assert(i==7&&gFieldEffectArguments[7]==-1);icons++;}
void ObjectEventGetLocalIdAndMap(struct ObjectEvent *o,s32 *a,s32 *b,s32 *c){*a=o-gObjectEvents;*b=0;*c=17;}
#include "ACTUAL_SOURCE"
static void baseline(void){WorldConceal_Reset();memset(gParties,0,sizeof(gParties));gMain.inBattle=0;gMain.callback2=CB2_Overworld;gMain.vblankCounter1=100;gPaletteFade.active=script=link=generated=0;gMapHeader.mapType=3;b1.location.mapGroup=0;b1.location.mapNum=17;b2.playerTrainerId[0]=42;gPlayerAvatar.flags=1;x=y=10;gParties[0][0].data[0]=25;gParties[0][0].data[1]=20;gParties[0][0].data[4]=MOVE_DOUBLE_TEAM;gParties[0][0].data[8]=3;gObjectEvents[0].trainerType=1;}
int main(void){unsigned i;baseline();
#if EW_FIELD_CONCEALMENT
 assert(WorldConceal_Start(0,0,MOVE_DOUBLE_TEAM));assert(gParties[0][0].data[8]==2&&cries==1);assert(!WorldConceal_Start(0,0,MOVE_DOUBLE_TEAM));
 for(i=0;i<8;i++)gFieldEffectArguments[i]=i+10;
 assert(WorldConceal_Filter(&gObjectEvents[0],4)==0&&icons==1);assert(WorldConceal_Filter(&gObjectEvents[0],4)==0&&icons==1);for(i=0;i<8;i++)assert(gFieldEffectArguments[i]==(s32)i+10);
 assert(WorldConceal_Filter(&gObjectEvents[0],1)==1);gObjectEvents[1].trainerType=2;assert(WorldConceal_Filter(&gObjectEvents[1],4)==4);
 for(i=0;i<24;i++){x++;assert(WorldConceal_Filter(&gObjectEvents[0],4)==0);}x++;assert(WorldConceal_Filter(&gObjectEvents[0],4)==4);
 baseline();assert(WorldConceal_Start(0,0,5));gPlayerAvatar.flags|=128;assert(WorldConceal_Filter(&gObjectEvents[0],3)==3);
 baseline();assert(WorldConceal_Start(0,0,5));gMain.vblankCounter1+=1800;assert(WorldConceal_Filter(&gObjectEvents[0],3)==3);
 baseline();assert(WorldConceal_Start(0,0,5));b1.location.mapNum++;assert(WorldConceal_Filter(&gObjectEvents[0],3)==3);
 baseline();assert(WorldConceal_Start(0,0,5));b2.playerTrainerId[0]++;assert(WorldConceal_Filter(&gObjectEvents[0],3)==3);
 baseline();assert(WorldConceal_Start(0,0,5));gMain.inBattle=1;assert(WorldConceal_Filter(&gObjectEvents[0],3)==3);
 baseline();assert(WorldConceal_Start(0,0,5));x+=2;assert(WorldConceal_Filter(&gObjectEvents[0],3)==3);
 for(i=0;i<6;i++){baseline();if(i==0)gParties[0][0].data[8]=0;if(i==1)gParties[0][0].data[1]=0;if(i==2)gParties[0][0].data[2]=1;if(i==3)b1.location.mapGroup=1;if(i==4)script=1;if(i==5)link=1;assert(!WorldConceal_Start(0,0,5));}
 baseline();assert(!WorldConceal_Start(0,0,2));assert(gParties[0][0].data[8]==3);
#else
 assert(!WorldConceal_Start(0,0,5));assert(!WorldConceal_Eligible(5));assert(WorldConceal_Filter(&gObjectEvents[0],4)==4);assert(gParties[0][0].data[8]==3);
#endif
 return 0;}
