#ifdef PORTABLE
#include "global.h"
#include "platform/expanded_species.h"
#include "platform/world_rules.h"
#include "constants/maps.h"
#include "constants/pokedex.h"
#include "constants/species.h"
#include "constants/expanded_species.h"

static const struct
{
    u16 species;
    u16 dexNumber;
} sExpandedDexMap[] =
{
#include "../data/pokemon/expanded/dex_map.inc"
};

bool8 ExpandedSpecies_IsPlayable(u16 species)
{
    switch (species)
    {
#include "../data/pokemon/expanded/playable_cases.inc"
        return TRUE;
    default:
        return FALSE;
    }
}

u16 ExpandedSpecies_Clamp(u16 species)
{
    return species <= SPECIES_EGG || ExpandedSpecies_IsPlayable(species) ? species : SPECIES_NONE;
}

u16 ExpandedSpecies_ClampIcon(u16 species)
{
    return species <= SPECIES_UNOWN_QMARK || ExpandedSpecies_IsPlayable(species) ? species : SPECIES_OLD_UNOWN_J;
}

u16 ExpandedSpecies_LegacyAnimSpecies(u16 species)
{
    /* Animation command IDs and delays still use the legacy species-minus-one ABI. */
    return species > SPECIES_NONE && species < NUM_SPECIES ? species : SPECIES_BULBASAUR;
}

u16 ExpandedSpecies_NationalDexNumber(u16 species)
{
    u32 i;
    for (i = 0; i < ARRAY_COUNT(sExpandedDexMap); i++)
        if (sExpandedDexMap[i].species == species)
            return sExpandedDexMap[i].dexNumber;
    return 0;
}

u16 ExpandedSpecies_FromNationalDexNumber(u16 dexNumber)
{
    u32 i;
    for (i = 0; i < ARRAY_COUNT(sExpandedDexMap); i++)
        if (sExpandedDexMap[i].dexNumber == dexNumber)
            return sExpandedDexMap[i].species;
    return SPECIES_NONE;
}

u16 ExpandedSpecies_ResolveEncounter(u16 species, u8 mapGroup, u8 mapNum)
{
    /* Pure extra-variant lookup shared by ordinary encounters and DexNav.
     * This function consumes no RNG. The ordinary wrapper chooses original or
     * extra, while an intentional DexNav target is never remapped. */
    if (WorldRules_Enabled(WORLD_RULE_EXPANDED_ROSTER)
        && mapGroup == MAP_GROUP(MAP_ROUTE101) && mapNum == MAP_NUM(MAP_ROUTE101))
    {
        switch (species)
        {
        case SPECIES_ZIGZAGOON:
            return SPECIES_GIMMIGHOUL_ROAMING;
        case SPECIES_WURMPLE:
            return SPECIES_MELTAN;
        case SPECIES_POOCHYENA:
            return SPECIES_COSMOEM;
        }
    }
#ifdef SPECIES_TYPE_NULL
    /* Route 102's existing rare Ralts land slot. No extra random draw, and
     * no effect until matching generated headers AND playable data promote. */
    if (WorldRules_Enabled(WORLD_RULE_EXPANDED_ROSTER)
        && mapGroup == MAP_GROUP(MAP_ROUTE102) && mapNum == MAP_NUM(MAP_ROUTE102)
        && species == SPECIES_RALTS && ExpandedSpecies_IsPlayable(SPECIES_TYPE_NULL))
        return SPECIES_TYPE_NULL;
#endif
    if (WorldRules_Enabled(WORLD_RULE_EXPANDED_ROSTER)
        && mapGroup == MAP_GROUP(MAP_ROUTE103) && mapNum == MAP_NUM(MAP_ROUTE103))
    {
#ifdef SPECIES_TURTWIG
        if (species == SPECIES_ZIGZAGOON && ExpandedSpecies_IsPlayable(SPECIES_TURTWIG))
            return SPECIES_TURTWIG;
#endif
#ifdef SPECIES_CHESPIN
        if (species == SPECIES_POOCHYENA && ExpandedSpecies_IsPlayable(SPECIES_CHESPIN))
            return SPECIES_CHESPIN;
#endif
#ifdef SPECIES_ARROKUDA
        /* Existing fishing Magikarp slot; ordinary wrapper retains the source. */
        if (species == SPECIES_MAGIKARP && ExpandedSpecies_IsPlayable(SPECIES_ARROKUDA))
            return SPECIES_ARROKUDA;
#endif
    }
    return species;
}
#endif
