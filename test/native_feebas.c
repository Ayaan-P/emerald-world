#include <assert.h>
#include <stdint.h>
typedef unsigned char u8;typedef unsigned short u16;typedef short s16;typedef int bool8;
#define TRUE 1
#define FALSE 0
#define MAP_OFFSET 7
#define MAP_ROUTE119 34
#define MAP_GROUP(x) 0
#define MAP_NUM(x) x
#define NUM_FEEBAS_SPOTS 6
#define NUM_FISHING_SPOTS 447
static const u16 sRoute119WaterTileData[]={0,45,0,46,91,131,92,139,298};
struct{struct{int mapGroup,mapNum;}location;struct{unsigned rand;}dewfordTrends[5];}save,*gSaveBlock1Ptr=&save;
static unsigned randomValue,shared,enabled;static uint32_t rng;
unsigned Random(void){return randomValue;}
unsigned WorldDewfordTrends_Seed(unsigned original){return enabled?shared:original;}
void FeebasSeedRng(u16 seed){rng=seed;}
u16 FeebasRandom(void){rng=rng*1103515245U+12345U;return rng>>16;}
u16 GetFeebasFishingSpotId(s16 x,s16 y,u8 section){(void)y;(void)section;return x;}
ACTUAL_FUNCTION
int main(void){int i,privateCount=0,publicCount=0,different=0;save.location.mapNum=34;save.dewfordTrends[0].rand=42;shared=777;
 for(i=1;i<=447;i++){int a,b;enabled=0;a=CheckFeebasAtCoords(i+7,30);enabled=1;b=CheckFeebasAtCoords(i+7,30);privateCount+=a;publicCount+=b;different+=(a!=b);}
 assert(privateCount>0&&privateCount<=6&&publicCount>0&&publicCount<=6&&different>0);assert(save.dewfordTrends[0].rand==42);
 randomValue=50;for(i=1;i<=447;i++)assert(!CheckFeebasAtCoords(i+7,30));randomValue=0;save.location.mapNum=11;for(i=1;i<=447;i++)assert(!CheckFeebasAtCoords(i+7,30));return 0;}
