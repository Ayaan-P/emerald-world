/* Validate a received pair before Expansion trade UI or saves inspect it.
 * This is only one part of the trade port; trade remains disabled until the
 * selection/confirmation protocol and auxiliary blocks are validated too. */
#include <stddef.h>
#include <string.h>
#include "global.h"
#include "pokemon.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/pokeball.h"
#include "constants/characters.h"

_Static_assert(sizeof(struct Pokemon) == 100, "Expansion trade block ABI changed");

static int mon_valid(struct Pokemon *mon)
{
    u16 checksum = 0;
    u32 key = mon->box.personality ^ mon->box.otId;
    u32 species, i;
    for (i = 0; i < ARRAY_COUNT(mon->box.secure.raw); i++) {
        u32 word = mon->box.secure.raw[i] ^ key;
        checksum += (u16)word;
        checksum += (u16)(word >> 16);
    }
    if (checksum != mon->box.checksum) return 0;
    species = GetMonData(mon, MON_DATA_SPECIES);
    if (species >= NUM_SPECIES) return 0;
    if (species == SPECIES_NONE) return !mon->box.hasSpecies;
    if (!IsSpeciesEnabled(species) || !mon->box.hasSpecies || mon->box.isBadEgg
        || mon->box.language < LANGUAGE_JAPANESE || mon->box.language > LANGUAGE_SPANISH
        || mon->box.language == 6 || mon->level == 0 || mon->level > MAX_LEVEL
        || mon->hp > mon->maxHP || (mon->status & ~0xFFFu)
        || (mon->mail != MAIL_NONE && mon->mail >= PARTY_SIZE)
        || GetMonData(mon, MON_DATA_HELD_ITEM) >= ITEMS_COUNT
        || GetMonData(mon, MON_DATA_POKEBALL) >= POKEBALL_COUNT
        || GetMonData(mon, MON_DATA_TERA_TYPE) >= NUMBER_OF_MON_TYPES
        || GetMonData(mon, MON_DATA_DYNAMAX_LEVEL) > MAX_DYNAMAX_LEVEL
        || GetMonData(mon, MON_DATA_EXP) > 1640000) return 0;
    for (i = 0; i < MAX_MON_MOVES; i++)
        if (GetMonData(mon, MON_DATA_MOVE1 + i) >= MOVES_COUNT) return 0;
    for (i = MON_DATA_COOL_RIBBON; i <= MON_DATA_TOUGH_RIBBON; i++)
        if (GetMonData(mon, i) > 4) return 0;
    for (i = 0; i < sizeof(mon->box.nickname); i++)
        if (mon->box.nickname[i] >= 0xFA && mon->box.nickname[i] != EOS) return 0;
    for (i = 0; i < sizeof(mon->box.otName); i++)
        if (mon->box.otName[i] >= 0xFA && mon->box.otName[i] != EOS) return 0;
    return 1;
}

int ExpansionTrade_PairValid(const void *data, size_t size)
{
    struct Pokemon pair[2];
    if (!data || size != sizeof pair) return 0;
    memcpy(pair, data, sizeof pair);
    return mon_valid(&pair[0]) && mon_valid(&pair[1]);
}
