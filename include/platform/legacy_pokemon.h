#ifndef GUARD_LEGACY_POKEMON_H
#define GUARD_LEGACY_POKEMON_H
#include "global.h"
/* Explicit legacy serialized layouts; never reinterpret as donor runtime data. */
struct LegacyPokemonSubstruct0
{
    u16 species;
    u16 heldItem;
    u32 experience;
    u8 ppBonuses;
    u8 friendship;
    u16 filler;
};

struct LegacyPokemonSubstruct1
{
    u16 moves[MAX_MON_MOVES];
    u8 pp[MAX_MON_MOVES];
};

struct LegacyPokemonSubstruct2
{
    u8 hpEV;
    u8 attackEV;
    u8 defenseEV;
    u8 speedEV;
    u8 spAttackEV;
    u8 spDefenseEV;
    u8 cool;
    u8 beauty;
    u8 cute;
    u8 smart;
    u8 tough;
    u8 sheen;
};

struct LegacyPokemonSubstruct3
{
 /* 0x00 */ u8 pokerus;
 /* 0x01 */ metloc_u8_t metLocation;

 /* 0x02 */ u16 metLevel:7;
 /* 0x02 */ u16 metGame:4;
 /* 0x03 */ u16 pokeball:4;
 /* 0x03 */ u16 otGender:1;

 /* 0x04 */ u32 hpIV:5;
 /* 0x04 */ u32 attackIV:5;
 /* 0x05 */ u32 defenseIV:5;
 /* 0x05 */ u32 speedIV:5;
 /* 0x05 */ u32 spAttackIV:5;
 /* 0x06 */ u32 spDefenseIV:5;
 /* 0x07 */ u32 isEgg:1;
 /* 0x07 */ u32 abilityNum:1;

 /* 0x08 */ u32 coolRibbon:3;               // Stores the highest contest rank achieved in the Cool category.
 /* 0x08 */ u32 beautyRibbon:3;             // Stores the highest contest rank achieved in the Beauty category.
 /* 0x08 */ u32 cuteRibbon:3;               // Stores the highest contest rank achieved in the Cute category.
 /* 0x09 */ u32 smartRibbon:3;              // Stores the highest contest rank achieved in the Smart category.
 /* 0x09 */ u32 toughRibbon:3;              // Stores the highest contest rank achieved in the Tough category.
 /* 0x09 */ u32 championRibbon:1;           // Given when defeating the Champion. Because both RSE and FRLG use it, later generations don't specify from which region it comes from.
 /* 0x0A */ u32 winningRibbon:1;            // Given at the Battle Tower's Level 50 challenge by winning a set of seven battles that extends the current streak to 56 or more.
 /* 0x0A */ u32 victoryRibbon:1;            // Given at the Battle Tower's Level 100 challenge by winning a set of seven battles that extends the current streak to 56 or more.
 /* 0x0A */ u32 artistRibbon:1;             // Given at the Contest Hall by winning a Master Rank contest with at least 800 points, and agreeing to have the Pokémon's portrait placed in the museum after being offered.
 /* 0x0A */ u32 effortRibbon:1;             // Given at Slateport's market to Pokémon with maximum EVs.
 /* 0x0A */ u32 marineRibbon:1;             // Never distributed.
 /* 0x0A */ u32 landRibbon:1;               // Never distributed.
 /* 0x0A */ u32 skyRibbon:1;                // Never distributed.
 /* 0x0A */ u32 countryRibbon:1;            // Distributed during Pokémon Festa '04 and '05 to tournament winners.
 /* 0x0B */ u32 nationalRibbon:1;           // Given to purified Shadow Pokémon in Colosseum/XD.
 /* 0x0B */ u32 earthRibbon:1;              // Given to teams that have beaten Mt. Battle's 100-battle challenge in Colosseum/XD.
 /* 0x0B */ u32 worldRibbon:1;              // Distributed during Pokémon Festa '04 and '05 to tournament winners.
 /* 0x0B */ u32 unusedRibbons:4;            // Discarded in Gen 4.

 // The functionality of this bit changed in FRLG:
 // In RS, this bit does nothing, is never set, & is accidentally unset when hatching Eggs.
 // In FRLG & Emerald, this controls Mew & Deoxys obedience and whether they can be traded.
 // If set, a Pokémon is a fateful encounter in FRLG's summary screen if hatched & for all Pokémon in Gen 4+ summary screens.
 // Set for in-game event island legendaries, events distributed after a certain date, & Pokémon from XD: Gale of Darkness.
 // Not to be confused with METLOC_FATEFUL_ENCOUNTER.
 /* 0x0B */ u32 modernFatefulEncounter:1;
};

// Number of bytes in the largest Pokémon substruct.
// They are assumed to be the same size, and will be padded to
// the largest size by the union.
// By default they are all 12 bytes.
#define LegacyNUM_SUBSTRUCT_BYTES (max(sizeof(struct LegacyPokemonSubstruct0),     \
                             max(sizeof(struct LegacyPokemonSubstruct1),     \
                             max(sizeof(struct LegacyPokemonSubstruct2),     \
                                 sizeof(struct LegacyPokemonSubstruct3)))))

enum LegacySubstructType
{
    LegacySUBSTRUCT_TYPE_0,
    LegacySUBSTRUCT_TYPE_1,
    LegacySUBSTRUCT_TYPE_2,
    LegacySUBSTRUCT_TYPE_3,
};

union LegacyPokemonSubstruct
{
    struct LegacyPokemonSubstruct0 type0;
    struct LegacyPokemonSubstruct1 type1;
    struct LegacyPokemonSubstruct2 type2;
    struct LegacyPokemonSubstruct3 type3;
    u16 raw[LegacyNUM_SUBSTRUCT_BYTES / 2]; // /2 because it's u16, not u8
};

struct LegacyBoxPokemon
{
    u32 personality;
    u32 otId;
    u8 nickname[VANILLA_POKEMON_NAME_LENGTH];
    u8 language;
    u8 isBadEgg:1;
    u8 hasSpecies:1;
    u8 isEgg:1;
    u8 blockBoxRS:1; // Unused, but Pokémon Box Ruby & Sapphire will refuse to deposit a Pokémon with this flag set
    u8 unused:4;
    u8 otName[PLAYER_NAME_LENGTH];
    u8 markings;
    u16 checksum;
    u16 unknown;

    union
    {
        u32 raw[(LegacyNUM_SUBSTRUCT_BYTES * 4) / 4]; // *4 because there are 4 substructs, /4 because it's u32, not u8
        union LegacyPokemonSubstruct substructs[4];
    } secure;
};

struct LegacyPokemon
{
    struct LegacyBoxPokemon box;
    u32 status;
    u8 level;
    u8 mail;
    u16 hp;
    u16 maxHP;
    u16 attack;
    u16 defense;
    u16 speed;
    u16 spAttack;
    u16 spDefense;
};

#endif
