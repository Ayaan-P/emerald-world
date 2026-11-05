#ifdef PORTABLE
#include "global.h"
#include "data.h"
#include "battle.h"
#include "battle_controllers.h"
#include "battle_main.h"
#include "battle_setup.h"
#include "battle_util.h"
#include "link.h"
#include "main.h"
#include "overworld.h"
#include "field_weather.h"
#include "pokemon.h"
#include "random.h"
#include "recorded_battle.h"
#include "party_menu.h"
#include "item.h"
#include "pokedex.h"
#include "constants/pokedex.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/characters.h"
#include "constants/weather.h"
#include "constants/opponents.h"
#include "platform/native_link.h"
#include "platform/world_activity.h"
#include "platform/world_coop.h"
#include "platform/world_coop_potion.h"
#include "platform/world_coop_roster.h"
#include <string.h>

/* No saved data or pointers cross this boundary. The native Pokemon layout is
 * exactly the 100-byte GBA layout on every supported native architecture. */
STATIC_ASSERT(sizeof(struct Pokemon) == 100, CoopPokemonWireSize);
enum { COOP_IDLE, COOP_EXCHANGE, COOP_BATTLE, COOP_REWARDS };
#if COOP_FULL_SIX_READY
#define COOP_VERSION 8
#else
#define COOP_VERSION 7
#endif
enum { COOP_MAGIC = 0x4357, COOP_TIMEOUT = 1800,
       COOP_CONFIRM = 4 + PARTY_SIZE, COOP_READY = COOP_CONFIRM + 1, COOP_COMMIT = COOP_CONFIRM + 2 };
struct CoopHeader
{
    u16 magic;
    u8 version, phase;
    u8 owner, count, environment, weather;
    u32 seed;
    u16 trainer;
    u8 kind, enemyCount;
#if COOP_FULL_SIX_READY
    u8 hiddenUsable, reserved[3];
#endif
};
struct CoopMonBlock
{
    u16 magic;
    u8 version, phase;
    struct Pokemon mon;
};
STATIC_ASSERT(sizeof(struct CoopMonBlock) <= 256, CoopBlockBound);
#if COOP_FULL_SIX_READY
STATIC_ASSERT(sizeof(struct CoopHeader) == 20, CoopHeaderWireSize);
#else
STATIC_ASSERT(sizeof(struct CoopHeader) == 16, CoopHeaderWireSize);
#endif
struct CoopCompletion
{
    u16 magic;
    u8 version, phase;
    u32 generation, seed;
    u8 sender, outcome, reward, catchOwner;
};
STATIC_ASSERT(sizeof(struct CoopCompletion) == 16, CoopCompletionWireSize);
/* Catch events use the authenticated master-to-controller FIFO, not saves. */
struct CoopCatchPacket
{
    u8 command, tag, owner, reserved;
    u32 generation;
    struct Pokemon mon;
};
STATIC_ASSERT(sizeof(struct CoopCatchPacket) == 108, CoopCatchWireSize);
enum { COOP_BALL_USE = 254, COOP_CATCH = 255 };
static struct
{
    u8 catchOwner;
    bool8 catchDelivered;
    u16 pendingBall, pendingMedicine;
    u16 medicineSpent[17];
    u16 medicineHeal, medicineItem;
    u32 medicineStatusBefore, medicineStatusAfter;
    u16 medicineHPAfter;
    u8 medicineAction, medicineBattler, medicineTarget;
    bool8 menuConfused, medicineClearConfusion;
    struct Pokemon caughtMon;
    u8 readySent, commitSent, commitEchoed, peerReady, peerCommit, peerOutcome, peerReward;
    u8 state, phase, local, ownerPeer, count, originalCount;
    u8 slots[MULTI_PARTY_SIZE];
    struct CoopRoster roster;
    struct Pokemon working[PARTY_SIZE];
    struct Pokemon menuShared[PARTY_SIZE];
    u8 menuSharedCount, fullMenuChoice;
    struct CoopRosterPlan fullMenuPlan;
    bool8 fullMenuActive;
    bool8 hiddenUsable[2];
#if COOP_FULL_SIX_READY
    u8 rosterAction, rosterBattler, rosterStage, rosterOrder[3];
#endif
    u8 rewardMask[PARTY_SIZE], rewardRead;
    u8 kind, enemyCount, capturedKind, capturedCount;
    u16 trainer, capturedTrainer;
    u8 moneyMultiplier[2], rewardMultiplier;
    u16 payday[2], rewardPayday;
    bool8 owner, sent, staged, captured, reward, partyMenuOrder;
    u16 timer;
    u8 environment, capturedEnvironment, weather, capturedWeather;
    u32 seed, capturedSeed, generation;
    struct Pokemon original[PARTY_SIZE];
    struct Pokemon selected[MULTI_PARTY_SIZE];
    struct Pokemon allies[PARTY_SIZE];
    struct Pokemon enemies[PARTY_SIZE], capturedEnemies[PARTY_SIZE];
    struct CoopHeader headers[2];
    struct CoopMonBlock outgoing;
    struct WorldCoopPublicMon publicMons[MAX_BATTLERS_COUNT];
    u8 publicSlots[MAX_BATTLERS_COUNT];
    bool8 publicValid[MAX_BATTLERS_COUNT];
} sCoop;

extern u16 GetBlockReceivedSize(u8 player);
extern void WorldActivity_ReturnFromCoopWildBattle(void);

/* Same checksum boundary as the native trade receiver. Never call GetMonData
 * before checking the encrypted checksum: it mutates a malformed box. */
static bool8 MonValid(struct Pokemon *mon, bool8 allowEmpty)
{
    struct Pokemon empty = {0};
    u16 checksum = 0;
    u32 key = mon->box.personality ^ mon->box.otId;
    u32 species;
    int i;
    for (i = 0; i < (int)ARRAY_COUNT(mon->box.secure.raw); i++)
    {
        u32 word = mon->box.secure.raw[i] ^ key;
        checksum += (u16)word;
        checksum += (u16)(word >> 16);
    }
    if (checksum != mon->box.checksum)
        return FALSE;
    species = GetMonData(mon, MON_DATA_SPECIES);
    if (species == SPECIES_NONE)
        return allowEmpty && memcmp(mon, &empty, sizeof(empty)) == 0;
    if (species >= NUM_SPECIES || !mon->box.hasSpecies || mon->box.isBadEgg
     || GetMonData(mon, MON_DATA_IS_EGG)
     || mon->box.language < LANGUAGE_JAPANESE || mon->box.language > LANGUAGE_SPANISH
     || mon->box.language == 6 || mon->level == 0 || mon->level > MAX_LEVEL
     || !mon->maxHP || mon->maxHP > 999 || mon->hp > mon->maxHP || (mon->status & ~0xFFFu)
     || !mon->attack || mon->attack > 999 || !mon->defense || mon->defense > 999
     || !mon->speed || mon->speed > 999 || !mon->spAttack || mon->spAttack > 999
     || !mon->spDefense || mon->spDefense > 999
     || (mon->mail != MAIL_NONE && mon->mail >= PARTY_SIZE)
     || GetMonData(mon, MON_DATA_HELD_ITEM) >= ITEMS_COUNT
     || GetMonData(mon, MON_DATA_HELD_ITEM) == ITEM_ENIGMA_BERRY
     || GetMonData(mon, MON_DATA_POKEBALL) > LAST_BALL
     || GetMonData(mon, MON_DATA_EXP) > 1640000)
        return FALSE;
    for (i = 0; i < MAX_MON_MOVES; i++)
    {
        u16 move = GetMonData(mon, MON_DATA_MOVE1 + i);
        if (move >= MOVES_COUNT
         || GetMonData(mon, MON_DATA_PP1 + i) > CalculatePPWithBonus(move, GetMonData(mon, MON_DATA_PP_BONUSES), i))
            return FALSE;
    }
    for (i = 0; i < (int)sizeof(mon->box.nickname); i++)
        if (mon->box.nickname[i] >= 0xFA && mon->box.nickname[i] != EOS)
            return FALSE;
    for (i = 0; i < (int)sizeof(mon->box.otName); i++)
        if (mon->box.otName[i] >= 0xFA && mon->box.otName[i] != EOS)
            return FALSE;
    return TRUE;
}

bool8 WorldCoop_CanSelectBall(u16 item)
{
    return sCoop.state == COOP_BATTLE && !sCoop.kind
        && item >= ITEM_MASTER_BALL && item <= LAST_BALL && item != ITEM_SAFARI_BALL
        && (sCoop.originalCount < PARTY_SIZE || !IsPokemonStorageFull());
}

void WorldCoop_CaptureWild(void)
{
    if (sCoop.state != COOP_IDLE)
        return;
    memset(sCoop.capturedEnemies, 0, sizeof(sCoop.capturedEnemies));
    sCoop.capturedEnemies[0] = gEnemyParty[0];
    sCoop.capturedKind = sCoop.capturedTrainer = 0;
    sCoop.capturedCount = 1;
    sCoop.capturedEnvironment = BattleSetup_GetEnvironmentId();
    sCoop.capturedWeather = GetCurrentWeather();
    sCoop.capturedSeed = gRngValue;
    sCoop.captured = MonValid(&sCoop.capturedEnemies[0], FALSE)
                  && GetMonData(&sCoop.capturedEnemies[0], MON_DATA_HP) != 0;
}

bool8 WorldCoop_CaptureTrainer(void)
{
    u8 i;
    if (sCoop.state != COOP_IDLE || !gTrainerBattleOpponent_A
     || gTrainerBattleOpponent_A >= TRAINERS_COUNT
     || !(gBattleTypeFlags & BATTLE_TYPE_TRAINER)
     || (gBattleTypeFlags & ~(BATTLE_TYPE_TRAINER | BATTLE_TYPE_DOUBLE)))
        return FALSE;
    WorldCoop_CreateTrainerParty();
    sCoop.captured = FALSE;
    sCoop.capturedCount = gTrainers[gTrainerBattleOpponent_A].partySize;
    if (!sCoop.capturedCount || sCoop.capturedCount > PARTY_SIZE)
        return FALSE;
    for (i = 0; i < sCoop.capturedCount; i++)
        if (!MonValid(&gEnemyParty[i], FALSE) || !GetMonData(&gEnemyParty[i], MON_DATA_HP))
            return FALSE;
    memcpy(sCoop.capturedEnemies, gEnemyParty, sizeof(sCoop.capturedEnemies));
    sCoop.capturedKind = (gBattleTypeFlags & BATTLE_TYPE_DOUBLE) ? 2 : 1;
    sCoop.capturedTrainer = gTrainerBattleOpponent_A;
    sCoop.capturedEnvironment = BattleSetup_GetEnvironmentId();
    sCoop.capturedWeather = GetCurrentWeather();
    sCoop.capturedSeed = gRngValue;
    sCoop.captured = TRUE;
    return TRUE;
}

bool8 WorldCoop_IsTrainer(void) { return sCoop.kind != 0 && sCoop.state != COOP_IDLE; }
bool8 WorldCoop_IsDoubleTrainer(void) { return WorldCoop_IsTrainer() && sCoop.kind == 2; }
/* The roster size is a bench, not permission to turn a single into a double.
 * kind records the original admitted format before the shared engine adds its
 * own DOUBLE flag for the two allied humans. */
bool8 WorldCoop_HasSecondOpponent(void) { return WorldCoop_IsDoubleTrainer() && sCoop.enemyCount > 1; }
u16 WorldCoop_TrainerId(void) { return sCoop.trainer; }

int WorldCoop_IsBattle(void)
{
    return sCoop.state == COOP_EXCHANGE || sCoop.state == COOP_BATTLE;
}

bool8 WorldCoop_IsPrivateRewards(void)
{
    return sCoop.state == COOP_REWARDS;
}

u8 WorldCoop_Environment(void) { return sCoop.environment; }
u8 WorldCoop_FieldWeather(void) { return sCoop.weather; }

const struct Pokemon *WorldCoop_GetOwnMon(u8 originalSlot)
{
    u8 i;
    if (originalSlot >= PARTY_SIZE)
        return NULL;
    if (!WorldCoop_IsBattle() || sCoop.fullMenuActive)
        return &gPlayerParty[originalSlot];
    if (sCoop.staged)
        for (i = 0; i < sCoop.count; i++)
            if (sCoop.slots[i] == originalSlot)
            {
                u8 index = sCoop.local * MULTI_PARTY_SIZE + i;
                if (sCoop.partyMenuOrder)
                    index = GetPartyIdFromBattlePartyId(index);
                return &gPlayerParty[index];
            }
    return &sCoop.working[originalSlot];
}

u8 WorldCoop_GetOwnPartyCount(void)
{
    return WorldCoop_IsBattle() ? sCoop.originalCount : gPlayerPartyCount;
}

/* Capture each currently staged private mon before rotating a slot. The
 * immutable original remains the abort rollback and identity boundary. */
static bool8 WorldCoop_CaptureWorkingParty(struct Pokemon out[PARTY_SIZE], u8 *activeStage)
{
    u8 i, active;
    if (sCoop.state != COOP_BATTLE || !sCoop.staged || sCoop.partyMenuOrder || sCoop.fullMenuActive) return FALSE;
    active = gBattlerPartyIndexes[sCoop.local * 2];
    if (active >= PARTY_SIZE || active / MULTI_PARTY_SIZE != sCoop.local) return FALSE;
    *activeStage = active % MULTI_PARTY_SIZE;
    memcpy(out, sCoop.working, sizeof(sCoop.working));
    for (i = 0; i < MULTI_PARTY_SIZE; i++)
    {
        u8 originalSlot = i < sCoop.count ? sCoop.slots[i] : COOP_ROSTER_EMPTY;
        struct Pokemon *mon, *original;
        if (sCoop.roster.staged[i] != originalSlot) return FALSE;
        if (originalSlot == COOP_ROSTER_EMPTY) continue;
        if (originalSlot >= PARTY_SIZE) return FALSE;
        mon = &gPlayerParty[sCoop.local * MULTI_PARTY_SIZE + i];
        original = &sCoop.original[originalSlot];
        if (!MonValid(mon, FALSE) || mon->box.personality != original->box.personality
         || mon->box.otId != original->box.otId
         || GetMonData(mon, MON_DATA_SPECIES) != GetMonData(original, MON_DATA_SPECIES)) return FALSE;
        out[originalSlot] = *mon;
    }
    return TRUE;
}

static bool8 WorldCoop_OwnHiddenUsable(void)
{
    u8 i, j;
    for (i = 0; i < PARTY_SIZE; i++)
    {
        if (!(sCoop.roster.validMask & (1u << i))) continue;
        for (j = 0; j < MULTI_PARTY_SIZE && sCoop.roster.staged[j] != i; j++);
        if (j == MULTI_PARTY_SIZE && MonValid(&sCoop.working[i], FALSE)
         && !GetMonData(&sCoop.working[i], MON_DATA_IS_EGG)
         && GetMonData(&sCoop.working[i], MON_DATA_HP)) return TRUE;
    }
    return FALSE;
}

bool8 WorldCoop_HasHiddenUsable(u8 battler)
{
    return COOP_FULL_SIX_READY && sCoop.state == COOP_BATTLE
        && battler < MAX_BATTLERS_COUNT && !(battler & BIT_SIDE)
        && sCoop.hiddenUsable[battler / 2];
}

bool8 WorldCoop_PlanRosterRotation(u8 originalSlot, struct CoopRosterPlan *plan)
{
    struct Pokemon candidate[PARTY_SIZE];
    u8 activeStage;
    if (originalSlot >= PARTY_SIZE || !WorldCoop_CaptureWorkingParty(candidate, &activeStage)
     || !MonValid(&candidate[originalSlot], FALSE) || GetMonData(&candidate[originalSlot], MON_DATA_IS_EGG)
     || !GetMonData(&candidate[originalSlot], MON_DATA_HP)) return FALSE;
    return CoopRoster_Plan(&sCoop.roster, originalSlot, activeStage, plan);
}

bool8 WorldCoop_CommitRosterRotation(const struct CoopRosterPlan *plan, const u8 participation[6], u8 knockedStageMask)
{
    struct Pokemon candidate[PARTY_SIZE];
    struct CoopRoster next = sCoop.roster;
    u8 i, activeStage;
    if (!plan || !participation || !WorldCoop_CaptureWorkingParty(candidate, &activeStage)
     || plan->incoming >= PARTY_SIZE || !MonValid(&candidate[plan->incoming], FALSE)
     || GetMonData(&candidate[plan->incoming], MON_DATA_IS_EGG)
     || !GetMonData(&candidate[plan->incoming], MON_DATA_HP)
     || !CoopRoster_Commit(&next, plan, activeStage, participation, knockedStageMask)) return FALSE;
    memcpy(sCoop.working, candidate, sizeof(sCoop.working));
    sCoop.roster = next;
    sCoop.hiddenUsable[sCoop.local] = WorldCoop_OwnHiddenUsable();
    gPlayerParty[sCoop.local * MULTI_PARTY_SIZE + plan->stage] = candidate[plan->incoming];
    sCoop.count = 0;
    for (i = 0; i < MULTI_PARTY_SIZE; i++)
    {
        sCoop.slots[i] = next.staged[i];
        if (next.staged[i] != COOP_ROSTER_EMPTY) sCoop.count = i + 1;
    }
    return TRUE;
}

/* A temporary local view. Nothing is sent and the shared party is restored
 * before the controller returns its choice. The engine integration remains
 * disabled until slot rotation and synchronization are wired together. */
bool8 WorldCoop_BeginFullPartyMenu(void)
{
    struct Pokemon candidate[PARTY_SIZE];
    u8 activeStage;
    if (!COOP_FULL_SIX_READY || !WorldCoop_CaptureWorkingParty(candidate, &activeStage)) return FALSE;
    memcpy(sCoop.menuShared, gPlayerParty, sizeof(sCoop.menuShared));
    sCoop.menuSharedCount = gPlayerPartyCount;
    memcpy(gPlayerParty, candidate, sizeof(candidate));
    gPlayerPartyCount = sCoop.originalCount;
    sCoop.fullMenuChoice = COOP_ROSTER_EMPTY;
    sCoop.fullMenuActive = TRUE;
    return TRUE;
}

bool8 WorldCoop_FullPartyMenuActive(void) { return sCoop.fullMenuActive; }

bool8 WorldCoop_ChooseFullPartyMenu(u8 originalSlot)
{
    struct CoopRosterPlan plan;
    u8 active;
    if (!COOP_FULL_SIX_READY || !sCoop.fullMenuActive || originalSlot >= PARTY_SIZE) return FALSE;
    active = gBattlerPartyIndexes[sCoop.local * 2];
    if (active >= PARTY_SIZE || active / MULTI_PARTY_SIZE != sCoop.local
     || !MonValid(&gPlayerParty[originalSlot], FALSE)
     || GetMonData(&gPlayerParty[originalSlot], MON_DATA_IS_EGG)
     || !GetMonData(&gPlayerParty[originalSlot], MON_DATA_HP)
     || !CoopRoster_Plan(&sCoop.roster, originalSlot, active % MULTI_PARTY_SIZE, &plan)) return FALSE;
    sCoop.fullMenuChoice = originalSlot;
    sCoop.fullMenuPlan = plan;
    return TRUE;
}

void WorldCoop_EndFullPartyMenu(void)
{
    if (!sCoop.fullMenuActive) return;
    memcpy(gPlayerParty, sCoop.menuShared, sizeof(sCoop.menuShared));
    gPlayerPartyCount = sCoop.menuSharedCount;
    sCoop.fullMenuActive = FALSE;
}

u8 WorldCoop_FullPartyChoice(void) { return sCoop.fullMenuChoice; }
u8 WorldCoop_FullPartyChoiceStage(void)
{
    return sCoop.fullMenuChoice < PARTY_SIZE
        ? sCoop.local * MULTI_PARTY_SIZE + sCoop.fullMenuPlan.stage : PARTY_SIZE;
}
u8 WorldCoop_FullPartyChoiceReply(void)
{
    u8 stage = WorldCoop_FullPartyChoiceStage();
    if (stage >= PARTY_SIZE) return PARTY_SIZE;
    return sCoop.fullMenuPlan.incoming == sCoop.fullMenuPlan.outgoing
        ? stage : (0x80 | (stage << 3) | sCoop.fullMenuChoice);
}

#if COOP_FULL_SIX_READY
/* Version-8 roster commands use authenticated controller channels and carry
 * only the newly selected combatant, never the owner's unstaged party. */
struct CoopRosterReply { u8 tag, owner, stage, hidden; struct Pokemon mon; };
struct CoopRosterMirror { u8 command, tag, owner, stage; u32 generation; u8 hidden, reserved[3]; struct Pokemon mon; };
STATIC_ASSERT(sizeof(struct CoopRosterReply) == WORLD_COOP_ROSTER_REPLY_SIZE, CoopRosterReplySize);
STATIC_ASSERT(sizeof(struct CoopRosterMirror) == 112, CoopRosterMirrorSize);
enum { ROSTER_WAIT_OWNER = 1, ROSTER_WAIT_MIRROR = 2, ROSTER_REPLY_TAG = 0xA7 };

bool8 WorldCoop_RosterChoiceValid(u8 battler, u8 choice)
{
    u8 stage = (choice >> 3) & 7, original = choice & 7;
    return sCoop.state == COOP_BATTLE && battler < MAX_BATTLERS_COUNT && !(battler & BIT_SIDE)
        && (choice & 0xC0) == 0x80 && original < PARTY_SIZE && stage < PARTY_SIZE
        && stage / MULTI_PARTY_SIZE == battler / 2 && stage != gBattlerPartyIndexes[battler];
}

bool8 WorldCoop_RosterRequestValid(const u8 *data, u16 size)
{
    u32 generation;
    u8 i, owner, stage;
    if (!data || sCoop.state != COOP_BATTLE || sCoop.generation != NativeLink_Generation()
     || size != 20 || data[0] != CONTROLLER_EXPUPDATE || data[1] != WORLD_COOP_ROSTER_REQUEST_TAG
     || data[2] < 1 || data[2] > 2 || data[3] >= PARTY_SIZE) return FALSE;
    owner = data[2] - 1; stage = data[8];
    memcpy(&generation, data + 4, sizeof(generation));
    if (generation != sCoop.generation || stage >= PARTY_SIZE || stage / MULTI_PARTY_SIZE != owner
     || stage == gBattlerPartyIndexes[owner * 2] || (data[15] & ~7) || data[16] || data[17] || data[18] || data[19]) return FALSE;
    for (i = 9; i < 15; i++) if (data[i] & ~7) return FALSE;
    return TRUE;
}

bool8 WorldCoop_ApplyRosterRequest(const u8 *data, u8 reply[WORLD_COOP_ROSTER_REPLY_SIZE])
{
    struct CoopRosterReply result = {0};
    struct CoopRosterPlan plan;
    u8 original, stage;
    if (!reply || !WorldCoop_RosterRequestValid(data, 20) || data[2] != sCoop.local + 1
     || gActiveBattler != sCoop.local * 2) return FALSE;
    original = data[3]; stage = data[8];
    if (sCoop.fullMenuChoice != original || !WorldCoop_PlanRosterRotation(original, &plan)
     || plan.stage + sCoop.local * MULTI_PARTY_SIZE != stage
     || !WorldCoop_CommitRosterRotation(&plan, data + 9, data[15])) return FALSE;
    sCoop.fullMenuChoice = COOP_ROSTER_EMPTY;
    result.tag = ROSTER_REPLY_TAG; result.owner = sCoop.local + 1; result.stage = stage;
    result.hidden = sCoop.hiddenUsable[sCoop.local]
        | (!!(sCoop.roster.knockedOff & (1u << original)) << 1); result.mon = gPlayerParty[stage];
    memcpy(reply, &result, sizeof(result));
    return TRUE;
}

bool8 WorldCoop_RosterReplyValid(u8 battler, const u8 *data, u16 size)
{
    struct CoopRosterReply reply;
    if (!data || size != sizeof(reply) || battler >= MAX_BATTLERS_COUNT || (battler & BIT_SIDE)) return FALSE;
    memcpy(&reply, data, sizeof(reply));
    return reply.tag == ROSTER_REPLY_TAG && reply.owner == battler / 2 + 1
        && reply.stage < PARTY_SIZE && reply.stage / MULTI_PARTY_SIZE == battler / 2
        && reply.stage != gBattlerPartyIndexes[battler] && reply.hidden <= 3
        && MonValid(&reply.mon, FALSE) && GetMonData(&reply.mon, MON_DATA_HP) != 0;
}

bool8 WorldCoop_RosterMirrorValid(const u8 *data, u16 size)
{
    struct CoopRosterMirror packet;
    if (sCoop.state != COOP_BATTLE || sCoop.generation != NativeLink_Generation()
     || !data || size != sizeof(packet) + 4) return FALSE;
    memcpy(&packet, data, sizeof(packet));
    return packet.command == CONTROLLER_EXPUPDATE && packet.tag == WORLD_COOP_ROSTER_MIRROR_TAG
        && packet.owner >= 1 && packet.owner <= 2 && packet.stage < PARTY_SIZE
        && packet.stage / MULTI_PARTY_SIZE == packet.owner - 1
        && packet.stage != gBattlerPartyIndexes[(packet.owner - 1) * 2]
        && packet.generation == sCoop.generation && packet.hidden <= 3
        && !packet.reserved[0] && !packet.reserved[1] && !packet.reserved[2]
        && !data[112] && !data[113] && !data[114] && !data[115]
        && MonValid(&packet.mon, FALSE) && GetMonData(&packet.mon, MON_DATA_HP) != 0;
}

bool8 WorldCoop_ApplyRosterMirror(const u8 *data)
{
    struct CoopRosterMirror packet;
    if (!WorldCoop_RosterMirrorValid(data, sizeof(packet) + 4)) return FALSE;
    memcpy(&packet, data, sizeof(packet));
    if (gActiveBattler != (packet.owner - 1) * 2) return FALSE;
    if (packet.owner == sCoop.local + 1)
    {
        /* The master can never overwrite the owner's private mon. */
        if (memcmp(&gPlayerParty[packet.stage], &packet.mon, sizeof(packet.mon))) return FALSE;
    }
    else
        gPlayerParty[packet.stage] = packet.mon;
    sCoop.hiddenUsable[packet.owner - 1] = packet.hidden & 1;
    if (packet.hidden & 2) gWishFutureKnock.knockedOffMons[B_SIDE_PLAYER] |= 1u << packet.stage;
    else gWishFutureKnock.knockedOffMons[B_SIDE_PLAYER] &= ~(1u << packet.stage);
    return TRUE;
}

bool8 WorldCoop_RosterActionActive(u8 battler)
{
    return sCoop.state == COOP_BATTLE && sCoop.rosterAction && sCoop.rosterBattler == battler;
}

int WorldCoop_BeginRosterAction(u8 battler, u8 choice, const u8 order[3])
{
    u8 packet[16] = { CONTROLLER_EXPUPDATE, WORLD_COOP_ROSTER_REQUEST_TAG, 0, 0 };
    u8 flank, enemy, slot, stage = (choice >> 3) & 7;
    u32 generation = sCoop.generation;
    if (!order || sCoop.rosterAction || !WorldCoop_RosterChoiceValid(battler, choice)) return -1;
    packet[2] = battler / 2 + 1; packet[3] = choice & 7; packet[8] = stage;
    memcpy(packet + 4, &generation, sizeof(generation));
    for (flank = 0; flank < 2; flank++)
    {
        enemy = 1 + flank * 2;
        if (enemy >= gBattlersCount || (gAbsentBattlerFlags & (1u << enemy))) continue;
        slot = gBattlerPartyIndexes[enemy];
        if (slot < PARTY_SIZE)
            packet[9 + slot] |= (gSentPokesToOpponent[flank] >> ((battler / 2) * MULTI_PARTY_SIZE)) & 7;
    }
    packet[15] = (gWishFutureKnock.knockedOffMons[B_SIDE_PLAYER]
                  >> ((battler / 2) * MULTI_PARTY_SIZE)) & 7;
    sCoop.rosterAction = ROSTER_WAIT_OWNER; sCoop.rosterBattler = battler; sCoop.rosterStage = stage;
    memcpy(sCoop.rosterOrder, order, sizeof(sCoop.rosterOrder));
    gActiveBattler = battler;
    PrepareBufferDataTransferLink(B_COMM_TO_CONTROLLER, sizeof(packet), packet);
    MarkBattlerForControllerExec(battler);
    return 0;
}

int WorldCoop_AdvanceRosterAction(u8 battler)
{
    struct CoopRosterReply reply;
    struct CoopRosterMirror packet = {0};
    u8 flank;
    if (!WorldCoop_RosterActionActive(battler)) return -1;
    if (gBattleControllerExecFlags) return 0;
    if (sCoop.rosterAction == ROSTER_WAIT_OWNER)
    {
        if (gBattleBufferB[battler][0] != CONTROLLER_DATATRANSFER
         || (gBattleBufferB[battler][2] | (gBattleBufferB[battler][3] << 8)) != sizeof(reply)
         || !WorldCoop_RosterReplyValid(battler, &gBattleBufferB[battler][4], sizeof(reply))) return -1;
        memcpy(&reply, &gBattleBufferB[battler][4], sizeof(reply));
        if (reply.stage != sCoop.rosterStage) return -1;
        packet.command = CONTROLLER_EXPUPDATE; packet.tag = WORLD_COOP_ROSTER_MIRROR_TAG;
        packet.owner = reply.owner; packet.stage = reply.stage; packet.generation = sCoop.generation;
        packet.hidden = reply.hidden; packet.mon = reply.mon;
        sCoop.rosterAction = ROSTER_WAIT_MIRROR;
        gActiveBattler = battler;
        PrepareBufferDataTransferLink(B_COMM_TO_CONTROLLER, sizeof(packet), (u8 *)&packet);
        MarkBattlerForControllerExec(battler);
        return 0;
    }
    if (sCoop.rosterAction != ROSTER_WAIT_MIRROR) return -1;
    for (flank = 0; flank < 2; flank++)
        gSentPokesToOpponent[flank] &= ~(1u << sCoop.rosterStage);
    gBattleBufferB[battler][0] = CONTROLLER_CHOSENMONRETURNVALUE;
    gBattleBufferB[battler][1] = sCoop.rosterStage;
    memcpy(&gBattleBufferB[battler][2], sCoop.rosterOrder, sizeof(sCoop.rosterOrder));
    sCoop.rosterAction = 0;
    return 1;
}
#endif

void WorldCoop_SetPartyMenuOrder(bool8 inMenuOrder)
{
    sCoop.partyMenuOrder = inMenuOrder;
}

static const u16 sCoopMedicines[] = { ITEM_POTION, ITEM_SUPER_POTION, ITEM_HYPER_POTION, ITEM_MAX_POTION,
    ITEM_ANTIDOTE, ITEM_BURN_HEAL, ITEM_ICE_HEAL, ITEM_AWAKENING, ITEM_PARALYZE_HEAL,
    ITEM_FRESH_WATER, ITEM_SODA_POP, ITEM_LEMONADE, ITEM_MOOMOO_MILK,
    ITEM_FULL_HEAL, ITEM_FULL_RESTORE, ITEM_REVIVE, ITEM_MAX_REVIVE };

static bool8 WorldCoop_RefundMedicine(void)
{
    u8 i;
    for (i = 0; i < ARRAY_COUNT(sCoopMedicines); i++)
    {
        if (sCoop.medicineSpent[i])
        {
            /* The consumed stack or slot is available: no battle operation
             * adds medicine to this private bag. */
            if (!AddBagItem(sCoopMedicines[i], sCoop.medicineSpent[i]))
                return FALSE; /* Leave the remaining ledger intact. */
            sCoop.medicineSpent[i] = 0;
        }
    }
    return TRUE;
}

void WorldCoop_Abort(void)
{
    WorldCoop_RefundMedicine();
    if (sCoop.staged)
    {
        memcpy(gPlayerParty, sCoop.original, sizeof(sCoop.original));
        gPlayerPartyCount = sCoop.originalCount;
    }
    sCoop.state = COOP_IDLE;
    sCoop.fullMenuActive = FALSE;
    sCoop.fullMenuChoice = COOP_ROSTER_EMPTY;
#if COOP_FULL_SIX_READY
    sCoop.rosterAction = 0;
#endif
    sCoop.staged = sCoop.captured = FALSE;
    sCoop.reward = FALSE;
    NativeLink_Abort();
}

static void ExchangeFailed(void)
{
    WorldCoop_Abort();
    WorldActivity_ReturnToField();
}

static bool8 HeaderValid(const struct CoopHeader *header, u8 phase)
{
    return header->magic == COOP_MAGIC && header->version == COOP_VERSION
        && header->phase == phase && header->owner <= 1 && header->count > 0
        && header->count <= MULTI_PARTY_SIZE && header->weather <= WEATHER_ABNORMAL
        && header->environment <= BATTLE_ENVIRONMENT_PLAIN && header->kind <= 2
#if COOP_FULL_SIX_READY
        && header->hiddenUsable <= 1 && !header->reserved[0] && !header->reserved[1] && !header->reserved[2]
#endif
        && (header->owner
            ? (header->kind ? header->trainer > 0 && header->trainer < TRAINERS_COUNT
                && header->enemyCount == gTrainers[header->trainer].partySize
                && header->enemyCount > 0 && header->enemyCount <= PARTY_SIZE
                && (!gTrainers[header->trainer].doubleBattle || header->kind == 2)
                && (header->kind != 2 || header->enemyCount > 1)
              : header->trainer == 0 && header->enemyCount == 1)
            : header->kind == 0 && header->trainer == 0 && header->enemyCount == 0);
}

static void CB2_Exchange(void)
{
    u8 peer, i;
    u8 phase = sCoop.phase;
    if (!NativeLink_IsActive() || !gReceivedRemoteLinkPlayers || ++sCoop.timer > COOP_TIMEOUT)
    {
        ExchangeFailed();
        return;
    }
    if (!sCoop.sent)
    {
        if (!IsLinkTaskFinished())
            return;
        if (phase == 0 || phase == COOP_CONFIRM)
        {
            struct CoopHeader header = sCoop.headers[sCoop.local];
            header.phase = phase;
            if (!SendBlock(BitmaskAllOtherLinkPlayers(), &header, sizeof(header)))
                return;
        }
        else
        {
            memset(&sCoop.outgoing, 0, sizeof(sCoop.outgoing));
            sCoop.outgoing.magic = COOP_MAGIC;
            sCoop.outgoing.version = COOP_VERSION;
            sCoop.outgoing.phase = phase;
            if (phase <= 3)
                sCoop.outgoing.mon = sCoop.selected[phase - 1];
            else if (sCoop.owner && phase - 4 < sCoop.capturedCount)
                sCoop.outgoing.mon = sCoop.capturedEnemies[phase - 4];
            if (!SendBlock(BitmaskAllOtherLinkPlayers(), &sCoop.outgoing, sizeof(sCoop.outgoing)))
                return;
        }
        sCoop.sent = TRUE;
    }
    if ((GetBlockReceivedStatus() & 3) != 3 || !IsLinkTaskFinished())
        return;
    for (peer = 0; peer < 2; peer++)
    {
        if (phase == 0 || phase == COOP_CONFIRM)
        {
            struct CoopHeader header;
            if (GetBlockReceivedSize(peer) != sizeof(header))
            {
                ExchangeFailed();
                return;
            }
            memcpy(&header, gBlockRecvBuffer[peer], sizeof(header));
            if (!HeaderValid(&header, phase))
            {
                ExchangeFailed();
                return;
            }
            if (phase == 0)
                sCoop.headers[peer] = header;
            else
            {
                header.phase = 0;
                if (memcmp(&header, &sCoop.headers[peer], sizeof(header)))
                {
                    ExchangeFailed();
                    return;
                }
            }
        }
        else
        {
            struct CoopMonBlock block;
            bool8 empty = phase <= 3 ? phase > sCoop.headers[peer].count
                : peer != sCoop.ownerPeer || phase - 4 >= sCoop.enemyCount;
            if (GetBlockReceivedSize(peer) != sizeof(block))
            {
                ExchangeFailed();
                return;
            }
            memcpy(&block, gBlockRecvBuffer[peer], sizeof(block));
            if (block.magic != COOP_MAGIC || block.version != COOP_VERSION || block.phase != phase
             || !MonValid(&block.mon, empty)
             || (!empty && GetMonData(&block.mon, MON_DATA_HP) == 0)
             || (empty && GetMonData(&block.mon, MON_DATA_SPECIES) != SPECIES_NONE))
            {
                ExchangeFailed();
                return;
            }
            if (phase <= 3)
                sCoop.allies[peer * MULTI_PARTY_SIZE + phase - 1] = block.mon;
            else if (!empty)
                sCoop.enemies[phase - 4] = block.mon;
        }
    }
    ResetBlockReceivedFlags();
    if (phase == 0)
    {
        if (sCoop.headers[0].owner + sCoop.headers[1].owner != 1
         || sCoop.headers[sCoop.local].owner != sCoop.owner)
        {
            ExchangeFailed();
            return;
        }
        sCoop.ownerPeer = sCoop.headers[0].owner ? 0 : 1;
        sCoop.environment = sCoop.headers[sCoop.ownerPeer].environment;
        sCoop.weather = sCoop.headers[sCoop.ownerPeer].weather;
        sCoop.seed = sCoop.headers[sCoop.ownerPeer].seed;
        sCoop.kind = sCoop.headers[sCoop.ownerPeer].kind;
        sCoop.trainer = sCoop.headers[sCoop.ownerPeer].trainer;
        sCoop.enemyCount = sCoop.headers[sCoop.ownerPeer].enemyCount;
    }
    sCoop.sent = FALSE;
    sCoop.timer = 0;
    sCoop.phase++;
    if (phase != COOP_CONFIRM)
        return;

    /* Only after both sides validated every block can a mixed battle party
     * exist. The untouched private snapshot is the rollback boundary. */
    memcpy(gPlayerParty, sCoop.allies, sizeof(sCoop.allies));
    /* Native multi menus use a six-slot layout, including empty reserves. */
    gPlayerPartyCount = PARTY_SIZE;
    ZeroEnemyPartyMons();
    memcpy(gEnemyParty, sCoop.enemies, sizeof(sCoop.enemies));
    gEnemyPartyCount = sCoop.enemyCount;
    sCoop.staged = TRUE;
    sCoop.captured = FALSE;
    sCoop.generation = NativeLink_Generation();
    sCoop.state = COOP_BATTLE;
#if COOP_FULL_SIX_READY
    sCoop.hiddenUsable[0] = sCoop.headers[0].hiddenUsable;
    sCoop.hiddenUsable[1] = sCoop.headers[1].hiddenUsable;
#endif
    gRngValue = gRecordedBattleRngSeed = sCoop.seed;
    gBattleTypeFlags = BATTLE_TYPE_LINK | BATTLE_TYPE_MULTI | BATTLE_TYPE_DOUBLE;
    if (sCoop.kind)
    {
        gBattleTypeFlags |= BATTLE_TYPE_TRAINER;
        gTrainerBattleOpponent_A = sCoop.trainer;
    }
    if (sCoop.local == 0)
        gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER;
    for (i = 0; i < 2; i++)
        gLinkPlayers[i].id = i * 2;
    if (sCoop.kind)
        BattleSetup_RecordWorldTrainerBattle();
    else
        BattleSetup_RecordWorldWildBattle();
    gMain.savedCallback = WorldActivity_ReturnFromCoopWildBattle;
    SetMainCallback2(CB2_InitBattle);
}

int WorldCoop_StartBattle(bool8 encounterOwner)
{
    u8 i;
    struct CoopHeader *header;
    if (sCoop.state != COOP_IDLE || !NativeLink_IsActive() || !gReceivedRemoteLinkPlayers
     || GetLinkPlayerCount() != 2 || GetMultiplayerId() > 1
     || (encounterOwner && !sCoop.captured))
        return 0;
    /* A failed refund must never be discarded by a new battle. */
    if (!WorldCoop_RefundMedicine()) return 0;
    sCoop.readySent = sCoop.commitSent = sCoop.commitEchoed = sCoop.peerReady = sCoop.peerCommit = FALSE;
    sCoop.catchOwner = sCoop.catchDelivered = sCoop.pendingBall = 0;
    sCoop.pendingMedicine = sCoop.medicineAction = 0;
#if COOP_FULL_SIX_READY
    sCoop.rosterAction = 0;
#endif
    sCoop.fullMenuActive = FALSE;
    sCoop.fullMenuChoice = COOP_ROSTER_EMPTY;
    memset(sCoop.medicineSpent, 0, sizeof(sCoop.medicineSpent));
    sCoop.count = 0;
    memset(sCoop.selected, 0, sizeof(sCoop.selected));
    for (i = 0; i < PARTY_SIZE && sCoop.count < MULTI_PARTY_SIZE; i++)
    {
        struct Pokemon mon = gPlayerParty[i];
        if (!GetMonData(&mon, MON_DATA_SPECIES) || GetMonData(&mon, MON_DATA_IS_EGG)
         || !GetMonData(&mon, MON_DATA_HP))
            continue;
        if (!MonValid(&mon, FALSE))
            return 0;
        sCoop.slots[sCoop.count] = i;
        sCoop.selected[sCoop.count++] = mon;
    }
    if (!sCoop.count)
        return 0;
    memcpy(sCoop.original, gPlayerParty, sizeof(sCoop.original));
    memcpy(sCoop.working, gPlayerParty, sizeof(sCoop.working));
    {
        u8 validMask = 0, staged[MULTI_PARTY_SIZE];
        for (i = 0; i < PARTY_SIZE; i++)
            if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
             && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)) validMask |= 1u << i;
        for (i = 0; i < MULTI_PARTY_SIZE; i++)
            staged[i] = i < sCoop.count ? sCoop.slots[i] : COOP_ROSTER_EMPTY;
        if (!CoopRoster_Init(&sCoop.roster, validMask, staged)) return 0;
    }
    sCoop.originalCount = gPlayerPartyCount;
    sCoop.owner = !!encounterOwner;
    sCoop.local = GetMultiplayerId();
    sCoop.phase = sCoop.timer = 0;
    sCoop.sent = sCoop.staged = sCoop.reward = sCoop.rewardRead = sCoop.partyMenuOrder = FALSE;
    sCoop.payday[0] = sCoop.payday[1] = sCoop.rewardPayday = 0;
    sCoop.moneyMultiplier[0] = sCoop.moneyMultiplier[1] = sCoop.rewardMultiplier = 1;
    memset(sCoop.headers, 0, sizeof(sCoop.headers));
    memset(sCoop.enemies, 0, sizeof(sCoop.enemies));
    memset(sCoop.rewardMask, 0, sizeof(sCoop.rewardMask));
    sCoop.kind = sCoop.enemyCount = sCoop.trainer = 0;
    header = &sCoop.headers[sCoop.local];
    header->magic = COOP_MAGIC;
    header->version = COOP_VERSION;
    header->owner = sCoop.owner;
    header->count = sCoop.count;
    header->environment = sCoop.owner ? sCoop.capturedEnvironment : 0;
    header->weather = sCoop.owner ? sCoop.capturedWeather : 0;
    header->seed = sCoop.owner ? sCoop.capturedSeed : 0;
    header->kind = sCoop.owner ? sCoop.capturedKind : 0;
    header->trainer = sCoop.owner ? sCoop.capturedTrainer : 0;
    header->enemyCount = sCoop.owner ? sCoop.capturedCount : 0;
#if COOP_FULL_SIX_READY
    header->hiddenUsable = WorldCoop_OwnHiddenUsable();
#endif
    sCoop.state = COOP_EXCHANGE;
    ResetBlockReceivedFlags();
    SetMainCallback1(NULL);
    SetMainCallback2(CB2_Exchange);
    return 1;
}

void WorldCoop_InitControllers(void)
{
    u8 i;
    memset(sCoop.publicValid, 0, sizeof(sCoop.publicValid));
    gBattleScripting.multiplayerId = sCoop.local;
    gBattlersCount = MAX_BATTLERS_COUNT;
    gAbsentBattlerFlags = WorldCoop_HasSecondOpponent() ? 0 : 1 << B_POSITION_OPPONENT_RIGHT;
    for (i = 0; i < MAX_BATTLERS_COUNT; i++)
    {
        gBattlerPositions[i] = i;
        gBattlerPartyIndexes[i] = (i & BIT_FLANK) ? MULTI_PARTY_SIZE : 0;
        if (i == B_POSITION_OPPONENT_RIGHT)
            gBattlerPartyIndexes[i] = WorldCoop_HasSecondOpponent() ? 1 : 0;
        BufferBattlePartyCurrentOrderBySide(i, (i & BIT_FLANK) != 0);
    }
    gBattlerControllerFuncs[0] = sCoop.local == 0 ? SetControllerToPlayer : SetControllerToLinkPartner;
    gBattlerControllerFuncs[2] = sCoop.local == 1 ? SetControllerToPlayer : SetControllerToLinkPartner;
    gBattlerControllerFuncs[1] = sCoop.local == 0 ? SetControllerToOpponent : SetControllerToLinkOpponent;
    gBattlerControllerFuncs[3] = sCoop.local == 0 ? SetControllerToOpponent : SetControllerToLinkOpponent;
    if (sCoop.local == 0)
        gBattleMainFunc = BeginBattleIntro;
}

/* Only selected active-mon replies enter this display projection. It does not
 * initialize gBattleMons, execute scripts, or inspect the partner's reserves. */
void WorldCoop_ObserveMonData(u8 battler, u8 partySlot, const struct BattlePokemon *mon)
{
    struct WorldCoopPublicMon *view;
    if (sCoop.state != COOP_BATTLE || sCoop.generation != NativeLink_Generation()
     || battler >= MAX_BATTLERS_COUNT || (gAbsentBattlerFlags & (1u << battler))
     || mon == NULL || !mon->species || mon->species >= NUM_SPECIES
     || !mon->level || mon->level > MAX_LEVEL || partySlot >= PARTY_SIZE)
        return;
    if ((battler & BIT_SIDE) ? partySlot >= sCoop.enemyCount : partySlot / MULTI_PARTY_SIZE != battler / 2)
        return;
    view = &sCoop.publicMons[battler];
    memset(view, 0, sizeof(*view));
    view->species = mon->species;
    view->level = mon->level;
    if (!(battler & BIT_SIDE))
    {
        view->hp = mon->hp;
        view->maxHP = mon->maxHP;
        view->status = mon->status1;
    }
    sCoop.publicSlots[battler] = partySlot;
    sCoop.publicValid[battler] = TRUE;
}

void WorldCoop_ObserveController(u8 battler, const u8 *data)
{
    struct WorldCoopPublicMon *view;
    u8 slot;
    if (sCoop.state != COOP_BATTLE || sCoop.generation != NativeLink_Generation()
     || battler >= MAX_BATTLERS_COUNT || (battler & BIT_SIDE)
     || !sCoop.publicValid[battler] || data == NULL
     || data[0] != CONTROLLER_SETMONDATA)
        return;
    slot = sCoop.publicSlots[battler];
    if (data[2] ? !(data[2] & (1u << slot)) : gBattlerPartyIndexes[battler] != slot)
        return;
    view = &sCoop.publicMons[battler];
    switch (data[1])
    {
    case REQUEST_HP_BATTLE:
        view->hp = data[3] | (data[4] << 8);
        break;
    case REQUEST_STATUS_BATTLE:
        view->status = data[3] | ((u32)data[4] << 8) | ((u32)data[5] << 16) | ((u32)data[6] << 24);
        break;
    }
}

bool8 WorldCoop_GetPublicMon(u8 battler, struct WorldCoopPublicMon *mon)
{
    if (sCoop.state != COOP_BATTLE || sCoop.generation != NativeLink_Generation()
     || battler >= MAX_BATTLERS_COUNT || !sCoop.publicValid[battler]
     || (gAbsentBattlerFlags & (1u << battler)) || mon == NULL
     || sCoop.publicSlots[battler] != gBattlerPartyIndexes[battler])
        return FALSE;
    *mon = sCoop.publicMons[battler];
    return TRUE;
}

bool8 WorldCoop_CanSelectBattleItem(u16 item)
{
    return WorldCoop_CanSelectBall(item)
        || (sCoop.state == COOP_BATTLE && WorldCoop_IsMedicine(item));
}

void WorldCoop_SetMenuConfusion(bool8 confused)
{
    sCoop.menuConfused = !!confused;
    sCoop.pendingMedicine = 0;
    sCoop.medicineTarget = PARTY_SIZE;
}

bool8 WorldCoop_SelectMedicineTarget(u16 item, u8 slot, struct Pokemon *mon)
{
    u8 battler = gBattlerInMenuId;
    u16 heal; u32 status; bool8 cureConfusion, confused;
    if (sCoop.state != COOP_BATTLE || !WorldCoop_IsMedicine(item)
     || battler != sCoop.local * 2 || slot >= PARTY_SIZE
     || slot / MULTI_PARTY_SIZE != sCoop.local || !mon || !CheckBagHasItem(item, 1)) return FALSE;
    confused = slot == gBattlerPartyIndexes[battler] && sCoop.menuConfused;
    if (!WorldCoop_MedicineEffect(item, GetMonData(mon, MON_DATA_HP),
         GetMonData(mon, MON_DATA_MAX_HP), GetMonData(mon, MON_DATA_STATUS), confused,
         &heal, &status, &cureConfusion)) return FALSE;
    sCoop.pendingMedicine = item;
    sCoop.medicineTarget = slot;
    return TRUE;
}

bool8 WorldCoop_CanUseMedicine(u16 item)
{
    u8 slot = sCoop.medicineTarget;
    if (slot >= PARTY_SIZE || sCoop.pendingMedicine != item) return FALSE;
    return WorldCoop_SelectMedicineTarget(item, slot, &gPlayerParty[slot]);
}

bool8 WorldCoop_ItemReplyValid(u16 reply)
{
    if (sCoop.state != COOP_BATTLE) return FALSE;
    if (!reply) return TRUE;
    if ((reply & 0xF800) == WORLD_COOP_MEDICINE_REPLY)
        return ((reply >> 8) & 7) < PARTY_SIZE && WorldCoop_IsMedicine(reply & 0xFF);
    return WorldCoop_BallReplyValid(reply);
}

u16 WorldCoop_SelectBattleItem(u16 item)
{
    if (WorldCoop_IsMedicine(item))
    {
        if (!WorldCoop_CanUseMedicine(item)) return 0;
        return WORLD_COOP_MEDICINE_REPLY | (sCoop.medicineTarget << 8) | item;
    }
    sCoop.pendingMedicine = 0;
    sCoop.medicineTarget = PARTY_SIZE;
    return WorldCoop_SelectBall(item);
}

bool8 WorldCoop_MedicinePacketValid(const u8 *data, u16 size)
{
    u32 generation, status, newStatus;
    u16 hp, maxHP, heal; bool8 cureConfusion;
    if (sCoop.state != COOP_BATTLE || sCoop.generation != NativeLink_Generation()
     || size != 20 || data[0] != CONTROLLER_EXPUPDATE || data[1] != WORLD_COOP_MEDICINE_TAG
     || data[2] < 1 || data[2] > 2 || !WorldCoop_IsMedicine(data[3])
     || data[17] >= PARTY_SIZE || data[17] / MULTI_PARTY_SIZE != data[2] - 1) return FALSE;
    memcpy(&generation, data + 4, sizeof(generation));
    hp = data[8] | (data[9] << 8); maxHP = data[10] | (data[11] << 8);
    status = (u32)data[12] | ((u32)data[13] << 8) | ((u32)data[14] << 16) | ((u32)data[15] << 24);
    return generation == sCoop.generation && !(status & ~0xFFFu)
        && data[16] <= 1 && !data[18] && !data[19]
        && WorldCoop_MedicineEffect(data[3], hp, maxHP, status, data[16], &heal, &newStatus, &cureConfusion);
}

bool8 WorldCoop_ConsumeMedicine(const u8 *data)
{
    u16 hp, maxHP, item;
    u32 status;
    u8 i, slot;
    bool8 confused;
    struct Pokemon *mon;
    if (!WorldCoop_MedicinePacketValid(data, 20) || data[2] != sCoop.local + 1
     || gActiveBattler != sCoop.local * 2) return FALSE;
    item = data[3]; slot = data[17];
    if (slot >= PARTY_SIZE || slot / MULTI_PARTY_SIZE != sCoop.local
     || sCoop.pendingMedicine != item || sCoop.medicineTarget != slot) return FALSE;
    mon = &gPlayerParty[slot];
    hp = data[8] | (data[9] << 8); maxHP = data[10] | (data[11] << 8);
    status = (u32)data[12] | ((u32)data[13] << 8) | ((u32)data[14] << 16) | ((u32)data[15] << 24);
    confused = slot == gBattlerPartyIndexes[gActiveBattler] && sCoop.menuConfused;
    if (GetMonData(mon, MON_DATA_HP) != hp || GetMonData(mon, MON_DATA_MAX_HP) != maxHP
     || (GetMonData(mon, MON_DATA_STATUS) & STATUS1_ANY) != (status & STATUS1_ANY)
     || confused != data[16]) return FALSE;
    for (i = 0; i < ARRAY_COUNT(sCoopMedicines) && sCoopMedicines[i] != item; i++);
    if (i == ARRAY_COUNT(sCoopMedicines) || sCoop.medicineSpent[i] == 0xFFFF
     || !RemoveBagItem(item, 1)) return FALSE;
    sCoop.medicineSpent[i]++;
    sCoop.pendingMedicine = 0;
    return TRUE;
}

enum { MEDICINE_WAIT_MON = 1, MEDICINE_WAIT_OWNER, MEDICINE_WAIT_HP, MEDICINE_WAIT_STATUS };

static bool8 WorldCoop_SendMedicineEvent(u8 battler, u16 hp, u16 maxHP, u32 status, bool8 confused)
{
    u8 packet[18] = { CONTROLLER_EXPUPDATE, WORLD_COOP_MEDICINE_TAG, 0, 0 };
    u32 generation = sCoop.generation;
    if ((status & ~0xFFFu) || !WorldCoop_MedicineEffect(sCoop.medicineItem, hp, maxHP, status,
         confused, &sCoop.medicineHeal, &sCoop.medicineStatusAfter, &sCoop.medicineClearConfusion)) return FALSE;
    sCoop.medicineStatusBefore = status;
    sCoop.medicineHPAfter = hp + sCoop.medicineHeal;
    packet[2] = battler / 2 + 1; packet[3] = sCoop.medicineItem;
    memcpy(packet + 4, &generation, sizeof(generation));
    packet[8] = hp; packet[9] = hp >> 8; packet[10] = maxHP; packet[11] = maxHP >> 8;
    packet[12] = status; packet[13] = status >> 8; packet[14] = status >> 16; packet[15] = status >> 24;
    packet[16] = confused; packet[17] = sCoop.medicineTarget;
    sCoop.medicineAction = MEDICINE_WAIT_OWNER;
    gActiveBattler = battler;
    PrepareBufferDataTransferLink(B_COMM_TO_CONTROLLER, sizeof(packet), packet);
    MarkBattlerForControllerExec(battler);
    return TRUE;
}

bool8 WorldCoop_MedicineActionActive(u8 battler)
{
    return sCoop.state == COOP_BATTLE && sCoop.medicineAction && sCoop.medicineBattler == battler;
}

u8 WorldCoop_MedicineTarget(void) { return sCoop.medicineTarget; }

int WorldCoop_BeginMedicineAction(u8 battler, u16 reply)
{
    u8 target = (reply >> 8) & 7;
    if (sCoop.state != COOP_BATTLE || sCoop.medicineAction || (battler & BIT_SIDE)
     || battler >= MAX_BATTLERS_COUNT || !WorldCoop_ItemReplyValid(reply)
     || (reply & 0xF800) != WORLD_COOP_MEDICINE_REPLY
     || target / MULTI_PARTY_SIZE != battler / 2) return -1;
    sCoop.medicineBattler = battler; sCoop.medicineTarget = target; sCoop.medicineItem = reply & 0xFF;
    if (target == gBattlerPartyIndexes[battler])
        return WorldCoop_SendMedicineEvent(battler, gBattleMons[battler].hp, gBattleMons[battler].maxHP,
            gBattleMons[battler].status1, !!(gBattleMons[battler].status2 & STATUS2_CONFUSION)) ? 0 : -1;
    /* Query only the selected staged slot from its owner. The reply is
     * authenticated and validated by the existing GETMONDATA boundary. */
    sCoop.medicineAction = MEDICINE_WAIT_MON;
    gActiveBattler = battler;
    BtlController_EmitGetMonData(B_COMM_TO_CONTROLLER, REQUEST_ALL_BATTLE, 1u << target);
    MarkBattlerForControllerExec(battler);
    return 0;
}

int WorldCoop_AdvanceMedicineAction(u8 battler)
{
    if (!WorldCoop_MedicineActionActive(battler)) return -1;
    if (gBattleControllerExecFlags) return 0;
    if (sCoop.medicineAction == MEDICINE_WAIT_MON)
    {
        struct BattlePokemon mon;
        if (gBattleBufferB[battler][0] != CONTROLLER_DATATRANSFER
         || (gBattleBufferB[battler][2] | (gBattleBufferB[battler][3] << 8)) != sizeof(mon)) return -1;
        memcpy(&mon, &gBattleBufferB[battler][4], sizeof(mon));
        return WorldCoop_SendMedicineEvent(battler, mon.hp, mon.maxHP, mon.status1, FALSE) ? 0 : -1;
    }
    if (sCoop.medicineAction == MEDICINE_WAIT_OWNER)
    {
        if (gBattleBufferB[battler][0] != CONTROLLER_TWORETURNVALUES
         || gBattleBufferB[battler][1] != 1 || gBattleBufferB[battler][2] || gBattleBufferB[battler][3]) return -1;
        gLastUsedItem = sCoop.medicineItem;
        gBattleMoveDamage = -(s32)sCoop.medicineHeal;
        if (sCoop.medicineTarget == gBattlerPartyIndexes[battler])
        {
            sCoop.medicineAction = 0;
            if (sCoop.medicineClearConfusion) gBattleMons[battler].status2 &= ~STATUS2_CONFUSION;
            if (sCoop.medicineStatusAfter != sCoop.medicineStatusBefore)
            {
                gBattleMons[battler].status1 = sCoop.medicineStatusAfter;
                if ((sCoop.medicineStatusBefore & STATUS1_SLEEP) && !(sCoop.medicineStatusAfter & STATUS1_SLEEP))
                    gBattleMons[battler].status2 &= ~STATUS2_NIGHTMARE;
                gActiveBattler = battler;
                BtlController_EmitSetMonData(B_COMM_TO_CONTROLLER, REQUEST_STATUS_BATTLE, 0,
                                             sizeof(gBattleMons[battler].status1), &gBattleMons[battler].status1);
                MarkBattlerForControllerExec(battler);
            }
            return sCoop.medicineHeal ? 1 : 2;
        }
        sCoop.medicineAction = MEDICINE_WAIT_HP;
        if (sCoop.medicineHeal)
        {
            gActiveBattler = battler;
            BtlController_EmitSetMonData(B_COMM_TO_CONTROLLER, REQUEST_HP_BATTLE, 1u << sCoop.medicineTarget,
                                         sizeof(sCoop.medicineHPAfter), &sCoop.medicineHPAfter);
            MarkBattlerForControllerExec(battler);
            return 0;
        }
    }
    if (sCoop.medicineAction == MEDICINE_WAIT_HP)
    {
        sCoop.medicineAction = MEDICINE_WAIT_STATUS;
        if (sCoop.medicineStatusAfter != sCoop.medicineStatusBefore)
        {
            gActiveBattler = battler;
            BtlController_EmitSetMonData(B_COMM_TO_CONTROLLER, REQUEST_STATUS_BATTLE, 1u << sCoop.medicineTarget,
                                         sizeof(sCoop.medicineStatusAfter), &sCoop.medicineStatusAfter);
            MarkBattlerForControllerExec(battler);
            return 0;
        }
    }
    if (sCoop.medicineAction == MEDICINE_WAIT_STATUS)
    {
        sCoop.medicineAction = 0;
        return 3;
    }
    return -1;
}

/* The owner supplies only private, ball-specific context. No partner bag or
 * dex is consulted by the master when it executes the ordinary capture odds. */
bool8 WorldCoop_BallReplyValid(u16 reply)
{
    u16 item = reply & 0xFF;
    return sCoop.state == COOP_BATTLE && !sCoop.kind
        && (reply == 0 || (item >= ITEM_MASTER_BALL && item <= LAST_BALL
            && item != ITEM_SAFARI_BALL && !(reply & ~0x3FF)
            && (!(reply & 0x100) || item == ITEM_REPEAT_BALL)
            && (!(reply & 0x200) || item == ITEM_DIVE_BALL)));
}

u16 WorldCoop_SelectBall(u16 item)
{
    u16 reply = item;
    if (!item)
        return 0;
    if (!WorldCoop_CanSelectBall(item) || !CheckBagHasItem(item, 1))
        return 0;
    sCoop.pendingBall = item;
    if (item == ITEM_REPEAT_BALL && GetSetPokedexFlag(SpeciesToNationalPokedexNum(
            GetMonData(&sCoop.enemies[0], MON_DATA_SPECIES)), FLAG_GET_CAUGHT))
        reply |= 0x100;
    if (item == ITEM_DIVE_BALL && sCoop.environment == BATTLE_ENVIRONMENT_UNDERWATER)
        reply |= 0x200;
    return reply;
}

void WorldCoop_EmitBallUse(u16 reply)
{
    u8 packet[9] = { CONTROLLER_EXPUPDATE, COOP_BALL_USE, 0, 0 };
    u32 generation = sCoop.generation;
    packet[2] = gBattlerAttacker / 2 + 1;
    packet[3] = reply & 0xFF;
    memcpy(packet + 4, &generation, sizeof(generation));
    gActiveBattler = gBattlerAttacker;
    PrepareBufferDataTransferLink(B_COMM_TO_CONTROLLER, sizeof(packet), packet);
    MarkBattlerForControllerExec(gActiveBattler);
}

bool8 WorldCoop_EmitCatch(void)
{
    struct CoopCatchPacket packet = {0};
    u8 battler;
    if (sCoop.state != COOP_BATTLE || sCoop.kind || sCoop.catchOwner
     || gBattlerAttacker > 2 || (gBattlerAttacker & BIT_SIDE))
        return FALSE;
    packet.command = CONTROLLER_EXPUPDATE;
    packet.tag = COOP_CATCH;
    packet.owner = gBattlerAttacker / 2 + 1;
    packet.generation = sCoop.generation;
    packet.mon = gEnemyParty[0];
    SetMonData(&packet.mon, MON_DATA_HP, &gBattleMons[B_POSITION_OPPONENT_LEFT].hp);
    SetMonData(&packet.mon, MON_DATA_STATUS, &gBattleMons[B_POSITION_OPPONENT_LEFT].status1);
    SetMonData(&packet.mon, MON_DATA_POKEBALL, &gLastUsedItem);
    for (battler = 0; battler <= 2; battler += 2)
    {
        gActiveBattler = battler;
        PrepareBufferDataTransferLink(B_COMM_TO_CONTROLLER, sizeof(packet), (u8 *)&packet);
        MarkBattlerForControllerExec(battler);
    }
    return TRUE;
}

bool8 WorldCoop_CatchPacketValid(const u8 *data, u16 size)
{
    struct CoopCatchPacket packet;
    struct Pokemon *base = &sCoop.enemies[0];
    u32 generation;
    if (sCoop.state != COOP_BATTLE || sCoop.kind || sCoop.enemyCount != 1
     || sCoop.generation != NativeLink_Generation() || size < 12
     || data[0] != CONTROLLER_EXPUPDATE || data[2] < 1 || data[2] > 2)
        return FALSE;
    memcpy(&generation, data + 4, sizeof(generation));
    if (generation != sCoop.generation)
        return FALSE;
    if (data[1] == COOP_BALL_USE)
        return size == 12 && data[3] >= ITEM_MASTER_BALL && data[3] <= LAST_BALL
            && data[3] != ITEM_SAFARI_BALL && !data[8] && !data[9] && !data[10] && !data[11];
    if (data[1] != COOP_CATCH || size != sizeof(packet) + 4 || data[3]
     || data[108] || data[109] || data[110] || data[111])
        return FALSE;
    memcpy(&packet, data, sizeof(packet));
    return MonValid(&packet.mon, FALSE) && packet.mon.hp
        && packet.mon.box.personality == base->box.personality
        && packet.mon.box.otId == base->box.otId
        && GetMonData(&packet.mon, MON_DATA_SPECIES) == GetMonData(base, MON_DATA_SPECIES)
        && packet.mon.level == base->level && packet.mon.maxHP == base->maxHP
        && packet.mon.attack == base->attack && packet.mon.defense == base->defense
        && packet.mon.speed == base->speed && packet.mon.spAttack == base->spAttack
        && packet.mon.spDefense == base->spDefense
        && GetMonData(&packet.mon, MON_DATA_POKEBALL) >= ITEM_MASTER_BALL
        && GetMonData(&packet.mon, MON_DATA_POKEBALL) != ITEM_SAFARI_BALL;
}

void WorldCoop_RecordCatchEvent(const u8 *data)
{
    if (data[1] == COOP_BALL_USE)
    {
        /* Only the owning player controller reaches here. The link-partner
         * mirror only ACKs, so no other human's bag is ever touched. */
        if (data[2] != sCoop.local + 1 || gActiveBattler != sCoop.local * 2
         || sCoop.pendingBall != data[3] || !RemoveBagItem(data[3], 1))
            NativeLink_Abort();
        sCoop.pendingBall = 0;
    }
    else
    {
        struct CoopCatchPacket packet;
        memcpy(&packet, data, sizeof(packet));
        if (sCoop.catchOwner && (sCoop.catchOwner != packet.owner
            || memcmp(&sCoop.caughtMon, &packet.mon, sizeof(packet.mon))))
        {
            NativeLink_Abort();
            return;
        }
        sCoop.catchOwner = packet.owner;
        sCoop.caughtMon = packet.mon;
    }
}

bool8 WorldCoop_BeginCatchRewards(void)
{
    u32 oldOtId;
    unsigned i;
    if (sCoop.state != COOP_REWARDS || sCoop.catchOwner != sCoop.local + 1
     || sCoop.catchDelivered || gBattleOutcome != B_OUTCOME_CAUGHT
     || (sCoop.originalCount == PARTY_SIZE && IsPokemonStorageFull()))
        return FALSE;
    sCoop.catchDelivered = TRUE;
    gEnemyParty[0] = sCoop.caughtMon;
    /* Stock GiveMonToPlayer changes OT_ID without re-encrypting: ordinary
     * wild mons already carry the local trainer's ID. The shared snapshot
     * instead carries the encounter owner's ID. Rekey only this private copy
     * before the stock dex/nickname/give scripts, preserving personality,
     * substructure order and checksum. Never alter the committed snapshot. */
    oldOtId = gEnemyParty[0].box.otId;
    SetMonData(&gEnemyParty[0], MON_DATA_OT_ID, gSaveBlock2Ptr->playerTrainerId);
    for (i = 0; i < ARRAY_COUNT(gEnemyParty[0].box.secure.raw); i++)
        gEnemyParty[0].box.secure.raw[i] ^= oldOtId ^ gEnemyParty[0].box.otId;
    gBattlerAttacker = 0;
    gBattlerTarget = 1;
    gBattlerPartyIndexes[1] = 0;
    gLastUsedItem = GetMonData(&sCoop.caughtMon, MON_DATA_POKEBALL);
    memset(&gBattleMons[1], 0, sizeof(gBattleMons[1]));
    gBattleMons[1].species = GetMonData(&sCoop.caughtMon, MON_DATA_SPECIES);
    gBattleMons[1].level = sCoop.caughtMon.level;
    gBattleMons[1].hp = sCoop.caughtMon.hp;
    gBattleMons[1].maxHP = sCoop.caughtMon.maxHP;
    gBattleMons[1].status1 = sCoop.caughtMon.status;
    GetMonData(&sCoop.caughtMon, MON_DATA_NICKNAME, gBattleMons[1].nickname);
    GetMonData(&sCoop.caughtMon, MON_DATA_OT_NAME, gBattleMons[1].otName);
    gBattleMons[1].otId = gEnemyParty[0].box.otId;
    gBattleMons[1].personality = sCoop.caughtMon.box.personality;
    return TRUE;
}

void WorldCoop_EmitDefeat(void)
{
    u8 packet[9] = { CONTROLLER_EXPUPDATE, 0, 0, 0, 0, 0, 0, 0, 1 };
    u8 slot = gBattlerPartyIndexes[gBattlerFainted];
    u16 species = GetMonData(&sCoop.enemies[slot], MON_DATA_SPECIES);
    u8 battler;
    packet[1] = slot;
    packet[2] = species;
    packet[3] = species >> 8;
    packet[4] = GetMonData(&sCoop.enemies[slot], MON_DATA_LEVEL);
    packet[5] = gSentPokesToOpponent[(gBattlerFainted & BIT_FLANK) >> 1];
    for (battler = 0; battler <= 2; battler += 2)
    {
        gActiveBattler = battler;
        packet[6] = sCoop.payday[battler / 2];
        packet[7] = sCoop.payday[battler / 2] >> 8;
        packet[8] = sCoop.moneyMultiplier[battler / 2];
        PrepareBufferDataTransferLink(B_COMM_TO_CONTROLLER, sizeof(packet), packet);
        MarkBattlerForControllerExec(battler);
    }
}

void WorldCoop_AddPayday(u8 battler, u16 amount)
{
    u8 owner = battler / 2;
    if (WorldCoop_IsBattle() && !(battler & BIT_SIDE) && owner < 2)
    {
        u32 total = sCoop.payday[owner] + amount;
        sCoop.payday[owner] = total > 0xFFFF ? 0xFFFF : total;
    }
}

void WorldCoop_DoublePrize(u8 battler)
{
    if (WorldCoop_IsBattle() && !(battler & BIT_SIDE) && battler < MAX_BATTLERS_COUNT)
        sCoop.moneyMultiplier[battler / 2] = 2;
}

bool8 WorldCoop_RewardPacketValid(const u8 *data, u16 size)
{
    return size == 12 && data[0] == CONTROLLER_EXPUPDATE && data[1] < sCoop.enemyCount
        && (data[2] | (data[3] << 8)) == GetMonData(&sCoop.enemies[data[1]], MON_DATA_SPECIES)
        && data[4] == GetMonData(&sCoop.enemies[data[1]], MON_DATA_LEVEL)
        && (data[5] & ~0x3F) == 0 && (data[8] == 1 || data[8] == 2)
        && data[9] == 0 && data[10] == 0 && data[11] == 0;
}

void WorldCoop_RecordDefeat(const u8 *data)
{
    u8 mask = data[5] >> (sCoop.local * MULTI_PARTY_SIZE);
    if (!WorldCoop_RewardPacketValid(data, 12) || (sCoop.reward & (1 << data[1])))
        return;
    sCoop.rewardMask[data[1]] = CoopRoster_RewardMask(&sCoop.roster, data[1], mask & 7);
    sCoop.reward |= 1 << data[1];
    sCoop.rewardPayday = data[6] | (data[7] << 8);
    sCoop.rewardMultiplier = data[8];
}

static bool8 BuildPrivateParty(struct Pokemon merged[PARTY_SIZE])
{
    u8 i;
    bool8 valid = TRUE;
    memcpy(merged, sCoop.working, sizeof(sCoop.working));
    for (i = 0; i < sCoop.count; i++)
    {
        struct Pokemon mon = gPlayerParty[sCoop.local * MULTI_PARTY_SIZE + i];
        struct Pokemon *original = &sCoop.original[sCoop.slots[i]];
        if (!MonValid(&mon, FALSE) || mon.box.personality != original->box.personality
         || mon.box.otId != original->box.otId
         || GetMonData(&mon, MON_DATA_SPECIES) != GetMonData(original, MON_DATA_SPECIES))
        {
            valid = FALSE;
            break;
        }
        merged[sCoop.slots[i]] = mon;
    }
    return valid;
}

/* Completion records share SendBlock's authenticated, session-scoped channel.
 * READY is emitted only after the local fade, ACK drain and private validation.
 * COMMIT proves its sender has also received the partner's READY. */
int WorldCoop_ReceiveCompletion(const u8 *data, u16 size, u8 sender)
{
    struct CoopCompletion packet;
    if (size < 2 || (data[0] | (data[1] << 8)) != COOP_MAGIC)
        return 0;
    if (sCoop.state != COOP_BATTLE || size != sizeof(packet) || sender > 1)
        return -1;
    memcpy(&packet, data, sizeof(packet));
    if (packet.version != COOP_VERSION || packet.generation != sCoop.generation || NativeLink_Generation() != sCoop.generation
     || packet.seed != sCoop.seed || packet.sender != sender || packet.catchOwner != sCoop.catchOwner
     || ((packet.outcome == B_OUTCOME_CAUGHT) != (packet.catchOwner != 0))
     || (packet.catchOwner && (sCoop.kind || sCoop.enemyCount != 1 || packet.reward))
     || packet.outcome == 0 || packet.outcome > B_OUTCOME_MON_TELEPORTED
     || (packet.reward & ~((1 << sCoop.enemyCount) - 1))
     || (packet.phase != COOP_READY && packet.phase != COOP_COMMIT))
        return -1;
    if (sender == sCoop.local)
    {
        if (!sCoop.readySent || packet.outcome != gBattleOutcome || packet.reward != sCoop.reward)
            return -1;
        if (packet.phase == COOP_COMMIT)
        {
            if (!sCoop.commitSent || !sCoop.peerReady)
                return -1;
            sCoop.commitEchoed = TRUE;
        }
        return 1;
    }
    if (packet.phase == COOP_READY)
    {
        if (sCoop.peerReady && (sCoop.peerOutcome != packet.outcome || sCoop.peerReward != packet.reward))
            return -1;
        sCoop.peerReady = TRUE;
        sCoop.peerOutcome = packet.outcome;
        sCoop.peerReward = packet.reward;
    }
    else
    {
        if (!sCoop.peerReady || !sCoop.readySent
         || packet.outcome != sCoop.peerOutcome || packet.reward != sCoop.peerReward)
            return -1;
        sCoop.peerCommit = TRUE;
    }
    return 1;
}

bool8 WorldCoop_CompletionCommitted(void)
{
    /* Catch delivery still requires the partner's matching COMMIT in this
     * generation. For ordinary outcomes retain the bilateral READY boundary
     * across normal peer closure; active wire drain is checked separately. */
    return sCoop.state == COOP_BATTLE && sCoop.commitSent && sCoop.peerReady
        && (!sCoop.catchOwner || (sCoop.peerCommit && sCoop.generation == NativeLink_Generation()));
}

bool8 WorldCoop_ReadyForPrivateRewards(void)
{
    struct Pokemon merged[PARTY_SIZE];
    struct CoopCompletion packet = {0};
    if (sCoop.state != COOP_BATTLE)
        return FALSE;
    if (WorldCoop_CompletionCommitted()
     && (!NativeLink_IsActive() || (sCoop.generation == NativeLink_Generation()
                                  && sCoop.commitEchoed && sCoop.peerCommit)))
        return TRUE;
    if (!NativeLink_IsActive() || NativeLink_Generation() != sCoop.generation
     || ++sCoop.timer > COOP_TIMEOUT || !BuildPrivateParty(merged)
     || ((gBattleOutcome == B_OUTCOME_CAUGHT) != (sCoop.catchOwner != 0))
     || (sCoop.catchOwner && (sCoop.kind || sCoop.reward))
     || (sCoop.peerReady && (sCoop.peerOutcome != gBattleOutcome || sCoop.peerReward != sCoop.reward)))
    {
        /* A rejected completion is not normal peer closure. Invalidate the
         * queued commit before Abort resets the transport, or a later poll
         * could mistake our own abort for the durable close fallback. */
        sCoop.commitSent = sCoop.commitEchoed = FALSE;
        NativeLink_Abort();
        return FALSE;
    }
    if (!IsLinkTaskFinished())
        return FALSE;
    packet.magic = COOP_MAGIC;
    packet.version = COOP_VERSION;
    packet.generation = sCoop.generation;
    packet.seed = sCoop.seed;
    packet.sender = sCoop.local;
    packet.outcome = gBattleOutcome;
    packet.reward = sCoop.reward;
    packet.catchOwner = sCoop.catchOwner;
    packet.phase = sCoop.readySent ? COOP_COMMIT : COOP_READY;
    if ((!sCoop.readySent || (sCoop.peerReady && !sCoop.commitSent))
     && SendBlock(BitmaskAllOtherLinkPlayers(), &packet, sizeof(packet)))
    {
        if (!sCoop.readySent)
            sCoop.readySent = TRUE;
        else
            sCoop.commitSent = TRUE;
    }
    /* SendBlock only queues our COMMIT. Do not let the same call close an
     * active session before its authenticated echo has actually drained. */
    return WorldCoop_CompletionCommitted() && sCoop.commitEchoed && sCoop.peerCommit;
}

/* The slave never runs the battle engine, so its gBattleMons cannot be used
 * as reward/HUD state. Reconstruct a normal, untransformed private active mon. */
static void LoadPrivateBattleMon(void)
{
    struct Pokemon *mon = &gPlayerParty[gBattlerPartyIndexes[0]];
    struct BattlePokemon *battle = &gBattleMons[0];
    u8 i;
    memset(battle, 0, sizeof(*battle));
    battle->species = GetMonData(mon, MON_DATA_SPECIES);
    battle->item = GetMonData(mon, MON_DATA_HELD_ITEM);
    battle->level = GetMonData(mon, MON_DATA_LEVEL);
    battle->hp = GetMonData(mon, MON_DATA_HP);
    battle->maxHP = GetMonData(mon, MON_DATA_MAX_HP);
    battle->attack = GetMonData(mon, MON_DATA_ATK);
    battle->defense = GetMonData(mon, MON_DATA_DEF);
    battle->speed = GetMonData(mon, MON_DATA_SPEED);
    battle->spAttack = GetMonData(mon, MON_DATA_SPATK);
    battle->spDefense = GetMonData(mon, MON_DATA_SPDEF);
    battle->experience = GetMonData(mon, MON_DATA_EXP);
    battle->personality = GetMonData(mon, MON_DATA_PERSONALITY);
    battle->otId = GetMonData(mon, MON_DATA_OT_ID);
    battle->status1 = GetMonData(mon, MON_DATA_STATUS);
    battle->friendship = GetMonData(mon, MON_DATA_FRIENDSHIP);
    battle->ppBonuses = GetMonData(mon, MON_DATA_PP_BONUSES);
    battle->abilityNum = GetMonData(mon, MON_DATA_ABILITY_NUM);
    battle->ability = GetMonAbility(mon);
    battle->hpIV = GetMonData(mon, MON_DATA_HP_IV);
    battle->attackIV = GetMonData(mon, MON_DATA_ATK_IV);
    battle->defenseIV = GetMonData(mon, MON_DATA_DEF_IV);
    battle->speedIV = GetMonData(mon, MON_DATA_SPEED_IV);
    battle->spAttackIV = GetMonData(mon, MON_DATA_SPATK_IV);
    battle->spDefenseIV = GetMonData(mon, MON_DATA_SPDEF_IV);
    battle->types[0] = gSpeciesInfo[battle->species].types[0];
    battle->types[1] = gSpeciesInfo[battle->species].types[1];
    GetMonData(mon, MON_DATA_NICKNAME, battle->nickname);
    GetMonData(mon, MON_DATA_OT_NAME, battle->otName);
    for (i = 0; i < MAX_MON_MOVES; i++)
    {
        battle->moves[i] = GetMonData(mon, MON_DATA_MOVE1 + i);
        battle->pp[i] = GetMonData(mon, MON_DATA_PP1 + i);
    }
    for (i = 0; i < NUM_BATTLE_STATS; i++)
        battle->statStages[i] = DEFAULT_STAT_STAGE;
}

bool8 WorldCoop_PreparePrivateRewards(void)
{
    struct Pokemon merged[PARTY_SIZE];
    u8 active = gBattlerPartyIndexes[sCoop.local * 2] - sCoop.local * MULTI_PARTY_SIZE;
    bool8 valid;
    if (!WorldCoop_CompletionCommitted())
        return FALSE;
    valid = BuildPrivateParty(merged);
    if (valid)
        memset(sCoop.medicineSpent, 0, sizeof(sCoop.medicineSpent));
    else
        WorldCoop_RefundMedicine();
    memcpy(gPlayerParty, valid ? merged : sCoop.original, sizeof(merged));
    gPlayerPartyCount = sCoop.originalCount;
    gBattlerPartyIndexes[0] = sCoop.slots[active < sCoop.count ? active : 0];
    LoadPrivateBattleMon();
    if (!valid)
        sCoop.reward = sCoop.catchOwner = FALSE;
    gPaydayMoney = valid && sCoop.reward ? sCoop.rewardPayday : 0;
    gBattleStruct->moneyMultiplier = sCoop.rewardMultiplier;
    sCoop.staged = FALSE;
    sCoop.state = COOP_REWARDS;
    CloseLink();
    gBattleTypeFlags = sCoop.kind ? BATTLE_TYPE_TRAINER : 0;
    gBattleControllerExecFlags = 0;
    return valid;
}

bool8 WorldCoop_NextReward(void)
{
    while (sCoop.rewardRead < sCoop.enemyCount && !(sCoop.reward & (1 << sCoop.rewardRead)))
        sCoop.rewardRead++;
    if (sCoop.rewardRead == sCoop.enemyCount)
        return FALSE;
    memset(&gBattleMons[1], 0, sizeof(gBattleMons[1]));
    gBattleMons[1].species = GetMonData(&sCoop.enemies[sCoop.rewardRead], MON_DATA_SPECIES);
    gBattleMons[1].level = GetMonData(&sCoop.enemies[sCoop.rewardRead], MON_DATA_LEVEL);
    gBattlerFainted = 1;
    gBattlerPartyIndexes[1] = sCoop.rewardRead;
    gSentPokesToOpponent[0] = sCoop.rewardMask[sCoop.rewardRead++];
    gBattleScripting.getexpState = 0;
    return TRUE;
}
#endif
