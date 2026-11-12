#include <assert.h>
#include <string.h>
typedef unsigned short u16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define SAVED_TRENDS_COUNT 5
#define FLAG_SYS_CHANGED_DEWFORD_TREND 0
#define FLAG_SYS_MIX_RECORD 1
#define SORT_MODE_NORMAL 0
struct DewfordTrend{unsigned rand,gainingTrendiness;u16 words[2];};
struct{struct DewfordTrend dewfordTrends[5];}save,*gSaveBlock1Ptr=&save;
static int flags[2],duplicate,chosen,comparisons,reports,tv;static u16 observed[3];
int FlagGet(int i){return flags[i];}void FlagSet(int i){flags[i]=1;}
int IsPhraseInSavedTrends(u16*p){(void)p;return duplicate;}
void SeedTrendRng(struct DewfordTrend*t){t->rand=99;}
int CompareTrends(struct DewfordTrend*a,struct DewfordTrend*b,int m){(void)a;(void)b;(void)m;return comparisons++==chosen;}
void TryPutTrendWatcherOnAir(u16*p){(void)p;tv++;}
void WorldDewfordTrends_Accepted(void){reports++;observed[0]=save.dewfordTrends[0].words[0];observed[1]=save.dewfordTrends[0].words[1];observed[2]=save.dewfordTrends[0].rand;}
ACTUAL_FUNCTION
int main(void){u16 words[]={512,513};save.dewfordTrends[0].rand=42;
 assert(TrySetTrendyPhrase(words));assert(reports==1&&observed[0]==512&&observed[2]==42); /* first submission does NOT reseed */
 chosen=0;comparisons=0;assert(TrySetTrendyPhrase(words));assert(reports==2&&observed[2]==99);
 chosen=2;comparisons=0;assert(!TrySetTrendyPhrase(words));assert(reports==2);
 chosen=99;comparisons=0;assert(!TrySetTrendyPhrase(words));assert(reports==2&&tv==1);
 duplicate=1;assert(!TrySetTrendyPhrase(words));assert(reports==2);
 return 0;}
