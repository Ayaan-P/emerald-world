#ifndef GUARD_PLATFORM_DEXNAV_NATIVE_H
#define GUARD_PLATFORM_DEXNAV_NATIVE_H
#ifdef PORTABLE
#include "pokemon.h"
#include "sprite.h"
#include "wild_encounter.h"

#define DEXNAV_HEADER_NONE 0xFFFF
#define NUM_HIDDEN_MONS_ENCOUNTER_SLOTS 3
#define DEXNAV_EFFECT_CAVE_DUST 0xFE

/* Runtime-only state. Never embedded in SaveBlock or transmitted to peers. */
struct DexNavNativeState
{
    u16 registeredSpecies;
    u16 detectorSteps;
    u8 dexNavChain;
    u8 dexNavSearchLevels[NUM_SPECIES];
    bool8 searching;
};
extern struct DexNavNativeState gDexNavNativeState;

void DexNavNative_Init(const char *savePath, bool8 allowPersistence);
void DexNavNative_Persist(void);
bool8 DexNavNative_Available(void);
void DexNavNative_SetInput(u16 newKeys, u16 heldKeys, bool8 canAct);
bool8 DexNavNative_HandleInput(void);
bool8 DexNavNative_ShouldCreep(u16 heldKeys);
void DexNavNative_SetCreeping(bool8 creeping);
bool8 DexNavNative_IsCreeping(void);
void DexNavNative_BattleFinished(u8 outcome);
void DexNavNative_CancelForOtherBattle(void);
void DexNavNative_SetBattleOwner(u16 species);
bool8 DexNavNative_OwnsWildMon(void);

u16 DexNavNative_GetHeader(void);
const struct WildPokemonInfo *DexNavNative_GetHiddenInfo(u16 headerId);
u8 DexNavNative_Ability(u16 species, u8 abilityNum);
u8 DexNavNative_Type(u16 species, u8 typeNum);
const u8 *DexNavNative_SpeciesName(u16 species);
const u8 *DexNavNative_MoveName(u16 move);
u16 DexNavNative_RandomEggMove(u16 species);
void DexNavNative_GenerateMoves(u16 species, u8 level, u16 *moves);
void DexNavNative_PerfectIVs(struct BoxPokemon *mon, u8 count);
void WildEncounter_CreateDexNavMon(u16 species, u8 level);
u16 WildEncounter_GetDexNavHeader(void);

bool8 DexNavNative_AcquireFieldResources(u16 species);
void DexNavNative_ReleaseFieldResources(void);
u8 DexNavNative_ItemPalette(void);
u8 DexNavNative_CreateMonIcon(u16 species, s16 x, s16 y, u8 priority);
void DexNavNative_FreeIcons(void);
u8 DexNavNative_StartEffect(u8 effectId);
void DexNavNative_StopEffect(u8 spriteId);
void DexNavNative_LoadWindowGfx(u8 windowId, u16 baseBlock, u16 paletteOffset);
void DexNavNative_BeginGui(void);
void DexNavNative_EndGui(void);
bool8 DexNavNative_ResourcesFailed(void);
u8 DexNavNative_CreateSprite(const struct SpriteTemplate *template, s16 x, s16 y, u8 priority);
void DexNavNative_DestroySprite(u8 spriteId);
void DexNavNative_LoadSheet(const struct CompressedSpriteSheet *sheet);

extern const struct CompressedSpriteSheet gDexNavNative_MoveTypesSheet;
extern const struct SpriteTemplate gDexNavNative_MoveTypesTemplate;
extern const struct SpriteSheet gDexNavNative_HeldItemSheet;
extern const u16 gDexNavNative_HeldItemPalette[];

#endif
#endif
