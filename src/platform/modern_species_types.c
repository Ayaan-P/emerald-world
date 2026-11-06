#ifdef PORTABLE
#include "global.h"
#include "pokemon.h"
#include "constants/species.h"
#include "constants/pokemon.h"
#include "platform/modern_species_types.h"
#include "platform/expanded_moves.h"

/* Legacy species retyped by Expansion bb3fd057061cdd7e6a9e79b76abb41924ee44ecc
 * src/data/pokemon/species_info/gen_{1,2,3}_families.h, P_UPDATED_TYPES >= GEN_6.
 * Family macros are expanded here. A monotype occupies both slots, just as
 * in the legacy table. Unlisted species keep their original table types. */
static const struct
{
    u16 species;
    u8 types[2];
} sModernTypes[] =
{
    {SPECIES_CLEFFA,     {TYPE_FAIRY, TYPE_FAIRY}},
    {SPECIES_CLEFAIRY,   {TYPE_FAIRY, TYPE_FAIRY}},
    {SPECIES_CLEFABLE,   {TYPE_FAIRY, TYPE_FAIRY}},
    {SPECIES_IGGLYBUFF,  {TYPE_NORMAL, TYPE_FAIRY}},
    {SPECIES_JIGGLYPUFF, {TYPE_NORMAL, TYPE_FAIRY}},
    {SPECIES_WIGGLYTUFF, {TYPE_NORMAL, TYPE_FAIRY}},
    {SPECIES_MR_MIME,    {TYPE_PSYCHIC, TYPE_FAIRY}},
    {SPECIES_TOGEPI,     {TYPE_FAIRY, TYPE_FAIRY}},
    {SPECIES_TOGETIC,    {TYPE_FAIRY, TYPE_FLYING}},
    {SPECIES_AZURILL,    {TYPE_NORMAL, TYPE_FAIRY}},
    {SPECIES_MARILL,     {TYPE_WATER, TYPE_FAIRY}},
    {SPECIES_AZUMARILL,  {TYPE_WATER, TYPE_FAIRY}},
    {SPECIES_SNUBBULL,   {TYPE_FAIRY, TYPE_FAIRY}},
    {SPECIES_GRANBULL,   {TYPE_FAIRY, TYPE_FAIRY}},
    {SPECIES_RALTS,      {TYPE_PSYCHIC, TYPE_FAIRY}},
    {SPECIES_KIRLIA,     {TYPE_PSYCHIC, TYPE_FAIRY}},
    {SPECIES_GARDEVOIR,  {TYPE_PSYCHIC, TYPE_FAIRY}},
    {SPECIES_MAWILE,     {TYPE_STEEL, TYPE_FAIRY}},
};

u8 ModernSpeciesTypes_GetType(u16 species, u8 typeIndex)
{
    u32 i;

    if (ExpandedMoves_UseModernTypes())
    {
        for (i = 0; i < ARRAY_COUNT(sModernTypes); i++)
        {
            if (sModernTypes[i].species == species)
                return sModernTypes[i].types[typeIndex];
        }
    }
    return gSpeciesInfo[species].types[typeIndex];
}
#endif
