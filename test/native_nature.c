#include <assert.h>
#include <stddef.h>
typedef unsigned char u8;typedef signed char s8;typedef short s16;
#define TRUE 1
#define NUM_NATURES 25
#define FLAVOR_COUNT 5
#define WILDMON_ORIGIN 0
#define PBLOCK_COLOR 0
#define PBLOCK_SPICY 1
#define PBLOCK_DRY 2
#define PBLOCK_SWEET 3
#define PBLOCK_BITTER 4
#define PBLOCK_SOUR 5
#define PBLOCK_FEEL 6
enum Flavor{FLAVOR_ZERO};enum Species{TEST_SPECIES};
struct Pokeblock{u8 color,spicy,dry,sweet,bitter,sour,feel;};
static struct{struct Pokeblock pokeblock;}sPokeblockFeeders[10];static unsigned gSpecialVar_Result,local=65535,random_,shared=1;
static struct Pokeblock publicBlock={1,20,0,0,0,0,10};
static void GetPokeblockFeederWithinRange(void){gSpecialVar_Result=local;}
static struct Pokeblock*WorldSafariFeeders_Active(void){return shared?&publicBlock:NULL;}
static unsigned GetSafariZoneFlag(void){return 1;}static unsigned Random(void){return random_;}
static void Shuffle(void*p,unsigned n,unsigned size){(void)p;(void)n;(void)size;}static u8 GetSynchronizedNature(unsigned origin,enum Species species){(void)origin;(void)species;return 7;}
ACTUAL_FUNCTIONS
int main(void){unsigned i,positive=0;assert(SafariZoneGetActivePokeblock()==&publicBlock);for(i=0;i<100;i++){u8 nature;random_=i;nature=PickWildMonNature(TEST_SPECIES);if(PokeblockGetGain(nature,&publicBlock)>0)positive++;else assert(nature==7);}assert(positive==80);
 local=0;sPokeblockFeeders[0].pokeblock=(struct Pokeblock){2,0,20,0,0,0,10};assert(SafariZoneGetActivePokeblock()==&sPokeblockFeeders[0].pokeblock);random_=0;assert(PokeblockGetGain(PickWildMonNature(TEST_SPECIES),&sPokeblockFeeders[0].pokeblock)>0);
 local=65535;shared=0;assert(PickWildMonNature(TEST_SPECIES)==7);return 0;}
