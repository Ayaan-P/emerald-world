#ifdef PORTABLE
#include "global.h"
#include "battle_setup.h"
#include "data.h"
#include "constants/trainers.h"

/* Native party records and trainer IDs are campaign-owned external data. */
static struct ExpansionTrainer sRuntimeTrainers[TRAINERS_COUNT];
static struct TrainerMon sRuntimeParties[TRAINERS_COUNT][PARTY_SIZE];

struct NativeTrainerBattleParams NativeBattle_GetTrainerParams(void)
{
    return (struct NativeTrainerBattleParams) { gTrainerBattleOpponent_A, gTrainerBattleOpponent_B, FALSE };
}

const struct ExpansionTrainer *GetTrainerStructFromId(u16 id)
{
    if (id >= TRAINER_PARTNER(PARTNER_NONE) && id < TRAINER_PARTNER(PARTNER_COUNT))
        return &gBattlePartners[0][id - TRAINER_PARTNER(PARTNER_NONE)];
    if (id >= TRAINERS_COUNT) return NULL;
    const struct Trainer *source = &gTrainers[id];
    struct ExpansionTrainer *runtimeTrainer = &sRuntimeTrainers[id];
    struct TrainerMon *runtimeParty = sRuntimeParties[id];
    memset(runtimeTrainer, 0, sizeof(*runtimeTrainer));
    memset(runtimeParty, 0, sizeof(sRuntimeParties[id]));
    runtimeTrainer->aiFlags = source->aiFlags;
    runtimeTrainer->trainerClass = source->trainerClass;
    runtimeTrainer->encounterMusic = source->encounterMusic_gender & 0x7f;
    runtimeTrainer->gender = source->encounterMusic_gender >> 7;
    runtimeTrainer->battleType = source->doubleBattle;
    runtimeTrainer->trainerPic = source->trainerPic;
    runtimeTrainer->partySize = source->partySize;
    memcpy(runtimeTrainer->trainerName, source->trainerName, sizeof(source->trainerName));
    for (u32 i = 0; i < MAX_TRAINER_ITEMS; i++) runtimeTrainer->items[i] = source->items[i];
    for (u32 i = 0; i < source->partySize && i < PARTY_SIZE; i++)
    {
        struct TrainerMon *dest = &runtimeParty[i];
        u32 iv;
        if (source->partyFlags & F_TRAINER_PARTY_CUSTOM_MOVESET)
        {
            if (source->partyFlags & F_TRAINER_PARTY_HELD_ITEM)
            {
                const struct TrainerMonItemCustomMoves *mon = &source->party.ItemCustomMoves[i];
                dest->species = mon->species; dest->lvl = mon->lvl; iv = mon->iv;
                dest->heldItem = mon->heldItem;
                memcpy(dest->moves, mon->moves, sizeof(dest->moves));
            }
            else
            {
                const struct TrainerMonNoItemCustomMoves *mon = &source->party.NoItemCustomMoves[i];
                dest->species = mon->species; dest->lvl = mon->lvl; iv = mon->iv;
                memcpy(dest->moves, mon->moves, sizeof(dest->moves));
            }
        }
        else if (source->partyFlags & F_TRAINER_PARTY_HELD_ITEM)
        {
            const struct TrainerMonItemDefaultMoves *mon = &source->party.ItemDefaultMoves[i];
            dest->species = mon->species; dest->lvl = mon->lvl; iv = mon->iv; dest->heldItem = mon->heldItem;
        }
        else
        {
            const struct TrainerMonNoItemDefaultMoves *mon = &source->party.NoItemDefaultMoves[i];
            dest->species = mon->species; dest->lvl = mon->lvl; iv = mon->iv;
        }
        iv = iv * MAX_PER_STAT_IVS / 255;
        dest->iv = iv | (iv << 5) | (iv << 10) | (iv << 15) | (iv << 20) | (iv << 25);
        dest->ball = BALL_POKE;
        dest->friendship = STANDARD_FRIENDSHIP;
        dest->teraType = TYPE_NONE;
    }
    runtimeTrainer->party = runtimeParty;
    return runtimeTrainer;
}

enum TrainerClassID GetTrainerClassFromId(u16 id) { return GetTrainerStructFromId(id)->trainerClass; }
enum TrainerPicID GetTrainerPicFromId(u16 id) { return GetTrainerStructFromId(id)->trainerPic; }
u64 GetTrainerAIFlagsFromId(u16 id) { return GetTrainerStructFromId(id)->aiFlags; }
const enum Item *GetTrainerItemsFromId(u16 id) { return GetTrainerStructFromId(id)->items; }
const struct TrainerMon *GetTrainerPartyFromId(u16 id) { return GetTrainerStructFromId(id)->party; }
u8 GetTrainerPartySizeFromId(u16 id) { return GetTrainerStructFromId(id)->partySize; }
struct StartingStatuses GetTrainerStartingStatusFromId(u16 id) { return GetTrainerStructFromId(id)->startingStatus; }
#endif
