/* Native boundary for the RHH DexNav module. No Expansion save, party or ID ABI. */
#ifdef PORTABLE
#include "global.h"
#include "platform/dexnav_native.h"
#include "platform/generated_map.h"
#include "dexnav.h"
#include "battle.h"
#include "battle_main.h"
#include "battle_pike.h"
#include "battle_pyramid.h"
#include "data.h"
#include "decompress.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "field_effect.h"
#include "field_player_avatar.h"
#include "fieldmap.h"
#include "graphics.h"
#include "link.h"
#include "main.h"
#include "malloc.h"
#include "menu.h"
#include "overworld.h"
#include "palette.h"
#include "pokemon_icon.h"
#include "random.h"
#include "safari_zone.h"
#include "text_window.h"
#include "window.h"
#include "constants/abilities.h"
#include "constants/battle.h"
#include "constants/event_object_movement.h"
#include "constants/field_effects.h"
#include "constants/moves.h"
#include "constants/region_map_sections.h"
#include "constants/rgb.h"
#include "platform/native_link.h"
#include "platform/native_save.h"
#include <stdio.h>
#include <string.h>
#ifndef _WIN32
#include <sys/stat.h>
#endif

/* Existing native species table; preserve its IDs and layout. */
extern const struct Evolution gEvolutionTable[NUM_SPECIES][EVOS_PER_MON];
STATIC_ASSERT(sizeof(struct Pokemon) == 100, DexNavNativePokemonMustRemain100Bytes);
struct DexNavNativeState gDexNavNativeState;
static bool8 sCreeping, sGui, sFailed;
static u16 sNewKeys, sHeldKeys, sBattleOwner;
static u32 sBattlePersonality;
static bool8 sCanAct;
static bool8 sOpenRequested;
static u8 sTrainer[4];
static bool8 sTrainerBound;
/* Explicit byte format: magic, trainer ID, native species count, registration,
 * levels, checksum. No pointers, native padding, chain or shared state on disk. */
#define PROGRESS_SIZE (16 + NUM_SPECIES)
static u8 sDiskProgress[PROGRESS_SIZE];
static u8 sProgressJournal[2][PROGRESS_SIZE];
static u8 sProgressSlot;
#ifndef _WIN32
static FILE *sProgressFile;
#endif
static u16 sBgPalette[16], sObjPalettes[3][16];
static u16 sBgPaletteFaded[16], sObjPalettesFaded[3][16];
static u8 sFieldPaletteSlots[3] = {0xFF, 0xFF, 0xFF};
static bool8 sFieldResources, sSharedHud, sBgPaletteWritten, sTextBadges;
static u8 sFieldIcon[0x200];
static u16 sFieldSpecies;
static u16 sEffectTileStart = 0xFFFF;
#define ICON_TAG_BASE 0xD800
#define ICON_PALETTE_TAG 0xD740
#define EFFECT_PALETTE_TAG 0xD741
#define EFFECT_TILE_TAG 0xD742
#define TYPE_TAG 0xD743
#define DEXNAV_SPRITE_OWNER 0x444E
static const u16 sFieldTags[3] = {ICON_PALETTE_TAG, HELD_ITEM_TAG, EFFECT_PALETTE_TAG};
static u8 sIconCount;
static u16 sIconTags[24];
static struct SpriteTemplate sIconTemplates[24];

static u16 ProgressChecksum(const u8 *bytes)
{
    u16 sum = 0x6D31;
    u32 i;
    for (i = 0; i < PROGRESS_SIZE - 2; ++i)
        sum = (sum << 5 | sum >> 11) ^ bytes[i];
    return sum;
}

static bool8 ValidProgress(const u8 *bytes)
{
    u16 registered = bytes[10] | bytes[11] << 8;
    u16 checksum = bytes[PROGRESS_SIZE - 2] | bytes[PROGRESS_SIZE - 1] << 8;
    return memcmp(bytes, "DNV2", 4) == 0
        && (bytes[8] | bytes[9] << 8) == NUM_SPECIES
        && (registered & DEXNAV_MASK_SPECIES) < NUM_SPECIES
        && (registered >> 14) <= ENCOUNTER_TYPE_WATER
        && checksum == ProgressChecksum(bytes);
}

static u16 ProgressSequence(const u8 *bytes) { return bytes[12] | bytes[13] << 8; }

#ifndef _WIN32
static u8 NewestProgressSlot(const u8 journal[2][PROGRESS_SIZE])
{
    bool8 valid0 = ValidProgress(journal[0]);
    bool8 valid1 = ValidProgress(journal[1]);
    if (!valid0 && !valid1) return 0xFF;
    return valid1 && (!valid0
        || (s16)(ProgressSequence(journal[1]) - ProgressSequence(journal[0])) > 0);
}
#endif

static void BindTrainer(void)
{
    if (sTrainerBound && memcmp(sTrainer, gSaveBlock2Ptr->playerTrainerId, 4) == 0)
        return;
    /* A new game in the same profile must not inherit another trainer's levels. */
    memset(&gDexNavNativeState, 0, sizeof(gDexNavNativeState));
    memcpy(sTrainer, gSaveBlock2Ptr->playerTrainerId, 4);
    sTrainerBound = TRUE;
    sBattleOwner = SPECIES_NONE;
    if (ValidProgress(sDiskProgress) && memcmp(sTrainer, sDiskProgress + 4, 4) == 0)
    {
        gDexNavNativeState.registeredSpecies = sDiskProgress[10] | sDiskProgress[11] << 8;
        memcpy(gDexNavNativeState.dexNavSearchLevels, sDiskProgress + 14, NUM_SPECIES);
    }
}

void DexNavNative_Init(const char *savePath, bool8 allowPersistence)
{
#ifndef _WIN32
    char path[4096];
    struct stat info;
    memset(sDiskProgress, 0, sizeof(sDiskProgress));
    if (!allowPersistence || savePath == NULL || sProgressFile != NULL)
        return;
    if (snprintf(path, sizeof(path), "%s.dexnav", savePath) >= (int)sizeof(path))
        return;
    /* Reuse native sandbox ownership/symlink/hardlink checks and lifetime lock.
     * No HOME discovery and no launcher/server/shared-world plumbing. */
    sProgressFile = NativeSave_Open(path);
    if (sProgressFile == NULL)
    {
        fprintf(stderr, "DexNav progression is session-only: private sidecar unavailable.\n");
        return;
    }
    if (fstat(fileno(sProgressFile), &info) != 0 || (info.st_mode & 077) != 0)
    {
        fclose(sProgressFile);
        sProgressFile = NULL;
        fprintf(stderr, "DexNav progression is session-only: private file permissions required.\n");
        return;
    }
    if (info.st_size == sizeof(sProgressJournal)
        && NativeSave_Read(sProgressFile, 0, sProgressJournal, sizeof(sProgressJournal)))
    {
        u8 newest = NewestProgressSlot(sProgressJournal);
        if (newest != 0xFF)
        {
            sProgressSlot = newest;
            memcpy(sDiskProgress, sProgressJournal[sProgressSlot], sizeof(sDiskProgress));
        }
    }
#else
    (void)savePath;
    (void)allowPersistence;
#endif
}

void DexNavNative_Persist(void)
{
    u16 checksum, registered;
    u16 sequence = ProgressSequence(sDiskProgress) + 1;
    BindTrainer();
    registered = gDexNavNativeState.registeredSpecies;
    memset(sDiskProgress, 0, sizeof(sDiskProgress));
    memcpy(sDiskProgress, "DNV2", 4);
    memcpy(sDiskProgress + 4, sTrainer, 4);
    sDiskProgress[8] = NUM_SPECIES & 0xFF;
    sDiskProgress[9] = NUM_SPECIES >> 8;
    sDiskProgress[10] = registered & 0xFF;
    sDiskProgress[11] = registered >> 8;
    sDiskProgress[12] = sequence & 0xFF;
    sDiskProgress[13] = sequence >> 8;
    memcpy(sDiskProgress + 14, gDexNavNativeState.dexNavSearchLevels, NUM_SPECIES);
    checksum = ProgressChecksum(sDiskProgress);
    sDiskProgress[PROGRESS_SIZE - 2] = checksum & 0xFF;
    sDiskProgress[PROGRESS_SIZE - 1] = checksum >> 8;
    sProgressSlot ^= 1;
    memcpy(sProgressJournal[sProgressSlot], sDiskProgress, sizeof(sDiskProgress));
#ifndef _WIN32
    if (sProgressFile)
    {
        struct stat info;
        /* Journal keeps one previous valid record across a torn write without
         * replacing the locked inode. Unchanged slot bytes remain identical. */
        if (fstat(fileno(sProgressFile), &info) != 0 || (info.st_mode & 077) != 0
            || !NativeSave_Write(sProgressFile, sProgressJournal, sizeof(sProgressJournal)))
        {
            fprintf(stderr, "DexNav progression could not be persisted. Trainer save is unchanged.\n");
            fclose(sProgressFile);
            sProgressFile = NULL;  // Preserve the last valid slot after an I/O failure.
        }
    }
#endif
}

bool8 DexNavNative_Available(void)
{
    u32 i;
#if GENERATED_CAVE_WILDLIFE
    /* DexNav reads compiled map headers; do not offer a mismatched roster. */
    if (GeneratedMap_Wildlife() != NULL) return FALSE;
#endif
    if (!FlagGet(FLAG_SYS_POKEDEX_GET) || GetSafariZoneFlag() || InBattlePike()
        || CurrentBattlePyramidLocation() != PYRAMID_LOCATION_NONE
        || gMapHeader.regionMapSectionId == MAPSEC_BATTLE_FRONTIER
        || IsOverworldLinkActive() || NativeLink_IsActive() || gMain.inBattle)
        return FALSE;
    for (i = 0; i < PARTY_SIZE; ++i)
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
            && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)
            && GetMonData(&gPlayerParty[i], MON_DATA_HP))
            break;
    if (i == PARTY_SIZE)
        return FALSE;
    BindTrainer();
    return TRUE;
}

void DexNavNative_SetInput(u16 newKeys, u16 heldKeys, bool8 canAct)
{
    sNewKeys = newKeys;
    sHeldKeys = heldKeys;
    sCanAct = canAct;
}

bool8 DexNavNative_HandleInput(void)
{
    if (sOpenRequested && sCanAct)
    {
        sOpenRequested = FALSE;
        if (DexNavNative_Available())
            return DexNav_OpenFromField();
    }
    if (sNewKeys & (START_BUTTON | SELECT_BUTTON))
        EndDexNavSearch();
    if (DexNav_Update())
        return TRUE;
    if (!sCanAct || !(sNewKeys & R_BUTTON) || !DexNavNative_Available())
        return FALSE;
    sNewKeys = 0;
    if (sHeldKeys & L_BUTTON)
        return DexNav_OpenFromField();
    /* TRUE tells the overworld to lock controls. Only failure message scripts
     * need that lock. A successful hunt must remain a real free-moving field. */
    return TryStartDexNavSearch();
}

bool8 DexNav_RequestOpen(void)
{
    if (!DexNavNative_Available() || sOpenRequested)
        return FALSE;
    sOpenRequested = TRUE;
    return TRUE;
}

/* Match the existing native movement helper without exporting its private API. */
bool8 DexNavNative_ElevationMismatchAt(u8 elevation, s16 x, s16 y)
{
    u8 mapElevation;
    if (elevation == ELEVATION_TRANSITION)
        return FALSE;
    mapElevation = MapGridGetElevationAt(x, y);
    return mapElevation != ELEVATION_TRANSITION
        && mapElevation != ELEVATION_MULTI_LEVEL && mapElevation != elevation;
}

bool8 DexNavNative_ShouldCreep(u16 heldKeys)
{
    return gDexNavNativeState.searching && (heldKeys & L_BUTTON)
        && !TestPlayerAvatarFlags(PLAYER_AVATAR_FLAG_MACH_BIKE | PLAYER_AVATAR_FLAG_ACRO_BIKE);
}
void DexNavNative_SetCreeping(bool8 creeping) { sCreeping = creeping; }
bool8 DexNavNative_IsCreeping(void) { return sCreeping; }

void DexNavNative_SetBattleOwner(u16 species)
{
    sBattleOwner = species;
    sBattlePersonality = GetMonData(&gEnemyParty[0], MON_DATA_PERSONALITY);
}
bool8 DexNavNative_OwnsWildMon(void)
{
    return sBattleOwner != SPECIES_NONE
        && sBattleOwner == GetMonData(&gEnemyParty[0], MON_DATA_SPECIES)
        && sBattlePersonality == GetMonData(&gEnemyParty[0], MON_DATA_PERSONALITY);
}
void DexNavNative_AbandonBattle(void)
{
    sBattleOwner = SPECIES_NONE;
    sBattlePersonality = 0;
    gDexNavSpecies = SPECIES_NONE;
    gDexNavNativeState.dexNavChain = 0;
}
void DexNavNative_PrepareNativeActivity(bool8 preserveEncounter)
{
    /* Relinquish the field allocation before any battle/trade heap transition.
     * Only the authenticated final-mon owner may retain encounter credit. */
    EndDexNavSearch();
    if (!preserveEncounter || !DexNavNative_OwnsWildMon())
        DexNavNative_AbandonBattle();
}
void DexNavNative_CancelForOtherBattle(void)
{
    DexNavNative_PrepareNativeActivity(!(gBattleTypeFlags & (BATTLE_TYPE_TRAINER | BATTLE_TYPE_LINK)));
}
void DexNavNative_BattleFinished(u8 outcome)
{
    u16 species = sBattleOwner;
    bool8 identity = DexNavNative_OwnsWildMon();
    sBattleOwner = SPECIES_NONE;  /* Consume before any return callback or whiteout. */
    sBattlePersonality = 0;
    if (!identity || species == SPECIES_NONE || species >= NUM_SPECIES)
    {
        if (species != SPECIES_NONE)
            gDexNavNativeState.dexNavChain = 0;
        gDexNavSpecies = SPECIES_NONE;
        return;
    }
    if (outcome == B_OUTCOME_WON || outcome == B_OUTCOME_CAUGHT)
    {
        if (gDexNavNativeState.dexNavSearchLevels[species] < 255)
            ++gDexNavNativeState.dexNavSearchLevels[species];
        IncrementDexNavChain();
        DexNavNative_Persist();
    }
    else
        gDexNavNativeState.dexNavChain = 0;
    gDexNavSpecies = SPECIES_NONE;
}

u16 DexNavNative_GetHeader(void) { return WildEncounter_GetDexNavHeader(); }
const struct WildPokemonInfo *DexNavNative_GetHiddenInfo(u16 headerId)
{
    (void)headerId;
    /* No hidden-only species table exists in native campaign data. */
    return NULL;
}
u8 DexNavNative_Ability(u16 species, u8 abilityNum)
{
    return species < NUM_SPECIES && abilityNum < 2 ? gSpeciesInfo[species].abilities[abilityNum] : ABILITY_NONE;
}
u8 DexNavNative_Type(u16 species, u8 typeNum)
{
    return species < NUM_SPECIES && typeNum < 2 ? gSpeciesInfo[species].types[typeNum] : TYPE_MYSTERY;
}
const u8 *DexNavNative_SpeciesName(u16 species) { return gSpeciesNames[species < NUM_SPECIES ? species : SPECIES_NONE]; }
const u8 *DexNavNative_MoveName(u16 move) { return gMoveNames[move < MOVES_COUNT ? move : MOVE_NONE]; }

extern const u16 gEggMoves[];
u16 DexNavNative_RandomEggMove(u16 species)
{
    u32 i, j, k, count = 0;
    const u16 *moves;
    /* Same reverse-evolution lookup as native daycare, without creating an egg. */
    for (k = 0; k < 5; ++k)
    {
        bool8 found = FALSE;
        for (i = 1; i < NUM_SPECIES && !found; ++i)
            for (j = 0; j < EVOS_PER_MON; ++j)
                if (gEvolutionTable[i][j].targetSpecies == species)
                {
                    species = i;
                    found = TRUE;
                    break;
                }
        if (!found) break;
    }
    /* Native flat learnset uses species + 20000 records and 0xFFFF terminator. */
    for (i = 0; gEggMoves[i] != 0xFFFF; ++i)
        if (gEggMoves[i] == species + 20000)
            break;
    if (gEggMoves[i] == 0xFFFF)
        return MOVE_NONE;
    moves = &gEggMoves[i + 1];
    while (moves[count] < 20000 && moves[count] != 0xFFFF)
        ++count;
    return count ? moves[Random() % count] : MOVE_NONE;
}

void DexNavNative_GenerateMoves(u16 species, u8 level, u16 *moves)
{
    struct Pokemon mon;
    u32 i;
    /* Temporary moveset creation never touches gEnemyParty or admission APIs. */
    CreateMon(&mon, species, level, USE_RANDOM_IVS, FALSE, 0, OT_ID_PLAYER_ID, 0);
    for (i = 0; i < MAX_MON_MOVES; ++i)
        moves[i] = GetMonData(&mon, MON_DATA_MOVE1 + i);
}
void DexNavNative_PerfectIVs(struct BoxPokemon *mon, u8 count)
{
    u8 indices[6] = {0, 1, 2, 3, 4, 5};
    u8 i, chosen, temp, value = 31;
    if (count > 3) count = 3;
    for (i = 0; i < count; ++i)
    {
        chosen = i + Random() % (6 - i);
        temp = indices[i]; indices[i] = indices[chosen]; indices[chosen] = temp;
        SetBoxMonData(mon, MON_DATA_HP_IV + indices[i], &value);
    }
}

static const u32 sHeldItemGfx[] = INCGFX_U32("graphics/party_menu/hold_icons.png", ".4bpp");
const u16 gDexNavNative_HeldItemPalette[] = INCGFX_U16("graphics/party_menu/hold_icons.png", ".gbapal");
const struct SpriteSheet gDexNavNative_HeldItemSheet = {sHeldItemGfx, sizeof(sHeldItemGfx), HELD_ITEM_TAG};
static const u32 sCaveDust[] = INCGFX_U32("graphics/field_effects/pics/cave_dust.png", ".4bpp");
static const u16 sCaveDustPal[] = INCGFX_U16("graphics/field_effects/palettes/cave_dust.pal", ".gbapal");
static const u16 sWindowPal[] = INCGFX_U16("graphics/text_window/dexnav_pal.pal", ".gbapal");
static const struct OamData sIconOam = {.shape = SPRITE_SHAPE(32x32), .size = SPRITE_SIZE(32x32), .priority = 0};
static const struct OamData sDustOam = {.shape = SPRITE_SHAPE(16x16), .size = SPRITE_SIZE(16x16), .priority = 2};
static const union AnimCmd sDustAnim[] = {ANIMCMD_FRAME(0, 8), ANIMCMD_FRAME(4, 8), ANIMCMD_FRAME(8, 8), ANIMCMD_FRAME(12, 8), ANIMCMD_JUMP(0)};
static const union AnimCmd *const sDustAnims[] = {sDustAnim};
static const struct SpriteTemplate sDustTemplate = {
    .tileTag = EFFECT_TILE_TAG, .paletteTag = EFFECT_PALETTE_TAG, .oam = &sDustOam,
    .anims = sDustAnims, .affineAnims = gDummySpriteAffineAnimTable, .callback = SpriteCallbackDummy,
};
extern const struct SpriteTemplate *const gFieldEffectObjectTemplatePointers[];
extern const u16 gFieldEffectObjectPalette0[];
extern const u16 gFieldEffectObjectPalette1[];
static struct SpriteTemplate sEffectTemplate;

static void SpriteCB_SearchSignal(struct Sprite *sprite)
{
    if (sprite->animEnded)
        StartSpriteAnim(sprite, 0);
}

static bool8 PaletteInUse(u8 slot)
{
    u32 i;
    for (i = 0; i < MAX_SPRITES; ++i)
        if (gSprites[i].inUse && gSprites[i].oam.paletteNum == slot)
            return TRUE;
    return FALSE;
}

/* Only pixels actually used by the field HUD reserve colors. The held-item
 * sprite uses the first tile (the second is mail), stars use the imported art,
 * and the caught marker is needed only for caught species. No quantization. */
static const u32 sHudStar[] = INCGFX_U32("graphics/dexnav/star.png", ".4bpp");
static const u32 sHudOwned[] = INCGFX_U32("graphics/dexnav/owned_icon.png", ".4bpp");

static u16 UsedColors(const u8 *tiles, u32 size)
{
    u16 mask = 0;
    u32 i;
    for (i = 0; i < size; ++i)
        mask |= (1 << (tiles[i] & 15)) | (1 << (tiles[i] >> 4));
    return mask | 1;  /* Transparent index may never become opaque. */
}

static bool8 PackFieldHud(u16 species, bool8 owned, u16 *palette)
{
    const u16 *iconPalette = GetValidMonIconPalettePtr(species);
    const u8 *icon = (const u8 *)GetMonIconPtr(species, 0, TRUE);
    u16 used = UsedColors((const u8 *)sHeldItemGfx, 32)
        | UsedColors((const u8 *)sHudStar, sizeof(sHudStar));
    u16 iconUsed = UsedColors(icon, sizeof(sFieldIcon));
    u8 map[16] = {0};
    u32 i, j;
    if (owned) used |= UsedColors((const u8 *)sHudOwned, sizeof(sHudOwned));
    CpuCopy16(gDexNavNative_HeldItemPalette, palette, PLTT_SIZE_4BPP);
    for (i = 1; i < 16; ++i)
    {
        if (!(iconUsed & (1 << i))) continue;
        for (j = 1; j < 16; ++j)
            if ((used & (1 << j)) && palette[j] == iconPalette[i]) break;
        if (j == 16)
        {
            for (j = 1; j < 16 && (used & (1 << j)); ++j) {}
            if (j == 16) return FALSE;
            palette[j] = iconPalette[i];
            used |= 1 << j;
        }
        map[i] = j;
    }
    for (i = 0; i < sizeof(sFieldIcon); ++i)
        sFieldIcon[i] = map[icon[i] & 15] | (map[icon[i] >> 4] << 4);
    return TRUE;
}

/* Record only allocations whose tags were absent, and never write a reserved
 * or active untagged bank. Borrowed native effect banks bypass this function. */
static bool8 AcquireFieldPalette(u8 index, const u16 *palette)
{
    u8 slot;
    if (IndexOfSpritePaletteTag(sFieldTags[index]) != 0xFF) return FALSE;
    slot = AllocSpritePalette(sFieldTags[index]);
    if (slot == 0xFF) return FALSE;
    if (slot < 12 || PaletteInUse(slot))
    {
        FreeSpritePaletteByTag(sFieldTags[index]);
        return FALSE;
    }
    sFieldPaletteSlots[index] = slot;
    CpuCopy16(&gPlttBufferUnfaded[OBJ_PLTT_ID(slot)], sObjPalettes[index], PLTT_SIZE_4BPP);
    CpuCopy16(&gPlttBufferFaded[OBJ_PLTT_ID(slot)], sObjPalettesFaded[index], PLTT_SIZE_4BPP);
    LoadPalette(palette, OBJ_PLTT_ID(slot), PLTT_SIZE_4BPP);
    return TRUE;
}

bool8 DexNavNative_AcquireFieldResources(u16 species, bool8 owned, bool8 hidden)
{
    u16 hudPalette[16];
    u32 i, freeSprites = 0;
    const u16 tags[] = {HELD_ITEM_TAG, OWNED_ICON_TAG, HIDDEN_SEARCH_TAG,
        HIDDEN_MON_ICON_TAG, LIT_STAR_TILE_TAG, EFFECT_TILE_TAG};
    if (sFieldResources || species == SPECIES_NONE || species >= NUM_SPECIES) return FALSE;
    sFailed = FALSE;
    for (i = 0; i < MAX_SPRITES; ++i)
        if (!gSprites[i].inUse) ++freeSprites;
    if (freeSprites < 9) return FALSE;
    for (i = 0; i < ARRAY_COUNT(tags); ++i)
        if (GetSpriteTileStartByTag(tags[i]) != 0xFFFF) return FALSE;
    for (i = 0; i < ARRAY_COUNT(sFieldTags); ++i)
        if (IndexOfSpritePaletteTag(sFieldTags[i]) != 0xFF) return FALSE;
    sFieldResources = TRUE;
    CpuCopy16(&gPlttBufferUnfaded[BG_PLTT_ID(14)], sBgPalette, sizeof(sBgPalette));
    CpuCopy16(&gPlttBufferFaded[BG_PLTT_ID(14)], sBgPaletteFaded, sizeof(sBgPaletteFaded));
    sFieldSpecies = species;
    sSharedHud = !hidden && PackFieldHud(species, owned, hudPalette);
    if (!AcquireFieldPalette(0, sSharedHud ? hudPalette : GetValidMonIconPalettePtr(species))) goto fail;
    /* An exact 15-color pack is not always possible (e.g. caught Wurmple).
     * Keep the original icon palette and render badge information using the
     * already-owned HUD window palette, rather than demand another OBJ bank. */
    sTextBadges = !hidden && !sSharedHud;
    if (!sSharedHud && !sTextBadges && !AcquireFieldPalette(1, gDexNavNative_HeldItemPalette)) goto fail;
    return TRUE;
fail:
    DexNavNative_ReleaseFieldResources();
    return FALSE;
}

void DexNavNative_ReleaseFieldResources(void)
{
    u32 i;
    bool8 ownsHud = IndexOfSpritePaletteTag(ICON_PALETTE_TAG) == sFieldPaletteSlots[0]
        && sFieldPaletteSlots[0] != 0xFF;
    if (!sFieldResources) return;
    DexNavNative_FreeIcons();
    for (i = 0; i < ARRAY_COUNT(sFieldTags); ++i)
    {
        if (sFieldPaletteSlots[i] != 0xFF
            && IndexOfSpritePaletteTag(sFieldTags[i]) == sFieldPaletteSlots[i])
        {
            LoadPalette(sObjPalettes[i], OBJ_PLTT_ID(sFieldPaletteSlots[i]), PLTT_SIZE_4BPP);
            CpuCopy16(sObjPalettesFaded[i], &gPlttBufferFaded[OBJ_PLTT_ID(sFieldPaletteSlots[i])], PLTT_SIZE_4BPP);
            FreeSpritePaletteByTag(sFieldTags[i]);
        }
        sFieldPaletteSlots[i] = 0xFF;
    }
    if (sBgPaletteWritten && ownsHud)
    {
        LoadPalette(sBgPalette, BG_PLTT_ID(14), sizeof(sBgPalette));
        CpuCopy16(sBgPaletteFaded, &gPlttBufferFaded[BG_PLTT_ID(14)], sizeof(sBgPaletteFaded));
    }
    if (sEffectTileStart != 0xFFFF && GetSpriteTileStartByTag(EFFECT_TILE_TAG) == sEffectTileStart)
        FreeSpriteTilesByTag(EFFECT_TILE_TAG);
    sEffectTileStart = 0xFFFF;
    sBgPaletteWritten = FALSE;
    sSharedHud = FALSE;
    sTextBadges = FALSE;
    sFieldResources = FALSE;
}
u8 DexNavNative_ItemPalette(void) { return sFieldPaletteSlots[sSharedHud ? 0 : 1]; }
bool8 DexNavNative_TextBadges(void) { return sTextBadges; }

/* Field tilesets use BG palettes 0..12 (NUM_PALS_TOTAL). BG14 and the
 * frame tiles at 0x214 are the standard window resources from menu.c,
 * already used by the DexNav window. No BG13 or new palette is borrowed.
 * AddWindow does not detect manually assigned tile collisions, so reject
 * any live window using our tiles or palette before loading the HUD.
 * The native dialogue window at 0x194 is disjoint even at 28x5 tiles. */
bool8 DexNavNative_CanUseHudWindow(u8 width, u8 height)
{
    u32 i;
    u32 end = 8 + width * height;
    for (i = 0; i < WINDOWS_MAX; ++i)
    {
        const struct WindowTemplate *w = &gWindows[i].window;
        if (w->bg == 0xFF) continue;
        if (w->paletteNum == 14) return FALSE;
        if (w->bg == 0 && w->baseBlock < end
            && w->baseBlock + w->width * w->height > 8) return FALSE;
    }
    return end <= 0x194;
}

u8 DexNavNative_CreateMonIcon(u16 species, s16 x, s16 y, u8 priority)
{
    struct SpriteTemplate template = {
        .paletteTag = ICON_PALETTE_TAG, .oam = &sIconOam,
        .anims = gDummySpriteAnimTable, .affineAnims = gDummySpriteAffineAnimTable,
        .callback = SpriteCallbackDummy,
    };
    struct SpriteSheet sheet;
    if (sIconCount >= ARRAY_COUNT(sIconTags) || species >= NUM_SPECIES)
    { sFailed = TRUE; return MAX_SPRITES; }
    template.tileTag = ICON_TAG_BASE + sIconCount;
    if (GetSpriteTileStartByTag(template.tileTag) != 0xFFFF)
    { sFailed = TRUE; return MAX_SPRITES; }
    if (sGui)
        template.paletteTag = gMonIconPaletteTable[GetValidMonIconPalIndex(species)].tag;
    if (!sGui && (!sFieldResources || species != sFieldSpecies))
    { sFailed = TRUE; return MAX_SPRITES; }
    sheet.data = !sGui && sSharedHud ? sFieldIcon : GetMonIconPtr(species, 0, TRUE);
    sheet.size = 0x200;  /* One native 32x32 frame, no unsafe mon-icon allocator. */
    sheet.tag = template.tileTag;
    LoadSpriteSheet(&sheet);
    if (GetSpriteTileStartByTag(sheet.tag) == 0xFFFF)
    { sFailed = TRUE; return MAX_SPRITES; }
    sIconTags[sIconCount] = sheet.tag;
    sIconTemplates[sIconCount] = template;
    return DexNavNative_CreateSprite(&sIconTemplates[sIconCount++], x, y, priority);
}
void DexNavNative_FreeIcons(void)
{
    while (sIconCount) FreeSpriteTilesByTag(sIconTags[--sIconCount]);
}

u8 DexNavNative_CreateSprite(const struct SpriteTemplate *template, s16 x, s16 y, u8 priority)
{
    struct SpriteTemplate checked = *template;
    u8 id;
    if (!sGui && sSharedHud && checked.paletteTag == HELD_ITEM_TAG)
        checked.paletteTag = ICON_PALETTE_TAG;
    if (checked.anims == NULL) checked.anims = gDummySpriteAnimTable;
    if (checked.affineAnims == NULL) checked.affineAnims = gDummySpriteAffineAnimTable;
    if (checked.callback == NULL) checked.callback = SpriteCallbackDummy;
    if (checked.tileTag != TAG_NONE && GetSpriteTileStartByTag(checked.tileTag) == 0xFFFF)
    { sFailed = TRUE; return MAX_SPRITES; }
    if (checked.paletteTag != TAG_NONE && IndexOfSpritePaletteTag(checked.paletteTag) == 0xFF)
    { sFailed = TRUE; return MAX_SPRITES; }
    id = CreateSprite(&checked, x, y, priority);
    if (id == MAX_SPRITES) sFailed = TRUE;
    /* Sprite keeps template pointer; use caller's static template, never stack. */
    if (id != MAX_SPRITES)
    {
        gSprites[id].template = template;
        gSprites[id].data[7] = DEXNAV_SPRITE_OWNER;
    }
    return id;
}

void DexNavNative_DestroySprite(u8 spriteId)
{
    if (spriteId < MAX_SPRITES && gSprites[spriteId].inUse
        && gSprites[spriteId].data[7] == DEXNAV_SPRITE_OWNER)
        DestroySprite(&gSprites[spriteId]);
}
void DexNavNative_LoadSheet(const struct CompressedSpriteSheet *sheet)
{
    struct SpriteSheet raw;
    void *buffer;
    u32 size = GetDecompressedDataSize(sheet->data);
    if (size < sheet->size || size > 0x4000)
    { sFailed = TRUE; return; }
    buffer = Alloc(size);
    if (buffer == NULL)
    { sFailed = TRUE; return; }
    LZDecompressWram(sheet->data, buffer);
    raw.data = buffer;
    raw.size = sheet->size;
    raw.tag = sheet->tag;
    LoadSpriteSheet(&raw);
    if (GetSpriteTileStartByTag(raw.tag) == 0xFFFF) sFailed = TRUE;
    Free(buffer);
}

/* A native tag alone is not proof: seasonal/map effects may reuse it with
 * different colors. Borrow only an exact unfaded native palette, read-only. */
static bool8 UseEffectPalette(u16 nativeTag, const u16 *palette)
{
    u8 slot = IndexOfSpritePaletteTag(nativeTag);
    if (nativeTag != TAG_NONE && slot != 0xFF
        && memcmp(&gPlttBufferUnfaded[OBJ_PLTT_ID(slot)], palette, PLTT_SIZE_4BPP) == 0)
    {
        sEffectTemplate.paletteTag = nativeTag;
        return TRUE;
    }
    if (sFieldPaletteSlots[2] == 0xFF)
    {
        if (!AcquireFieldPalette(2, palette)) return FALSE;
    }
    else
    {
        if (IndexOfSpritePaletteTag(EFFECT_PALETTE_TAG) != sFieldPaletteSlots[2]) return FALSE;
        LoadPalette(palette, OBJ_PLTT_ID(sFieldPaletteSlots[2]), PLTT_SIZE_4BPP);
    }
    sEffectTemplate.paletteTag = EFFECT_PALETTE_TAG;
    return TRUE;
}

u8 DexNavNative_StartEffect(u8 effectId)
{
    s16 x = gFieldEffectArguments[0], y = gFieldEffectArguments[1];
    u8 id;
    u8 templateId = 0xFF;
    const u16 *palette = gFieldEffectObjectPalette0;
    const struct SpriteSheet sheet = {sCaveDust, sizeof(sCaveDust), EFFECT_TILE_TAG};
    switch (effectId)
    {
    case FLDEFF_UNUSED_GRASS:
        templateId = FLDEFFOBJ_UNUSED_GRASS;
        palette = gFieldEffectObjectPalette1;
        break;
    case FLDEFF_UNUSED_GRASS_2:
        templateId = FLDEFFOBJ_UNUSED_GRASS_2;
        palette = gFieldEffectObjectPalette1;
        break;
    case FLDEFF_UNUSED_SAND: templateId = FLDEFFOBJ_UNUSED_SAND; break;
    case FLDEFF_WATER_SURFACING: templateId = FLDEFFOBJ_WATER_SURFACING; break;
    default: break;
    }
    if (!sFieldResources) return MAX_SPRITES;
    SetSpritePosToOffsetMapCoords(&x, &y, 8, 8);
    if (templateId != 0xFF)
    {
        /* Own the sprite, not the native field-effect lifecycle or palette. */
        sEffectTemplate = *gFieldEffectObjectTemplatePointers[templateId];
        sEffectTemplate.callback = SpriteCB_SearchSignal;
        if (!UseEffectPalette(sEffectTemplate.paletteTag, palette)) return MAX_SPRITES;
        id = DexNavNative_CreateSprite(&sEffectTemplate, x, y, 0xFF);
        if (id != MAX_SPRITES) gSprites[id].coordOffsetEnabled = TRUE;
        return id;
    }
    if (!UseEffectPalette(TAG_NONE, sCaveDustPal)) return MAX_SPRITES;
    if (GetSpriteTileStartByTag(EFFECT_TILE_TAG) == 0xFFFF)
    {
        LoadSpriteSheet(&sheet);
        sEffectTileStart = GetSpriteTileStartByTag(EFFECT_TILE_TAG);
        if (sEffectTileStart == 0xFFFF) return MAX_SPRITES;
    }
    id = DexNavNative_CreateSprite(&sDustTemplate, x, y, 0xFF);
    if (id != MAX_SPRITES) gSprites[id].coordOffsetEnabled = TRUE;
    return id;
}
void DexNavNative_StopEffect(u8 spriteId)
{
    if (spriteId < MAX_SPRITES && gSprites[spriteId].inUse
        && (gSprites[spriteId].template == &sDustTemplate
            || gSprites[spriteId].template == &sEffectTemplate))
        DexNavNative_DestroySprite(spriteId);
}
void DexNavNative_LoadWindowGfx(u8 windowId, u16 baseBlock, u16 paletteOffset)
{
    if (!sGui && sFieldResources) sBgPaletteWritten = TRUE;
    LoadUserWindowBorderGfx(windowId, baseBlock, paletteOffset);
    LoadPalette(sWindowPal, paletteOffset, sizeof(sWindowPal));
}
void DexNavNative_BeginGui(void) { sGui = TRUE; sFailed = FALSE; sIconCount = 0; }
void DexNavNative_EndGui(void) { DexNavNative_FreeIcons(); sGui = FALSE; }
bool8 DexNavNative_ResourcesFailed(void) { return sFailed; }

/* Reuse native summary-screen type tiles and native palette semantics. */
static const struct OamData sTypeOam = {.shape = SPRITE_SHAPE(32x16), .size = SPRITE_SIZE(32x16), .priority = 0};
#define TYPE_ANIM(n) static const union AnimCmd sType##n[] = {ANIMCMD_FRAME((n) * 8, 0), ANIMCMD_END}
TYPE_ANIM(0); TYPE_ANIM(1); TYPE_ANIM(2); TYPE_ANIM(3); TYPE_ANIM(4); TYPE_ANIM(5);
TYPE_ANIM(6); TYPE_ANIM(7); TYPE_ANIM(8); TYPE_ANIM(9); TYPE_ANIM(10); TYPE_ANIM(11);
TYPE_ANIM(12); TYPE_ANIM(13); TYPE_ANIM(14); TYPE_ANIM(15); TYPE_ANIM(16); TYPE_ANIM(17);
static const union AnimCmd *const sTypeAnims[] = {
    sType0, sType1, sType2, sType3, sType4, sType5, sType6, sType7, sType8,
    sType9, sType10, sType11, sType12, sType13, sType14, sType15, sType16, sType17,
};
const struct CompressedSpriteSheet gDexNavNative_MoveTypesSheet = {gMoveTypes_Gfx, (NUMBER_OF_MON_TYPES + 5) * 0x100, TYPE_TAG};
const struct SpriteTemplate gDexNavNative_MoveTypesTemplate = {
    .tileTag = TYPE_TAG, .paletteTag = TAG_NONE, .oam = &sTypeOam,
    .anims = sTypeAnims, .affineAnims = gDummySpriteAffineAnimTable, .callback = SpriteCallbackDummy,
};
#endif /* PORTABLE */
