/* Isolated behavioral tests of the production co-op state machine. Link IO
 * and Pokemon accessors are explicit fixtures, not a simulated game result. */
#include "../../src/platform/world_coop.c"
/* The game config defines NDEBUG. This test must execute assertions. */
#undef NDEBUG
#include <assert.h>
#include <stdio.h>

struct Pokemon gPlayerParty[PARTY_SIZE], gEnemyParty[PARTY_SIZE];
u8 gPlayerPartyCount, gEnemyPartyCount;
struct Main gMain;
struct LinkPlayer gLinkPlayers[MAX_RFU_PLAYERS];
u16 gBlockRecvBuffer[MAX_RFU_PLAYERS][BLOCK_BUFFER_SIZE / 2];
u8 gReceivedRemoteLinkPlayers;
u32 gBattleTypeFlags, gBattleControllerExecFlags;
u16 gPaydayMoney;
u32 gRngValue, gRecordedBattleRngSeed;
u8 gBattlersCount, gBattlerPositions[MAX_BATTLERS_COUNT];
u16 gBattlerPartyIndexes[MAX_BATTLERS_COUNT];
void (*gBattleMainFunc)(void), (*gBattlerControllerFuncs[MAX_BATTLERS_COUNT])(void);
struct BattleScripting gBattleScripting;
static struct BattleStruct testBattleStruct;
struct BattleStruct *gBattleStruct = &testBattleStruct;
struct BattlePokemon gBattleMons[MAX_BATTLERS_COUNT];
u8 gActiveBattler, gBattlerFainted, gSentPokesToOpponent[2], gAbsentBattlerFlags;
static u8 emittedRewards[2][12];
static u8 local, received, corruptPhase, remoteOwner;
static bool8 active;
u8 gBattleOutcome = B_OUTCOME_WON;
static u32 testGeneration = 17;
u32 NativeLink_Generation(void) { return testGeneration; }
static struct CoopCompletion lastCompletion;
static unsigned completionSends;
static bool8 bilateral;
static struct CoopCompletion completionQueue[2][8];
static unsigned completionCount[2];
static u16 sizes[2];
static struct Pokemon remoteParty[3], remoteWild;

/* Fixtures store accessors' data in known encrypted words. The production
 * checksum gate still executes before any accessor, including on corruption. */
u32 GetMonData(struct Pokemon *mon, s32 field, u8 *unused)
{
    u32 key = mon->box.personality ^ mon->box.otId;
    u32 *raw = mon->box.secure.raw;
    (void)unused;
    switch (field)
    {
    case MON_DATA_SPECIES: return (raw[0] ^ key) & 0xFFFF;
    case MON_DATA_IS_EGG: return 0;
    case MON_DATA_HP: return mon->hp;
    case MON_DATA_MAX_HP: return mon->maxHP;
    case MON_DATA_ATK: return mon->attack;
    case MON_DATA_DEF: return mon->defense;
    case MON_DATA_SPEED: return mon->speed;
    case MON_DATA_SPATK: return mon->spAttack;
    case MON_DATA_SPDEF: return mon->spDefense;
    case MON_DATA_PERSONALITY: return mon->box.personality;
    case MON_DATA_OT_ID: return mon->box.otId;
    case MON_DATA_STATUS: return mon->status;
    case MON_DATA_FRIENDSHIP: return 100;
    case MON_DATA_ABILITY_NUM: return 0;
    case MON_DATA_HP_IV: case MON_DATA_ATK_IV: case MON_DATA_DEF_IV:
    case MON_DATA_SPEED_IV: case MON_DATA_SPATK_IV: case MON_DATA_SPDEF_IV: return 10;
    case MON_DATA_NICKNAME: memcpy(unused, mon->box.nickname, sizeof(mon->box.nickname)); return 0;
    case MON_DATA_OT_NAME: memcpy(unused, mon->box.otName, sizeof(mon->box.otName)); return 0;
    case MON_DATA_LEVEL: return mon->level;
    case MON_DATA_HELD_ITEM: return (raw[0] ^ key) >> 16;
    case MON_DATA_POKEBALL: return 1;
    case MON_DATA_EXP: return raw[3] ^ key;
    case MON_DATA_PP_BONUSES: return 0;
    default:
        if (field >= MON_DATA_MOVE1 && field <= MON_DATA_MOVE4)
            return (raw[1 + (field - MON_DATA_MOVE1) / 2] ^ key) >> (((field - MON_DATA_MOVE1) % 2) * 16) & 0xFFFF;
        if (field >= MON_DATA_PP1 && field <= MON_DATA_PP4) return 0;
        assert(!"unexpected fixture accessor"); return 0;
    }
}
u32 GetMonData2(struct Pokemon *mon, s32 field) { return GetMonData3(mon, field, NULL); }
const struct SpeciesInfo gSpeciesInfo[NUM_SPECIES] = {0};
u8 GetMonAbility(struct Pokemon *mon) { return 1; }
u8 CalculatePPWithBonus(u16 move, u8 bonuses, u8 index) { return 40; }
u8 BattleSetup_GetEnvironmentId(void) { return BATTLE_ENVIRONMENT_GRASS; }
u8 GetCurrentWeather(void) { return WEATHER_RAIN; }
void SetMainCallback1(MainCallback cb) { gMain.callback1 = cb; }
void SetMainCallback2(MainCallback cb) { gMain.callback2 = cb; }
void ZeroEnemyPartyMons(void) { memset(gEnemyParty, 0, sizeof(gEnemyParty)); }
int NativeLink_IsActive(void) { return active; }
void NativeLink_Abort(void) { active = FALSE; }
void CloseLink(void) { gReceivedRemoteLinkPlayers = FALSE; }
void WorldActivity_ReturnToField(void) { gMain.callback2 = NULL; }
void WorldActivity_ReturnFromCoopWildBattle(void) {}
u8 GetLinkPlayerCount(void) { return 2; }
u8 GetMultiplayerId(void) { return local; }
u8 BitmaskAllOtherLinkPlayers(void) { return 3 ^ (1 << local); }
bool8 IsLinkTaskFinished(void) { return TRUE; }
u8 GetBlockReceivedStatus(void) { return received; }
void ResetBlockReceivedFlags(void) { received = 0; }
u16 GetBlockReceivedSize(u8 peer) { return sizes[peer]; }
void CB2_InitBattle(void) {}
void BufferBattlePartyCurrentOrderBySide(u8 battler, u8 flank) {}
u8 GetPartyIdFromBattlePartyId(u8 index) { return sCoop.partyMenuOrder ? 5 - index : index; }
void SetControllerToPlayer(void) {}
void SetControllerToLinkPartner(void) {}
void SetControllerToOpponent(void) {}
void SetControllerToLinkOpponent(void) {}
void BeginBattleIntro(void) {}
void PrepareBufferDataTransferLink(u8 id, u16 size, u8 *data)
{
    assert(id == B_COMM_TO_CONTROLLER && size <= 12 && !(gActiveBattler & 1));
    memset(emittedRewards[gActiveBattler / 2], 0, 12);
    memcpy(emittedRewards[gActiveBattler / 2], data, size);
}
void MarkBattlerForControllerExec(u8 battler) {}

/* This fixture exercises defeat completion. Catch ownership/encryption has
 * its own stock-accessor fixture in coop_catching_core.c. Fail on accidental
 * entry rather than inventing a catch or mutating an unmodelled bag/PC. */
u8 gBattlerAttacker, gBattlerTarget;
u16 gLastUsedItem;
struct SaveBlock2 *gSaveBlock2Ptr;
bool8 IsPokemonStorageFull(void) { assert(!"unexpected catch storage query"); return TRUE; }
bool8 CheckBagHasItem(u16 item, u16 count) { assert(!"unexpected catch bag query"); return FALSE; }
bool8 RemoveBagItem(u16 item, u16 count) { assert(!"unexpected catch bag removal"); return FALSE; }
u16 SpeciesToNationalPokedexNum(u16 species) { assert(!"unexpected catch dex query"); return 0; }
s8 GetSetPokedexFlag(u16 species, u8 operation) { assert(!"unexpected catch dex mutation"); return 0; }
void SetMonData(struct Pokemon *mon, s32 field, const void *data) { assert(!"unexpected catch setter"); }

bool8 SendBlock(u8 mask, const void *src, u16 size)
{
    u8 peer = local ^ 1;
    assert(size <= 256);
    if (sCoop.state == COOP_BATTLE && size == sizeof(struct CoopCompletion))
    {
        lastCompletion = *(const struct CoopCompletion *)src;
        completionSends++;
        if (bilateral)
        {
            assert(completionCount[peer] < 8);
            completionQueue[peer][completionCount[peer]++] = lastCompletion;
            assert(completionCount[local] < 8);
            completionQueue[local][completionCount[local]++] = lastCompletion;
        }
        return TRUE;
    }
    memcpy(gBlockRecvBuffer[local], src, size);
    sizes[local] = sizes[peer] = size;
    if (size == sizeof(struct CoopHeader))
    {
        struct CoopHeader header = *(const struct CoopHeader *)src;
        header.owner = remoteOwner;
        header.count = 3;
        header.environment = remoteOwner ? BATTLE_ENVIRONMENT_CAVE : 0;
        header.weather = remoteOwner ? WEATHER_SANDSTORM : 0;
        header.seed = remoteOwner ? 0xABC123 : 0;
        header.kind = header.trainer = 0;
        header.enemyCount = remoteOwner ? 1 : 0;
        memcpy(gBlockRecvBuffer[peer], &header, size);
    }
    else
    {
        struct CoopMonBlock block = *(const struct CoopMonBlock *)src;
        memset(&block.mon, 0, sizeof(block.mon));
        if (block.phase <= 3) block.mon = remoteParty[block.phase - 1];
        else if (remoteOwner && block.phase == 4) block.mon = remoteWild;
        if (block.phase == corruptPhase) block.mon.box.checksum++;
        memcpy(gBlockRecvBuffer[peer], &block, size);
    }
    received = 3;
    return TRUE;
}

static struct Pokemon FixtureMon(u16 species, u32 identity)
{
    struct Pokemon mon = {0};
    u32 key;
    int i;
    mon.box.personality = identity;
    mon.box.otId = identity + 100;
    mon.box.hasSpecies = TRUE;
    mon.box.language = LANGUAGE_ENGLISH;
    memset(mon.box.nickname, EOS, sizeof(mon.box.nickname));
    memset(mon.box.otName, EOS, sizeof(mon.box.otName));
    mon.level = 10;
    mon.hp = mon.maxHP = 30;
    mon.attack = mon.defense = mon.speed = mon.spAttack = mon.spDefense = 20;
    mon.box.secure.raw[0] = species;
    mon.box.secure.raw[1] = 1;
    mon.box.secure.raw[3] = 1000;
    key = mon.box.personality ^ mon.box.otId;
    for (i = 0; i < (int)ARRAY_COUNT(mon.box.secure.raw); i++)
    {
        mon.box.checksum += (u16)mon.box.secure.raw[i];
        mon.box.checksum += (u16)(mon.box.secure.raw[i] >> 16);
        mon.box.secure.raw[i] ^= key;
    }
    return mon;
}

static void Reset(u8 slot, bool8 own)
{
    int i;
    memset(&sCoop, 0, sizeof(sCoop));
    memset(&gMain, 0, sizeof(gMain));
    local = slot;
    testGeneration = 17;
    active = gReceivedRemoteLinkPlayers = TRUE;
    received = corruptPhase = 0;
    remoteOwner = !own;
    for (i = 0; i < PARTY_SIZE; i++) gPlayerParty[i] = FixtureMon(1 + i, 1000 + slot * 100 + i);
    gPlayerParty[0].hp = gPlayerParty[2].hp = 0;
    for (i = 0; i < 3; i++) remoteParty[i] = FixtureMon(25 + i, 2000 + i);
    gEnemyParty[0] = FixtureMon(100, 3000);
    remoteWild = FixtureMon(101, 3001);
    gPlayerPartyCount = 6;
    WorldCoop_CaptureWild();
    assert(WorldCoop_StartBattle(own));
}

static void Exchange(void)
{
    int i;
    for (i = 0; i < COOP_CONFIRM + 2 && gMain.callback2 != CB2_InitBattle; i++) CB2_Exchange();
}

struct PeerFixture
{
    typeof(sCoop) coop;
    struct Pokemon party[PARTY_SIZE];
    u16 indexes[MAX_BATTLERS_COUNT];
    bool8 connected;
};
u16 gTrainerBattleOpponent_A;
const struct Trainer gTrainers[TRAINERS_COUNT] = {0};
void WorldCoop_CreateTrainerParty(void) { assert(!"unexpected trainer entry"); }
void BattleSetup_RecordWorldTrainerBattle(void) {}
void BattleSetup_RecordWorldWildBattle(void) {}
static struct PeerFixture peers[2];

static void SavePeer(void)
{
    peers[local].coop = sCoop;
    memcpy(peers[local].party, gPlayerParty, sizeof(gPlayerParty));
    memcpy(peers[local].indexes, gBattlerPartyIndexes, sizeof(gBattlerPartyIndexes));
    peers[local].connected = active;
}
static void LoadPeer(u8 peer)
{
    local = peer;
    sCoop = peers[peer].coop;
    memcpy(gPlayerParty, peers[peer].party, sizeof(gPlayerParty));
    memcpy(gBattlerPartyIndexes, peers[peer].indexes, sizeof(gBattlerPartyIndexes));
    active = peers[peer].connected;
    gReceivedRemoteLinkPlayers = active;
}
static void DeliverCompletion(void)
{
    for (unsigned i = 0; i < completionCount[local]; i++)
    {
        struct CoopCompletion *packet = &completionQueue[local][i];
        assert(WorldCoop_ReceiveCompletion((u8 *)packet, sizeof(*packet), packet->sender) == 1);
    }
    completionCount[local] = 0;
}

static void AsymmetricCompletion(void)
{
    u8 packet[12] = { CONTROLLER_EXPUPDATE, 0, 100, 0, 10, 0, 0, 0, 1 };
    for (u8 peer = 0; peer < 2; peer++)
    {
        Reset(peer, peer == 0); Exchange(); WorldCoop_InitControllers();
        sCoop.seed = 0x123;
        sCoop.enemies[0] = FixtureMon(100, 3000);
        packet[5] = 1 | (1 << MULTI_PARTY_SIZE);
        WorldCoop_RecordDefeat(packet);
        gPlayerParty[peer * MULTI_PARTY_SIZE].hp = 10 + peer;
        SavePeer();
    }
    /* Both snapshots are distinct, while the staged allied party is the same
     * six wire mons on both machines, as in a completed real exchange. */
    for (u8 i = 0; i < MULTI_PARTY_SIZE; i++)
    {
        peers[0].party[MULTI_PARTY_SIZE + i] = peers[1].party[MULTI_PARTY_SIZE + i];
        peers[1].party[i] = peers[0].party[i];
    }
    bilateral = TRUE;
    memset(completionCount, 0, sizeof(completionCount));
    LoadPeer(0);
    for (int frame = 0; frame < 40; frame++)
    {
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(active && sCoop.staged && !WorldCoop_CompletionCommitted());
    }
    SavePeer();
    /* Slow peer now finishes its fade. Its earlier ENDLINKBATTLE ACK was not
     * used as readiness, and the faster peer has not torn anything down. */
    LoadPeer(1); DeliverCompletion();
    assert(!WorldCoop_ReadyForPrivateRewards()); /* READY */
    DeliverCompletion(); /* Local READY echo, not a completion point. */
    assert(!WorldCoop_ReadyForPrivateRewards()); /* COMMIT */
    assert(!WorldCoop_ReadyForPrivateRewards()); /* COMMIT only queued. */
    SavePeer();
    LoadPeer(0);
    DeliverCompletion(); /* Local READY, partner READY, partner COMMIT. */
    assert(!WorldCoop_ReadyForPrivateRewards());
    assert(!WorldCoop_ReadyForPrivateRewards()); /* Local COMMIT is not echoed. */
    DeliverCompletion();
    assert(WorldCoop_CompletionCommitted());
    SavePeer();
    LoadPeer(1); DeliverCompletion();
    assert(WorldCoop_ReadyForPrivateRewards());
    assert(!WorldCoop_IsPrivateRewards());
    assert(WorldCoop_PreparePrivateRewards());
    assert(WorldCoop_IsPrivateRewards() && !gReceivedRemoteLinkPlayers);
    assert(gPlayerParty[1].hp == 11 && gPlayerPartyCount == 6);
    for (u8 i = 0; i < PARTY_SIZE; i++)
        assert(gPlayerParty[i].box.personality == sCoop.original[i].box.personality);
    assert(!memcmp(&gPlayerParty[5], &sCoop.original[5], sizeof(struct Pokemon)));
    assert(WorldCoop_NextReward());
    assert(!WorldCoop_NextReward());
    assert(!WorldCoop_PreparePrivateRewards());
    SavePeer();
    LoadPeer(0); active = FALSE; /* normal partner closure overtakes receipt */
    assert(WorldCoop_CompletionCommitted() && WorldCoop_ReadyForPrivateRewards());
    assert(WorldCoop_PreparePrivateRewards());
    assert(gPlayerParty[1].hp == 10 && gPlayerPartyCount == 6);
    assert(WorldCoop_NextReward());
    assert(!WorldCoop_NextReward());
    assert(!WorldCoop_PreparePrivateRewards());
    for (u8 i = 0; i < PARTY_SIZE; i++)
        assert(gPlayerParty[i].box.personality == sCoop.original[i].box.personality);
    bilateral = FALSE;
    puts("bilateral asymmetric production completion: both private parties and single-use rewards retained");
}

int main(void)
{
    struct Pokemon originals[6];
    u8 packet[12] = { CONTROLLER_EXPUPDATE, 0, 101, 0, 10, 1 << 3, 10, 0, 1, 0, 0, 0 };
    struct Pokemon invalid = FixtureMon(1, 1);
    assert(MonValid(&invalid, FALSE));
    invalid.box.checksum++;
    assert(!MonValid(&invalid, FALSE));
    invalid = FixtureMon(NUM_SPECIES, 1);
    assert(!MonValid(&invalid, FALSE));
    invalid = FixtureMon(1, 1); invalid.level = 101;
    assert(!MonValid(&invalid, FALSE));
    invalid = FixtureMon(1, 1); invalid.defense = 0;
    assert(!MonValid(&invalid, FALSE));
    invalid = FixtureMon(1, 1);
    invalid.box.secure.raw[1] ^= 1 ^ MOVES_COUNT;
    invalid.box.checksum += MOVES_COUNT - 1;
    assert(!MonValid(&invalid, FALSE));
    invalid = FixtureMon(1, 1);
    invalid.box.secure.raw[0] ^= ITEMS_COUNT << 16;
    invalid.box.checksum += ITEMS_COUNT;
    assert(!MonValid(&invalid, FALSE));

    Reset(1, FALSE);
    memcpy(originals, sCoop.original, sizeof(originals));
    assert(WorldCoop_GetOwnPartyCount() == 6);
    assert(WorldCoop_GetOwnMon(1)->box.personality == originals[1].box.personality);
    Exchange();
    assert(sCoop.state == COOP_BATTLE);
    assert(sCoop.ownerPeer == 0);
    assert(GetMonData(&gEnemyParty[0], MON_DATA_SPECIES, NULL) == 101);
    assert(gRngValue == 0xABC123);
    assert(WorldCoop_Environment() == BATTLE_ENVIRONMENT_CAVE);
    assert(WorldCoop_FieldWeather() == WEATHER_SANDSTORM);
    WorldCoop_InitControllers();
    assert(gBattlerControllerFuncs[2] == SetControllerToPlayer);
    assert(gBattlerControllerFuncs[0] == SetControllerToLinkPartner);
    assert(gBattlerPositions[0] == 0 && gBattlerPositions[2] == 2);
    assert(gAbsentBattlerFlags == 1 << B_POSITION_OPPONENT_RIGHT);
    assert(sCoop.slots[0] == 1 && sCoop.slots[1] == 3 && sCoop.slots[2] == 4);
    gPlayerParty[3].hp = 11;
    gPlayerParty[4].hp = 12;
    gPlayerParty[5].hp = 13;
    assert(WorldCoop_GetOwnMon(1)->hp == 11);
    assert(WorldCoop_GetOwnMon(3)->hp == 12);
    assert(WorldCoop_GetOwnMon(4)->hp == 13);
    assert(WorldCoop_GetOwnMon(0)->box.personality == originals[0].box.personality);
    assert(WorldCoop_GetOwnMon(5)->box.personality == originals[5].box.personality);
    assert(WorldCoop_GetOwnMon(PARTY_SIZE) == NULL);
    {
        struct Pokemon ordered[PARTY_SIZE];
        int i;
        memcpy(ordered, gPlayerParty, sizeof(ordered));
        for (i = 0; i < PARTY_SIZE; i++) gPlayerParty[5 - i] = ordered[i];
        WorldCoop_SetPartyMenuOrder(TRUE);
        assert(WorldCoop_GetOwnMon(1)->hp == 11);
        assert(WorldCoop_GetOwnMon(3)->hp == 12);
        assert(WorldCoop_GetOwnMon(4)->hp == 13);
        assert(WorldCoop_GetOwnMon(0)->box.personality == originals[0].box.personality);
        memcpy(gPlayerParty, ordered, sizeof(ordered));
        WorldCoop_SetPartyMenuOrder(FALSE);
    }
    assert(WorldCoop_RewardPacketValid(packet, sizeof(packet)));
    assert(!WorldCoop_RewardPacketValid(packet, sizeof(packet) - 1));
    gBattlerFainted = 1;
    gBattleMons[1].species = 101;
    gBattleMons[1].level = 10;
    gSentPokesToOpponent[0] = 1 << 3;
    WorldCoop_AddPayday(0, 10);
    WorldCoop_AddPayday(2, 30);
    WorldCoop_DoublePrize(2);
    WorldCoop_EmitDefeat();
    assert(emittedRewards[0][6] == 10 && emittedRewards[0][8] == 1);
    assert(emittedRewards[1][6] == 30 && emittedRewards[1][8] == 2);
    WorldCoop_RecordDefeat(emittedRewards[1]);
    /* A finished local fade is not bilateral completion. */
    assert(!WorldCoop_PreparePrivateRewards());
    assert(active && sCoop.staged);
    assert(gPlayerParty[3].hp == 11);
    /* The partner is paused after ENDLINKBATTLE ACK, before its fade finishes. */
    assert(!WorldCoop_ReadyForPrivateRewards());
    assert(lastCompletion.phase == COOP_READY && active && sCoop.staged);
    for (int n = 0; n < 20; n++) assert(!WorldCoop_ReadyForPrivateRewards());
    assert(!sCoop.commitSent && active);
    {
        struct CoopCompletion peer = lastCompletion;
        peer.sender = 0;
        assert(WorldCoop_ReceiveCompletion((u8 *)&peer, sizeof(peer), 0) == 1);
        assert(!WorldCoop_ReadyForPrivateRewards());
        assert(lastCompletion.phase == COOP_COMMIT && !WorldCoop_ReadyForPrivateRewards());
        assert(WorldCoop_ReceiveCompletion((u8 *)&lastCompletion, sizeof(lastCompletion), local) == 1);
        assert(WorldCoop_CompletionCommitted());
        /* Partner closes after receiving our COMMIT, before we consume theirs. */
        active = FALSE;
        assert(WorldCoop_ReadyForPrivateRewards());
    }
    assert(WorldCoop_PreparePrivateRewards());
    /* Slave engine mons were never run. Reward HUD must use the merged owner. */
    assert(gBattleMons[0].species == GetMonData(&gPlayerParty[gBattlerPartyIndexes[0]], MON_DATA_SPECIES));
    assert(gBattleMons[0].hp == 11 && gBattleMons[0].level == 10);
    assert(!WorldCoop_PreparePrivateRewards()); /* exactly once */
    assert(gPaydayMoney == 30 && gBattleStruct->moneyMultiplier == 2);
    assert(gPlayerPartyCount == 6);
    assert(gPlayerParty[1].hp == 11 && gPlayerParty[3].hp == 12 && gPlayerParty[4].hp == 13);
    assert(!memcmp(&gPlayerParty[0], &originals[0], sizeof(struct Pokemon)));
    assert(!memcmp(&gPlayerParty[2], &originals[2], sizeof(struct Pokemon)));
    assert(!memcmp(&gPlayerParty[5], &originals[5], sizeof(struct Pokemon)));
    assert(WorldCoop_NextReward());
    assert(gSentPokesToOpponent[0] == 1 << 1);
    assert(!WorldCoop_NextReward());

    Reset(0, FALSE); Exchange();
    assert(sCoop.state == COOP_BATTLE && sCoop.ownerPeer == 1);
    assert(gBattleTypeFlags & BATTLE_TYPE_IS_MASTER);
    assert(GetMonData(&gEnemyParty[0], MON_DATA_SPECIES, NULL) == 101);
    WorldCoop_InitControllers();
    assert(gBattlerControllerFuncs[0] == SetControllerToPlayer);
    assert(gBattlerControllerFuncs[2] == SetControllerToLinkPartner);
    WorldCoop_Abort();
    assert(!memcmp(gPlayerParty, sCoop.original, sizeof(gPlayerParty)));

    Reset(1, TRUE); Exchange();
    assert(sCoop.state == COOP_BATTLE && sCoop.ownerPeer == 1);
    assert(!(gBattleTypeFlags & BATTLE_TYPE_IS_MASTER));
    assert(GetMonData(&gEnemyParty[0], MON_DATA_SPECIES, NULL) == 100);
    assert(WorldCoop_Environment() == BATTLE_ENVIRONMENT_GRASS);
    assert(WorldCoop_FieldWeather() == WEATHER_RAIN);
    WorldCoop_Abort();

    Reset(0, TRUE); corruptPhase = 2; Exchange();
    assert(sCoop.state == COOP_IDLE && !active);
    assert(!memcmp(gPlayerParty, sCoop.original, sizeof(gPlayerParty)));

    Reset(0, TRUE); remoteOwner = TRUE; Exchange();
    assert(sCoop.state == COOP_IDLE && !active);
    assert(!memcmp(gPlayerParty, sCoop.original, sizeof(gPlayerParty)));

    Reset(1, FALSE); Exchange();
    gPlayerParty[3] = remoteParty[0];
    assert(!WorldCoop_ReadyForPrivateRewards());
    WorldCoop_Abort();
    assert(!WorldCoop_PreparePrivateRewards());
    assert(!memcmp(gPlayerParty, sCoop.original, sizeof(gPlayerParty)));
    AsymmetricCompletion();
    Reset(0, TRUE); Exchange();
    {
        struct CoopCompletion packet = {0};
        packet.magic = COOP_MAGIC; packet.version = COOP_VERSION;
        packet.phase = COOP_READY; packet.seed = sCoop.seed;
        packet.sender = 1; packet.outcome = B_OUTCOME_WON;
        /* A reopen cannot adopt an old battle into the new link generation. */
        packet.generation = testGeneration = 18;
        assert(WorldCoop_ReceiveCompletion((u8 *)&packet, sizeof(packet), 1) == -1);
        packet.generation = testGeneration = 17;
        packet.phase = COOP_COMMIT;
        assert(WorldCoop_ReceiveCompletion((u8 *)&packet, sizeof(packet), 1) == -1);
        packet.phase = COOP_READY; packet.sender = 0;
        assert(WorldCoop_ReceiveCompletion((u8 *)&packet, sizeof(packet), 1) == -1);
        packet.sender = 1; packet.seed++;
        assert(WorldCoop_ReceiveCompletion((u8 *)&packet, sizeof(packet), 1) == -1);
        /* Disconnect before the bilateral readiness point rolls back exactly. */
        active = FALSE;
        assert(!WorldCoop_CompletionCommitted());
        WorldCoop_Abort();
        assert(!memcmp(gPlayerParty, sCoop.original, sizeof(gPlayerParty)));
    }
    puts("co-op core: checksum/species/level rejection, authoritative owner, allied controllers, private six-slot merge, rollback and reward ownership passed");
    return 0;
}
