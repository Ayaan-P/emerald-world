#ifdef PORTABLE
#include "global.h"
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
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/characters.h"
#include "constants/weather.h"
#include "platform/native_link.h"
#include "platform/world_activity.h"
#include "platform/world_coop.h"
#include <string.h>

/* No saved data or pointers cross this boundary. The native Pokemon layout is
 * exactly the 100-byte GBA layout on every supported native architecture. */
STATIC_ASSERT(sizeof(struct Pokemon) == 100, CoopPokemonWireSize);
enum { COOP_IDLE, COOP_EXCHANGE, COOP_BATTLE, COOP_REWARDS };
enum { COOP_MAGIC = 0x4357, COOP_VERSION = 1, COOP_TIMEOUT = 1800 };
struct CoopHeader
{
    u16 magic;
    u8 version, phase;
    u8 owner, count, environment, weather;
    u32 seed;
};
struct CoopMonBlock
{
    u16 magic;
    u8 version, phase;
    struct Pokemon mon;
};
STATIC_ASSERT(sizeof(struct CoopMonBlock) <= 256, CoopBlockBound);
STATIC_ASSERT(sizeof(struct CoopHeader) == 12, CoopHeaderWireSize);
struct CoopCompletion
{
    u16 magic;
    u8 version, phase;
    u32 generation, seed;
    u8 sender, outcome, reward, reserved;
};
STATIC_ASSERT(sizeof(struct CoopCompletion) == 16, CoopCompletionWireSize);
static struct
{
    u8 readySent, commitSent, peerReady, peerCommit, peerOutcome, peerReward;
    u8 state, phase, local, ownerPeer, count, originalCount;
    u8 slots[MULTI_PARTY_SIZE];
    u8 rewardMask, rewardRead;
    u8 moneyMultiplier[2], rewardMultiplier;
    u16 payday[2], rewardPayday;
    bool8 owner, sent, staged, captured, reward, partyMenuOrder;
    u16 timer;
    u8 environment, capturedEnvironment, weather, capturedWeather;
    u32 seed, capturedSeed, generation;
    struct Pokemon original[PARTY_SIZE];
    struct Pokemon selected[MULTI_PARTY_SIZE];
    struct Pokemon allies[PARTY_SIZE];
    struct Pokemon wild, capturedWild;
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

void WorldCoop_CaptureWild(void)
{
    if (sCoop.state != COOP_IDLE)
        return;
    sCoop.capturedWild = gEnemyParty[0];
    sCoop.capturedEnvironment = BattleSetup_GetEnvironmentId();
    sCoop.capturedWeather = GetCurrentWeather();
    sCoop.capturedSeed = gRngValue;
    sCoop.captured = MonValid(&sCoop.capturedWild, FALSE)
                  && GetMonData(&sCoop.capturedWild, MON_DATA_HP) != 0;
}

int WorldCoop_IsBattle(void)
{
    return sCoop.state == COOP_EXCHANGE || sCoop.state == COOP_BATTLE;
}

u8 WorldCoop_Environment(void) { return sCoop.environment; }
u8 WorldCoop_FieldWeather(void) { return sCoop.weather; }

const struct Pokemon *WorldCoop_GetOwnMon(u8 originalSlot)
{
    u8 i;
    if (originalSlot >= PARTY_SIZE)
        return NULL;
    if (!WorldCoop_IsBattle())
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
    return &sCoop.original[originalSlot];
}

u8 WorldCoop_GetOwnPartyCount(void)
{
    return WorldCoop_IsBattle() ? sCoop.originalCount : gPlayerPartyCount;
}

void WorldCoop_SetPartyMenuOrder(bool8 inMenuOrder)
{
    sCoop.partyMenuOrder = inMenuOrder;
}

void WorldCoop_Abort(void)
{
    if (sCoop.staged)
    {
        memcpy(gPlayerParty, sCoop.original, sizeof(sCoop.original));
        gPlayerPartyCount = sCoop.originalCount;
    }
    sCoop.state = COOP_IDLE;
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
        && header->environment <= BATTLE_ENVIRONMENT_PLAIN;
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
        if (phase == 0 || phase == 5)
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
            else if (sCoop.owner)
                sCoop.outgoing.mon = sCoop.capturedWild;
            if (!SendBlock(BitmaskAllOtherLinkPlayers(), &sCoop.outgoing, sizeof(sCoop.outgoing)))
                return;
        }
        sCoop.sent = TRUE;
    }
    if ((GetBlockReceivedStatus() & 3) != 3 || !IsLinkTaskFinished())
        return;
    for (peer = 0; peer < 2; peer++)
    {
        if (phase == 0 || phase == 5)
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
            bool8 empty = phase <= 3 ? phase > sCoop.headers[peer].count : peer != sCoop.ownerPeer;
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
                sCoop.wild = block.mon;
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
    }
    sCoop.sent = FALSE;
    sCoop.timer = 0;
    sCoop.phase++;
    if (phase != 5)
        return;

    /* Only after both sides validated every block can a mixed battle party
     * exist. The untouched private snapshot is the rollback boundary. */
    memcpy(gPlayerParty, sCoop.allies, sizeof(sCoop.allies));
    /* Native multi menus use a six-slot layout, including empty reserves. */
    gPlayerPartyCount = PARTY_SIZE;
    ZeroEnemyPartyMons();
    gEnemyParty[0] = sCoop.wild;
    gEnemyPartyCount = 1;
    sCoop.staged = TRUE;
    sCoop.captured = FALSE;
    sCoop.generation = NativeLink_Generation();
    sCoop.state = COOP_BATTLE;
    gRngValue = gRecordedBattleRngSeed = sCoop.seed;
    gBattleTypeFlags = BATTLE_TYPE_LINK | BATTLE_TYPE_MULTI | BATTLE_TYPE_DOUBLE;
    if (sCoop.local == 0)
        gBattleTypeFlags |= BATTLE_TYPE_IS_MASTER;
    for (i = 0; i < 2; i++)
        gLinkPlayers[i].id = i * 2;
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
    sCoop.readySent = sCoop.commitSent = sCoop.peerReady = sCoop.peerCommit = FALSE;
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
    sCoop.originalCount = gPlayerPartyCount;
    sCoop.owner = !!encounterOwner;
    sCoop.local = GetMultiplayerId();
    sCoop.phase = sCoop.timer = 0;
    sCoop.sent = sCoop.staged = sCoop.reward = sCoop.rewardRead = sCoop.partyMenuOrder = FALSE;
    sCoop.payday[0] = sCoop.payday[1] = sCoop.rewardPayday = 0;
    sCoop.moneyMultiplier[0] = sCoop.moneyMultiplier[1] = sCoop.rewardMultiplier = 1;
    memset(sCoop.headers, 0, sizeof(sCoop.headers));
    header = &sCoop.headers[sCoop.local];
    header->magic = COOP_MAGIC;
    header->version = COOP_VERSION;
    header->owner = sCoop.owner;
    header->count = sCoop.count;
    header->environment = sCoop.owner ? sCoop.capturedEnvironment : 0;
    header->weather = sCoop.owner ? sCoop.capturedWeather : 0;
    header->seed = sCoop.owner ? sCoop.capturedSeed : 0;
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
    gAbsentBattlerFlags = 1 << B_POSITION_OPPONENT_RIGHT;
    for (i = 0; i < MAX_BATTLERS_COUNT; i++)
    {
        gBattlerPositions[i] = i;
        gBattlerPartyIndexes[i] = (i & BIT_FLANK) ? MULTI_PARTY_SIZE : 0;
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
    if ((battler & BIT_SIDE) ? partySlot != 0 : partySlot / MULTI_PARTY_SIZE != battler / 2)
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

void WorldCoop_EmitDefeat(void)
{
    u8 packet[9] = { CONTROLLER_EXPUPDATE, 0, 0, 0, 0, 0, 0, 0, 1 };
    u16 species = gBattleMons[gBattlerFainted].species;
    u8 battler;
    packet[2] = species;
    packet[3] = species >> 8;
    packet[4] = gBattleMons[gBattlerFainted].level;
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
    return size == 12 && data[0] == CONTROLLER_EXPUPDATE && data[1] == 0
        && (data[2] | (data[3] << 8)) == GetMonData(&sCoop.wild, MON_DATA_SPECIES)
        && data[4] == GetMonData(&sCoop.wild, MON_DATA_LEVEL)
        && (data[5] & ~0x3F) == 0 && (data[8] == 1 || data[8] == 2)
        && data[9] == 0 && data[10] == 0 && data[11] == 0;
}

void WorldCoop_RecordDefeat(const u8 *data)
{
    u8 i, mask = data[5] >> (sCoop.local * MULTI_PARTY_SIZE);
    if (sCoop.reward || !WorldCoop_RewardPacketValid(data, 12))
        return;
    sCoop.rewardMask = 0;
    for (i = 0; i < sCoop.count; i++)
        if (mask & (1 << i))
            sCoop.rewardMask |= 1 << sCoop.slots[i];
    sCoop.reward = TRUE;
    sCoop.rewardPayday = data[6] | (data[7] << 8);
    sCoop.rewardMultiplier = data[8];
}

static bool8 BuildPrivateParty(struct Pokemon merged[PARTY_SIZE])
{
    u8 i;
    bool8 valid = TRUE;
    memcpy(merged, sCoop.original, sizeof(sCoop.original));
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
     || packet.seed != sCoop.seed || packet.sender != sender || packet.reserved
     || packet.outcome == 0 || packet.outcome > B_OUTCOME_MON_TELEPORTED
     || packet.reward > 1 || (packet.phase != 6 && packet.phase != 7))
        return -1;
    if (sender == sCoop.local)
        return 1;
    if (packet.phase == 6)
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
    return sCoop.state == COOP_BATTLE && sCoop.commitSent && sCoop.peerReady;
}

bool8 WorldCoop_ReadyForPrivateRewards(void)
{
    struct Pokemon merged[PARTY_SIZE];
    struct CoopCompletion packet = {0};
    if (sCoop.state != COOP_BATTLE)
        return FALSE;
    if (WorldCoop_CompletionCommitted() && (!NativeLink_IsActive() || sCoop.peerCommit))
        return TRUE;
    if (!NativeLink_IsActive() || NativeLink_Generation() != sCoop.generation
     || ++sCoop.timer > COOP_TIMEOUT || !BuildPrivateParty(merged)
     || (sCoop.peerReady && (sCoop.peerOutcome != gBattleOutcome || sCoop.peerReward != sCoop.reward)))
    {
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
    packet.phase = sCoop.readySent ? 7 : 6;
    if ((!sCoop.readySent || (sCoop.peerReady && !sCoop.commitSent))
     && SendBlock(BitmaskAllOtherLinkPlayers(), &packet, sizeof(packet)))
    {
        if (!sCoop.readySent)
            sCoop.readySent = TRUE;
        else
            sCoop.commitSent = TRUE;
    }
    return WorldCoop_CompletionCommitted() && sCoop.peerCommit;
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
    memcpy(gPlayerParty, valid ? merged : sCoop.original, sizeof(merged));
    gPlayerPartyCount = sCoop.originalCount;
    gBattlerPartyIndexes[0] = sCoop.slots[active < sCoop.count ? active : 0];
    LoadPrivateBattleMon();
    if (!valid)
        sCoop.reward = FALSE;
    gPaydayMoney = valid && sCoop.reward ? sCoop.rewardPayday : 0;
    gBattleStruct->moneyMultiplier = sCoop.rewardMultiplier;
    sCoop.staged = FALSE;
    sCoop.state = COOP_REWARDS;
    CloseLink();
    gBattleTypeFlags = 0;
    gBattleControllerExecFlags = 0;
    return valid;
}

bool8 WorldCoop_NextReward(void)
{
    if (!sCoop.reward || sCoop.rewardRead)
    {
        sCoop.state = COOP_IDLE;
        return FALSE;
    }
    sCoop.rewardRead = TRUE;
    memset(&gBattleMons[1], 0, sizeof(gBattleMons[1]));
    gBattleMons[1].species = GetMonData(&sCoop.wild, MON_DATA_SPECIES);
    gBattleMons[1].level = GetMonData(&sCoop.wild, MON_DATA_LEVEL);
    gBattlerFainted = 1;
    gSentPokesToOpponent[0] = sCoop.rewardMask;
    gBattleScripting.getexpState = 0;
    return TRUE;
}
#endif
