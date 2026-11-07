#ifdef PORTABLE
#include "global.h"
#include "pokemon.h"
#include "platform/wild_shuffle.h"

/* Canonical National Dex 1..386 is shared by the current game and Expansion.
 * Keep the permutation algorithm version stable: a seed names the same map. */
#define SHUFFLE_DEX 386
#define SHUFFLE_SEEDS 20
static bool8 sEnabled;
static unsigned sSeed=1, sBuiltSeed;
static u16 sMapping[SHUFFLE_DEX+1];

static u32 Next(u32 *state)
{
    u32 x=*state;
    x^=x<<13;x^=x>>17;x^=x<<5;
    *state=x;
    return x;
}
static void Build(void)
{
    unsigned i;u32 rng=(u32)sSeed;
    for (i=1;i<=SHUFFLE_DEX;i++) sMapping[i]=(u16)i;
    for (i=SHUFFLE_DEX;i>1;i--) {
        unsigned j=1+Next(&rng)%i;
        u16 temporary=sMapping[i];sMapping[i]=sMapping[j];sMapping[j]=temporary;
    }
    sBuiltSeed=sSeed;
}
int WildShuffle_Enabled(void){return sEnabled;}
unsigned WildShuffle_Seed(void){return sSeed;}
void WildShuffle_Toggle(void){sEnabled=!sEnabled;}
void WildShuffle_NextSeed(void){sSeed=sSeed%SHUFFLE_SEEDS+1;}
u16 WildShuffle_MapNational(u16 national)
{
    if (!sEnabled || !national || national>SHUFFLE_DEX) return national;
    if (sBuiltSeed!=sSeed) Build();
    return sMapping[national];
}
u16 WildShuffle_MapSpecies(u16 species)
{
    u16 national,mapped;
    if (!sEnabled) return species;
    national=SpeciesToNationalPokedexNum(species);
    if (!national || national>SHUFFLE_DEX) return species;
    mapped=NationalPokedexNumToSpecies(WildShuffle_MapNational(national));
    return mapped ? mapped : species;
}
#endif
