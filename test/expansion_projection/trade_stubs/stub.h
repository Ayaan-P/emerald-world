#ifndef TRADE_STUB_H
#define TRADE_STUB_H
#include <stdint.h>
typedef uint16_t u16; typedef uint32_t u32; typedef uint8_t u8;
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define NUM_SPECIES 100
#define SPECIES_NONE 0
#define LANGUAGE_JAPANESE 1
#define LANGUAGE_SPANISH 7
#define MAX_LEVEL 100
#define MAX_DYNAMAX_LEVEL 10
#define MAIL_NONE 255
#define PARTY_SIZE 6
#define ITEMS_COUNT 100
#define POKEBALL_COUNT 28
#define NUMBER_OF_MON_TYPES 21
#define NUM_ABILITY_SLOTS 3
#define MON_DATA_ABILITY_NUM 31
#define MAX_MON_MOVES 4
#define POKEMON_NAME_LENGTH 12
#define MON_DATA_NICKNAME 30
#define MOVES_COUNT 100
#define MON_DATA_SPECIES 1
#define MON_DATA_HELD_ITEM 2
#define MON_DATA_POKEBALL 3
#define MON_DATA_TERA_TYPE 4
#define MON_DATA_DYNAMAX_LEVEL 5
#define MON_DATA_EXP 6
#define MON_DATA_MOVE1 10
#define MON_DATA_COOL_RIBBON 20
#define MON_DATA_TOUGH_RIBBON 24
#define EOS 255
struct BoxPokemon { u32 personality,otId; u8 nickname[10],language,hasSpecies,isBadEgg,otName[7]; u16 checksum; union { u32 raw[12]; } secure; };
struct Pokemon { struct BoxPokemon box; u32 status; u8 level,mail; u16 hp,maxHP; u8 padding[10]; };
u32 GetMonData(struct Pokemon *,u32,...); int IsSpeciesEnabled(u32);
#endif
