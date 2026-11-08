"""Party API used by isolated generated-map C harnesses, not a game substitute."""


def write_party_fixture(directory):
    (directory/'pokemon.h').write_text('''#ifndef TEST_POKEMON_H
#define TEST_POKEMON_H
#include "global.h"
#define PARTY_SIZE 6
#define MON_DATA_SPECIES 1
#define MON_DATA_IS_EGG 2
#define MON_DATA_HP 3
struct Pokemon { u16 species, hp; u8 egg; };
extern struct Pokemon gPlayerParty[PARTY_SIZE];
extern u8 gPlayerPartyCount;
u32 GetMonData(const struct Pokemon *, int);
#endif
''')
    source=directory/'party_fixture.c'
    source.write_text('''#include "pokemon.h"
struct Pokemon gPlayerParty[PARTY_SIZE] = {{1, 10, 0}};
u8 gPlayerPartyCount = 1;
u32 GetMonData(const struct Pokemon *mon, int field)
{
    if (field == MON_DATA_SPECIES) return mon->species;
    if (field == MON_DATA_IS_EGG) return mon->egg;
    if (field == MON_DATA_HP) return mon->hp;
    return 0;
}
''')
    return source
