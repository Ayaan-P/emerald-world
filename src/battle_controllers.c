#include "global.h"
#include "battle.h"
#include "battle_ai_script_commands.h"
#include "battle_anim.h"
#include "battle_controllers.h"
#include "battle_message.h"
#include "cable_club.h"
#include "link.h"
#include "link_rfu.h"
#include "party_menu.h"
#include "recorded_battle.h"
#include "task.h"
#include "util.h"
#include "constants/abilities.h"
#ifdef PORTABLE
#include "platform/native_link.h"
#include "platform/world_coop.h"
#include "constants/moves.h"
#include "constants/items.h"
#endif

static EWRAM_DATA u8 sLinkSendTaskId = 0;
static EWRAM_DATA u8 sLinkReceiveTaskId = 0;
#ifdef PORTABLE
static bool8 sNativeBattlePayloadFailed;
static bool8 sNativeBattleReplyUsed[MAX_BATTLERS_COUNT];
static bool8 sNativeBattleRequestPending[MAX_BATTLERS_COUNT];
/* Controllers replace buffer A's opcode with TERMINATOR_NOP on completion.
 * Keep the accepted request identity until its authenticated reply arrives. */
static u8 sNativeBattleRequest[MAX_BATTLERS_COUNT][3];
#endif
static EWRAM_DATA u8 sUnused = 0; // Debug? Never read
EWRAM_DATA struct UnusedControllerStruct gUnusedControllerStruct = {}; // Debug? Unused code that writes to it, never read
static EWRAM_DATA u8 sBattleBuffersTransferData[0x100] = {};

static void CreateTasksForSendRecvLinkBuffers(void);
static void InitLinkBtlControllers(void);
static void InitSinglePlayerBtlControllers(void);
static void SetBattlePartyIds(void);
static void Task_HandleSendLinkBuffersData(u8 taskId);
static void Task_HandleCopyReceivedLinkBuffersData(u8 taskId);

void HandleLinkBattleSetup(void)
{
    if (gBattleTypeFlags & BATTLE_TYPE_LINK)
    {
        if (gWirelessCommType)
            SetWirelessCommType1();
        if (!gReceivedRemoteLinkPlayers)
            OpenLink();
        CreateTask(Task_WaitForLinkPlayerConnection, 0);
        CreateTasksForSendRecvLinkBuffers();
    }
}

void SetUpBattleVarsAndBirchZigzagoon(void)
{
    s32 i;

    gBattleMainFunc = BeginBattleIntroDummy;

    for (i = 0; i < MAX_BATTLERS_COUNT; i++)
    {
        gBattlerControllerFuncs[i] = BattleControllerDummy;
        gBattlerPositions[i] = 0xFF;
        gActionSelectionCursor[i] = 0;
        gMoveSelectionCursor[i] = 0;
    }

    HandleLinkBattleSetup();
    gBattleControllerExecFlags = 0;
    ClearBattleAnimationVars();
    ClearBattleMonForms();
// UB: at the start of a battle CheckMoveLimitations is called with gActiveBattler 
// from the previous battle, which can lead to multiple arrays being accessed out of bounds
#ifdef UBFIX
    gActiveBattler = 0;
#endif
    BattleAI_HandleItemUseBeforeAISetup(0xF);

    if (gBattleTypeFlags & BATTLE_TYPE_FIRST_BATTLE)
    {
        ZeroEnemyPartyMons();
        CreateMon(&gEnemyParty[0], SPECIES_ZIGZAGOON, 2, USE_RANDOM_IVS, 0, 0, OT_ID_PLAYER_ID, 0);
        i = 0;
        SetMonData(&gEnemyParty[0], MON_DATA_HELD_ITEM, &i);
    }

    // Below are never read
    gUnusedFirstBattleVar1 = 0;
    gUnusedFirstBattleVar2 = 0;
}

void InitBattleControllers(void)
{
    s32 i;

    if (!(gBattleTypeFlags & BATTLE_TYPE_RECORDED))
        RecordedBattle_Init(B_RECORD_MODE_RECORDING);
    else
        RecordedBattle_Init(B_RECORD_MODE_PLAYBACK);

    if (!(gBattleTypeFlags & BATTLE_TYPE_RECORDED))
        RecordedBattle_SaveParties();

    if (gBattleTypeFlags & BATTLE_TYPE_LINK)
        InitLinkBtlControllers();
    else
        InitSinglePlayerBtlControllers();

    SetBattlePartyIds();

    if (!(gBattleTypeFlags & BATTLE_TYPE_MULTI))
    {
        for (i = 0; i < gBattlersCount; i++)
            BufferBattlePartyCurrentOrderBySide(i, 0);
    }

    for (i = 0; i < sizeof(gBattleStruct->tvMovePoints); i++)
        *((u8 *)(&gBattleStruct->tvMovePoints) + i) = 0;

    for (i = 0; i < sizeof(gBattleStruct->tv); i++)
        *((u8 *)(&gBattleStruct->tv) + i) = 0;
}

static void InitSinglePlayerBtlControllers(void)
{
    s32 i;

    if (gBattleTypeFlags & BATTLE_TYPE_INGAME_PARTNER)
    {
        gBattleMainFunc = BeginBattleIntro;

        if (gBattleTypeFlags & BATTLE_TYPE_RECORDED)
        {
            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedPlayer;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

            gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToPlayerPartner;
            gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

            gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToOpponent;
            gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;
        }
        else
        {
            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

            gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToPlayerPartner;
            gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

            gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToOpponent;
            gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;
        }

        gBattlersCount = MAX_BATTLERS_COUNT;

        BufferBattlePartyCurrentOrderBySide(0, 0);
        BufferBattlePartyCurrentOrderBySide(1, 0);
        BufferBattlePartyCurrentOrderBySide(2, 1);
        BufferBattlePartyCurrentOrderBySide(3, 1);

        gBattlerPartyIndexes[0] = 0;
        gBattlerPartyIndexes[1] = 0;
        gBattlerPartyIndexes[2] = 3;
        gBattlerPartyIndexes[3] = 3;
    }
    else if (!(gBattleTypeFlags & BATTLE_TYPE_DOUBLE))
    {
        gBattleMainFunc = BeginBattleIntro;

        if (gBattleTypeFlags & BATTLE_TYPE_SAFARI)
            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToSafari;
        else if (gBattleTypeFlags & BATTLE_TYPE_WALLY_TUTORIAL)
            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToWally;
        else
            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToPlayer;

        gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

        gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
        gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

        gBattlersCount = 2;

        if (gBattleTypeFlags & BATTLE_TYPE_RECORDED)
        {
            if (gBattleTypeFlags & BATTLE_TYPE_RECORDED_LINK)
            {
                if (gBattleTypeFlags & BATTLE_TYPE_RECORDED_IS_MASTER)
                {
                    gBattleMainFunc = BeginBattleIntro;

                    gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedPlayer;
                    gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

                    gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToRecordedOpponent;
                    gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

                    gBattlersCount = 2;
                }
                else // see how the banks are switched
                {
                    gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToRecordedPlayer;
                    gBattlerPositions[B_BATTLER_1] = B_POSITION_PLAYER_LEFT;

                    gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedOpponent;
                    gBattlerPositions[B_BATTLER_0] = B_POSITION_OPPONENT_LEFT;

                    gBattlersCount = 2;
                }
            }
            else
            {
                gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

                gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
                gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;
            }
        }
    }
    else
    {
        gBattleMainFunc = BeginBattleIntro;

        gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToPlayer;
        gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

        gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
        gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

        gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToPlayer;
        gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

        gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToOpponent;
        gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;

        gBattlersCount = MAX_BATTLERS_COUNT;

        if (gBattleTypeFlags & BATTLE_TYPE_RECORDED)
        {
            if (gBattleTypeFlags & BATTLE_TYPE_MULTI && gBattleTypeFlags & BATTLE_TYPE_BATTLE_TOWER)
            {
                gBattleMainFunc = BeginBattleIntro;

                gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

                gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
                gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

                gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

                gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToOpponent;
                gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;

                gBattlersCount = MAX_BATTLERS_COUNT;

                BufferBattlePartyCurrentOrderBySide(0, 0);
                BufferBattlePartyCurrentOrderBySide(1, 0);
                BufferBattlePartyCurrentOrderBySide(2, 1);
                BufferBattlePartyCurrentOrderBySide(3, 1);

                gBattlerPartyIndexes[0] = 0;
                gBattlerPartyIndexes[1] = 0;
                gBattlerPartyIndexes[2] = 3;
                gBattlerPartyIndexes[3] = 3;
            }
            else if (gBattleTypeFlags & BATTLE_TYPE_MULTI)
            {
                u8 multiplayerId;

                for (multiplayerId = gRecordedBattleMultiplayerId, i = 0; i < MAX_LINK_PLAYERS; i++)
                {
                    switch (gLinkPlayers[i].id)
                    {
                    case 0:
                    case 3:
                        BufferBattlePartyCurrentOrderBySide(gLinkPlayers[i].id, 0);
                        break;
                    case 1:
                    case 2:
                        BufferBattlePartyCurrentOrderBySide(gLinkPlayers[i].id, 1);
                        break;
                    }

                    if (i == multiplayerId)
                    {
                        gBattlerControllerFuncs[gLinkPlayers[i].id] = SetControllerToRecordedPlayer;
                        switch (gLinkPlayers[i].id)
                        {
                        case 0:
                        case 3:
                            gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_LEFT;
                            gBattlerPartyIndexes[gLinkPlayers[i].id] = 0;
                            break;
                        case 1:
                        case 2:
                            gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_RIGHT;
                            gBattlerPartyIndexes[gLinkPlayers[i].id] = 3;
                            break;
                        }
                    }
                    else if ((!(gLinkPlayers[i].id & 1) && !(gLinkPlayers[multiplayerId].id & 1))
                            || ((gLinkPlayers[i].id & 1) && (gLinkPlayers[multiplayerId].id & 1)))
                    {
                        gBattlerControllerFuncs[gLinkPlayers[i].id] = SetControllerToRecordedPlayer;
                        switch (gLinkPlayers[i].id)
                        {
                        case 0:
                        case 3:
                            gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_LEFT;
                            gBattlerPartyIndexes[gLinkPlayers[i].id] = 0;
                            break;
                        case 1:
                        case 2:
                            gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_RIGHT;
                            gBattlerPartyIndexes[gLinkPlayers[i].id] = 3;
                            break;
                        }
                    }
                    else
                    {
                        gBattlerControllerFuncs[gLinkPlayers[i].id] = SetControllerToRecordedOpponent;
                        switch (gLinkPlayers[i].id)
                        {
                        case 0:
                        case 3:
                            gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_OPPONENT_LEFT;
                            gBattlerPartyIndexes[gLinkPlayers[i].id] = 0;
                            break;
                        case 1:
                        case 2:
                            gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_OPPONENT_RIGHT;
                            gBattlerPartyIndexes[gLinkPlayers[i].id] = 3;
                            break;
                        }
                    }
                }
            }
            else if (gBattleTypeFlags & BATTLE_TYPE_IS_MASTER)
            {
                gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

                gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

                if (gBattleTypeFlags & BATTLE_TYPE_RECORDED_LINK)
                {
                  gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToRecordedOpponent;
                  gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

                  gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToRecordedOpponent;
                  gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;
                }
                else
                {
                  gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
                  gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

                  gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToOpponent;
                  gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;
                }
            }
            else
            {
                gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_1] = B_POSITION_PLAYER_LEFT;

                gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToRecordedPlayer;
                gBattlerPositions[B_BATTLER_3] = B_POSITION_PLAYER_RIGHT;

                if (gBattleTypeFlags & BATTLE_TYPE_RECORDED_LINK)
                {
                    gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToRecordedOpponent;
                    gBattlerPositions[B_BATTLER_0] = B_POSITION_OPPONENT_LEFT;

                    gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToRecordedOpponent;
                    gBattlerPositions[B_BATTLER_2] = B_POSITION_OPPONENT_RIGHT;
                }
                else
                {
                    gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToOpponent;
                    gBattlerPositions[B_BATTLER_0] = B_POSITION_OPPONENT_LEFT;

                    gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToOpponent;
                    gBattlerPositions[B_BATTLER_2] = B_POSITION_OPPONENT_RIGHT;
                }
            }
        }
    }
}

static void InitLinkBtlControllers(void)
{
    s32 i;
    u8 multiplayerId;

#ifdef PORTABLE
    if (WorldCoop_IsBattle())
    {
        WorldCoop_InitControllers();
        return;
    }
#endif
    if (!(gBattleTypeFlags & BATTLE_TYPE_DOUBLE))
    {
        if (gBattleTypeFlags & BATTLE_TYPE_IS_MASTER)
        {
            gBattleMainFunc = BeginBattleIntro;

            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

            gBattlersCount = 2;
        }
        else
        {
            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_OPPONENT_LEFT;

            gBattlersCount = 2;
        }
    }
    else if (!(gBattleTypeFlags & BATTLE_TYPE_MULTI) && gBattleTypeFlags & BATTLE_TYPE_DOUBLE)
    {
        if (gBattleTypeFlags & BATTLE_TYPE_IS_MASTER)
        {
            gBattleMainFunc = BeginBattleIntro;

            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

            gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

            gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;

            gBattlersCount = MAX_BATTLERS_COUNT;
        }
        else
        {
            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_OPPONENT_LEFT;

            gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_3] = B_POSITION_PLAYER_RIGHT;

            gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_2] = B_POSITION_OPPONENT_RIGHT;

            gBattlersCount = MAX_BATTLERS_COUNT;
        }
    }
    else if (gBattleTypeFlags & BATTLE_TYPE_BATTLE_TOWER)
    {
        if (gBattleTypeFlags & BATTLE_TYPE_IS_MASTER)
        {
            gBattleMainFunc = BeginBattleIntro;

            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToOpponent;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

            gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToLinkPartner;
            gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

            gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToOpponent;
            gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;

            gBattlersCount = MAX_BATTLERS_COUNT;
        }
        else
        {
            gBattlerControllerFuncs[B_BATTLER_0] = SetControllerToLinkPartner;
            gBattlerPositions[B_BATTLER_0] = B_POSITION_PLAYER_LEFT;

            gBattlerControllerFuncs[B_BATTLER_1] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_1] = B_POSITION_OPPONENT_LEFT;

            gBattlerControllerFuncs[B_BATTLER_2] = SetControllerToPlayer;
            gBattlerPositions[B_BATTLER_2] = B_POSITION_PLAYER_RIGHT;

            gBattlerControllerFuncs[B_BATTLER_3] = SetControllerToLinkOpponent;
            gBattlerPositions[B_BATTLER_3] = B_POSITION_OPPONENT_RIGHT;

            gBattlersCount = MAX_BATTLERS_COUNT;
        }

        BufferBattlePartyCurrentOrderBySide(0, 0);
        BufferBattlePartyCurrentOrderBySide(1, 0);
        BufferBattlePartyCurrentOrderBySide(2, 1);
        BufferBattlePartyCurrentOrderBySide(3, 1);
        gBattlerPartyIndexes[0] = 0;
        gBattlerPartyIndexes[1] = 0;
        gBattlerPartyIndexes[2] = 3;
        gBattlerPartyIndexes[3] = 3;
    }
    else
    {
        multiplayerId = GetMultiplayerId();

        if (gBattleTypeFlags & BATTLE_TYPE_IS_MASTER)
            gBattleMainFunc = BeginBattleIntro;

        for (i = 0; i < MAX_LINK_PLAYERS; i++)
        {
            switch (gLinkPlayers[i].id)
            {
            case 0:
            case 3:
                BufferBattlePartyCurrentOrderBySide(gLinkPlayers[i].id, 0);
                break;
            case 1:
            case 2:
                BufferBattlePartyCurrentOrderBySide(gLinkPlayers[i].id, 1);
                break;
            }

            if (i == multiplayerId)
            {
                gBattlerControllerFuncs[gLinkPlayers[i].id] = SetControllerToPlayer;
                switch (gLinkPlayers[i].id)
                {
                case 0:
                case 3:
                    gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_LEFT;
                    gBattlerPartyIndexes[gLinkPlayers[i].id] = 0;
                    break;
                case 1:
                case 2:
                    gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_RIGHT;
                    gBattlerPartyIndexes[gLinkPlayers[i].id] = 3;
                    break;
                }
            }
            else
            {
                if ((!(gLinkPlayers[i].id & 1) && !(gLinkPlayers[multiplayerId].id & 1))
                 || ((gLinkPlayers[i].id & 1) && (gLinkPlayers[multiplayerId].id & 1)))
                {
                    gBattlerControllerFuncs[gLinkPlayers[i].id] = SetControllerToLinkPartner;
                    switch (gLinkPlayers[i].id)
                    {
                    case 0:
                    case 3:
                        gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_LEFT;
                        gBattlerPartyIndexes[gLinkPlayers[i].id] = 0;
                        break;
                    case 1:
                    case 2:
                        gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_PLAYER_RIGHT;
                        gBattlerPartyIndexes[gLinkPlayers[i].id] = 3;
                        break;
                    }
                }
                else
                {
                    gBattlerControllerFuncs[gLinkPlayers[i].id] = SetControllerToLinkOpponent;
                    switch (gLinkPlayers[i].id)
                    {
                    case 0:
                    case 3:
                        gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_OPPONENT_LEFT;
                        gBattlerPartyIndexes[gLinkPlayers[i].id] = 0;
                        break;
                    case 1:
                    case 2:
                        gBattlerPositions[gLinkPlayers[i].id] = B_POSITION_OPPONENT_RIGHT;
                        gBattlerPartyIndexes[gLinkPlayers[i].id] = 3;
                        break;
                    }
                }
            }
        }

        gBattlersCount = MAX_BATTLERS_COUNT;
    }
}

static void SetBattlePartyIds(void)
{
    s32 i, j;

    if (!(gBattleTypeFlags & BATTLE_TYPE_MULTI))
    {
        for (i = 0; i < gBattlersCount; i++)
        {
            for (j = 0; j < PARTY_SIZE; j++)
            {
                if (i < 2)
                {
                    if (GET_BATTLER_SIDE2(i) == B_SIDE_PLAYER)
                    {
                        if (GetMonData(&gPlayerParty[j], MON_DATA_HP) != 0
                         && GetMonData(&gPlayerParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_NONE
                         && GetMonData(&gPlayerParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_EGG
                         && !GetMonData(&gPlayerParty[j], MON_DATA_IS_EGG))
                        {
                            gBattlerPartyIndexes[i] = j;
                            break;
                        }
                    }
                    else
                    {
                        if (GetMonData(&gEnemyParty[j], MON_DATA_HP) != 0
                         && GetMonData(&gEnemyParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_NONE
                         && GetMonData(&gEnemyParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_EGG
                         && !GetMonData(&gEnemyParty[j], MON_DATA_IS_EGG))
                        {
                            gBattlerPartyIndexes[i] = j;
                            break;
                        }
                    }
                }
                else
                {
                    if (GET_BATTLER_SIDE2(i) == B_SIDE_PLAYER)
                    {
                        if (GetMonData(&gPlayerParty[j], MON_DATA_HP) != 0
                         && GetMonData(&gPlayerParty[j], MON_DATA_SPECIES) != SPECIES_NONE  // Probably a typo by Game Freak. The rest use SPECIES2.
                         && GetMonData(&gPlayerParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_EGG
                         && !GetMonData(&gPlayerParty[j], MON_DATA_IS_EGG)
                         && gBattlerPartyIndexes[i - 2] != j)
                        {
                            gBattlerPartyIndexes[i] = j;
                            break;
                        }
                    }
                    else
                    {
                        if (GetMonData(&gEnemyParty[j], MON_DATA_HP) != 0
                         && GetMonData(&gEnemyParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_NONE
                         && GetMonData(&gEnemyParty[j], MON_DATA_SPECIES_OR_EGG) != SPECIES_EGG
                         && !GetMonData(&gEnemyParty[j], MON_DATA_IS_EGG)
                         && gBattlerPartyIndexes[i - 2] != j)
                        {
                            gBattlerPartyIndexes[i] = j;
                            break;
                        }
                    }
                }
            }
        }

        if (gBattleTypeFlags & BATTLE_TYPE_TWO_OPPONENTS)
            gBattlerPartyIndexes[1] = 0, gBattlerPartyIndexes[3] = 3;
    }
}

static void PrepareBufferDataTransfer(u8 bufferId, u8 *data, u16 size)
{
    s32 i;

    if (gBattleTypeFlags & BATTLE_TYPE_LINK)
    {
        PrepareBufferDataTransferLink(bufferId, size, data);
    }
    else
    {
        switch (bufferId)
        {
        case B_COMM_TO_CONTROLLER:
            for (i = 0; i < size; data++, i++)
                gBattleBufferA[gActiveBattler][i] = *data;
            break;
        case B_COMM_TO_ENGINE:
            for (i = 0; i < size; data++, i++)
                gBattleBufferB[gActiveBattler][i] = *data;
            break;
        }
    }
}

#define tInitialDelayTimer      data[10]
#define tState                  data[11]
#define tCurrentBlock_WrapFrom  data[12]
#define tBlockSendDelayTimer    data[13]
#define tCurrentBlock_End       data[14]
#define tCurrentBlock_Start     data[15]
//
// Inbound communications are stored in one buffer; outbound communications
// in another. Both buffers work pretty similarly: the next message will be
// written into the buffer after the previous message (with 4-byte alignment),
// unless we're too close to the end of the buffer, in which case we jump back
// to the start.
//
// Regarding the task variable names above: these variables are altered in-
// place, so the precise operational definition of "current" depends on when
// the variables are being accessed. When data is present in the send and
// receive buffers, "current" refers to the most recently received message;
// but when a message is actually being placed in the buffers, "current"
// refers to the previous message, until such time that we finish updating it
// to refer to the new message.

static void CreateTasksForSendRecvLinkBuffers(void)
{
#ifdef PORTABLE
    sNativeBattlePayloadFailed = FALSE;
    memset(sNativeBattleReplyUsed, 0, sizeof(sNativeBattleReplyUsed));
    memset(sNativeBattleRequestPending, 0, sizeof(sNativeBattleRequestPending));
    memset(sNativeBattleRequest, 0, sizeof(sNativeBattleRequest));
#endif
    sLinkSendTaskId = CreateTask(Task_HandleSendLinkBuffersData, 0);
    gTasks[sLinkSendTaskId].tState                 = 0;
    gTasks[sLinkSendTaskId].tCurrentBlock_WrapFrom = 0;
    gTasks[sLinkSendTaskId].tBlockSendDelayTimer   = 0;
    gTasks[sLinkSendTaskId].tCurrentBlock_End      = 0;
    gTasks[sLinkSendTaskId].tCurrentBlock_Start    = 0;

    sLinkReceiveTaskId = CreateTask(Task_HandleCopyReceivedLinkBuffersData, 0);
    gTasks[sLinkReceiveTaskId].tCurrentBlock_WrapFrom = 0;
    gTasks[sLinkReceiveTaskId].tBlockSendDelayTimer   = 0; // not used by "receive" task
    gTasks[sLinkReceiveTaskId].tCurrentBlock_End      = 0;
    gTasks[sLinkReceiveTaskId].tCurrentBlock_Start    = 0;

    sUnused = 0;
}

enum
{
    LINK_BUFF_BUFFER_ID,
    LINK_BUFF_ACTIVE_BATTLER,
    LINK_BUFF_ATTACKER,
    LINK_BUFF_TARGET,
    LINK_BUFF_SIZE_LO,
    LINK_BUFF_SIZE_HI,
    LINK_BUFF_ABSENT_BATTLER_FLAGS,
    LINK_BUFF_EFFECT_BATTLER,
    LINK_BUFF_DATA,
};

/* Native battle payload boundary. */
#ifdef PORTABLE
/* The cable adapter owns the completed block's length, not its payload. */
extern u16 GetBlockReceivedSize(u8 player);
/* Side metadata never changes the cable wire layout or FIFO record lengths. */
static u8 sNativeBattleSources[BATTLE_BUFFER_LINK_SIZE];

static u8 NativeBattleMaster(void)
{
    u8 local = GetMultiplayerId();
    return (gBattleTypeFlags & BATTLE_TYPE_IS_MASTER) ? local : local ^ 1;
}

static u8 NativeBattleOwner(u8 battler)
{
    if (WorldCoop_IsBattle() || (gBattleTypeFlags & BATTLE_TYPE_BATTLE_TOWER))
        return battler == 2 ? 1 : 0;
    return NativeBattleMaster() ^ (battler & BIT_SIDE);
}

static bool8 NativeBattleSourceValid(const u8 *packet, u8 source)
{
    if (GetLinkPlayerCount() != 2 || source >= 2)
        return FALSE;
    switch (packet[LINK_BUFF_BUFFER_ID])
    {
    case B_COMM_TO_CONTROLLER:
        return source == NativeBattleMaster();
    case B_COMM_TO_ENGINE:
        return source == NativeBattleOwner(packet[LINK_BUFF_ACTIVE_BATTLER]);
    case B_COMM_CONTROLLER_IS_DONE:
        return packet[LINK_BUFF_DATA] == source;
    }
    return FALSE;
}

static void AbortNativeBattlePayload(void)
{
    sNativeBattlePayloadFailed = TRUE;
    NativeLink_Abort();
    gLinkErrorOccurred = TRUE;
}

static bool8 NativeBattleCommandValid(const u8 *data, u16 size, u8 bufferId)
{
    u16 needed = 4;
    u16 count, pos;
    if (size < 4 || data[0] >= CONTROLLER_CMDS_COUNT)
        return FALSE;
    switch (data[0])
    {
    case CONTROLLER_GETMONDATA:
    case CONTROLLER_SETMONDATA:
        if (data[1] > REQUEST_TOUGH_RIBBON_BATTLE || data[2] >= (1 << PARTY_SIZE))
            return FALSE;
        if (data[0] == CONTROLLER_GETMONDATA && data[1] == REQUEST_ALL_BATTLE)
        {
            u8 mask = data[2];
            count = mask == 0;
            while (mask)
            {
                count += mask & 1;
                mask >>= 1;
            }
            /* DataTransfer adds four bytes plus 1..4 bytes of padding. */
            if (count * sizeof(struct BattlePokemon) > 236)
                return FALSE;
        }
        if (data[0] == CONTROLLER_SETMONDATA)
        {
            /* SetMonData reads these widths, independently of the wire length. */
            needed = 4;
            if (data[1] == REQUEST_ALL_BATTLE)
                needed = 3 + sizeof(struct BattlePokemon);
            else if (data[1] == REQUEST_MOVES_PP_BATTLE)
                needed = 16;
            else if (data[1] == REQUEST_PP_DATA_BATTLE)
                needed = 8;
            else if (data[1] == REQUEST_ALL_IVS_BATTLE)
                needed = 9;
            else if (data[1] == REQUEST_OTID_BATTLE || data[1] == REQUEST_EXP_BATTLE
                  || data[1] == REQUEST_PERSONALITY_BATTLE || data[1] == REQUEST_STATUS_BATTLE)
                needed = 7;
            else if (data[1] == REQUEST_SPECIES_BATTLE || data[1] == REQUEST_HELDITEM_BATTLE
                  || (data[1] >= REQUEST_MOVE1_BATTLE && data[1] <= REQUEST_MOVE4_BATTLE)
                  || data[1] == REQUEST_CHECKSUM_BATTLE
                  || (data[1] >= REQUEST_HP_BATTLE && data[1] <= REQUEST_SPDEF_BATTLE))
                needed = 5;
        }
        break;
    case CONTROLLER_GETRAWMONDATA:
    case CONTROLLER_SETRAWMONDATA:
        /* GET also writes a local BattlePokemon, smaller than a party mon. */
        if ((u16)data[1] + data[2] > (data[0] == CONTROLLER_GETRAWMONDATA
                ? sizeof(struct BattlePokemon) : sizeof(gPlayerParty[0])))
            return FALSE;
        if (data[0] == CONTROLLER_SETRAWMONDATA)
            needed = 3 + data[2];
        break;
    case CONTROLLER_SWITCHINANIM:
    case CONTROLLER_EXPUPDATE:
#ifdef PORTABLE
        if (data[0] == CONTROLLER_EXPUPDATE && WorldCoop_IsBattle())
            return WorldCoop_RewardPacketValid(data, size);
#endif
        if (data[1] >= PARTY_SIZE)
            return FALSE;
        break;
    case CONTROLLER_MOVEANIMATION:
        needed = 16 + sizeof(struct DisableStruct);
        if ((data[1] | (data[2] << 8)) >= MOVES_COUNT)
            return FALSE;
        break;
    case CONTROLLER_PRINTSTRING:
    case CONTROLLER_PRINTSTRINGPLAYERONLY:
        needed = 4 + sizeof(struct BattleMsgData);
        break;
    case CONTROLLER_CHOOSEMOVE:
        needed = 4 + sizeof(struct ChooseMoveStruct);
        break;
    case CONTROLLER_CHOOSEPOKEMON:
        needed = 8;
        break;
    case CONTROLLER_STATUSICONUPDATE:
        needed = 9;
        break;
    case CONTROLLER_STATUSANIMATION:
        needed = 6;
        break;
    case CONTROLLER_DATATRANSFER:
        needed = 4 + (data[2] | (data[3] << 8));
        if (needed < 4)
            return FALSE;
        break;
    case CONTROLLER_DMA3TRANSFER:
        /* An address from another process is never a native destination. */
        return FALSE;
    case CONTROLLER_PAUSE:
        needed = 2 + data[1] * 3;
        break;
    case CONTROLLER_32:
        needed = 3 + (data[1] | (data[2] << 8));
        if (needed < 3)
            return FALSE;
        break;
    case CONTROLLER_CHOSENMONRETURNVALUE:
        needed = 5;
        /* PARTY_SIZE is the cancel sentinel. */
        if (data[1] > PARTY_SIZE)
            return FALSE;
        break;
    case CONTROLLER_TWORETURNVALUES:
        if (bufferId == B_COMM_TO_ENGINE
            && (data[1] > B_ACTION_UNK_14
                || ((data[1] == B_ACTION_USE_MOVE || data[1] == B_ACTION_EXEC_SCRIPT)
                    && !(data[2] == 0xFF && data[3] == 0xFF)
                    && (data[2] >= MAX_MON_MOVES || data[3] >= MAX_BATTLERS_COUNT))))
            return FALSE;
        break;
    case CONTROLLER_DRAWPARTYSTATUSSUMMARY:
        needed = 4 + sizeof(struct HpAndStatus) * PARTY_SIZE;
        break;
    case CONTROLLER_LINKSTANDBYMSG:
    case CONTROLLER_ENDLINKBATTLE:
        pos = data[0] == CONTROLLER_LINKSTANDBYMSG ? 2 : 4;
        if (size <= pos + 2 || data[pos] != data[pos + 1])
            return FALSE;
        count = data[pos];
        needed = pos + 2 + count;
        if (needed >= size)
            return FALSE;
        pos += 2;
        while (count)
        {
            u16 actions;
            if (count < 2 || data[pos] >= MAX_BATTLERS_COUNT)
                return FALSE;
            actions = data[pos + 1];
            if (actions > count - 2)
                return FALSE;
            count -= actions + 2;
            pos += actions + 2;
        }
        break;
    case CONTROLLER_RETURNMONTOBALL:
    case CONTROLLER_BALLTHROWANIM:
    case CONTROLLER_STATUSXOR:
    case CONTROLLER_RESETACTIONMOVESELECTION:
    case CONTROLLER_INTROSLIDE:
    case CONTROLLER_SETUNKVAR:
        needed = 2;
        break;
    }
    /* The native sender always adds 1..4 bytes of alignment padding. */
    return needed < size;
}

static bool8 NativeBattleHeaderValid(const u8 *packet, u16 size)
{
    return size >= LINK_BUFF_DATA + 4 && size <= 252
        && (size % 4) == 0
        && packet[LINK_BUFF_BUFFER_ID] <= B_COMM_CONTROLLER_IS_DONE
        && packet[LINK_BUFF_ACTIVE_BATTLER] < MAX_BATTLERS_COUNT
        && packet[LINK_BUFF_ATTACKER] < MAX_BATTLERS_COUNT
        && packet[LINK_BUFF_TARGET] < MAX_BATTLERS_COUNT
        && packet[LINK_BUFF_EFFECT_BATTLER] < MAX_BATTLERS_COUNT
        && packet[LINK_BUFF_ABSENT_BATTLER_FLAGS] < (1 << MAX_BATTLERS_COUNT)
        && (packet[LINK_BUFF_SIZE_LO] | (packet[LINK_BUFF_SIZE_HI] << 8)) == size - LINK_BUFF_DATA
        /* Completion callers send four bytes, padded to eight by the sender. */
        && (packet[LINK_BUFF_BUFFER_ID] == B_COMM_CONTROLLER_IS_DONE
            ? (size == LINK_BUFF_DATA + 8 && packet[LINK_BUFF_DATA] < GetLinkPlayerCount())
            : NativeBattleCommandValid(packet + LINK_BUFF_DATA, size - LINK_BUFF_DATA, packet[LINK_BUFF_BUFFER_ID]));
}

/* Only REQUEST_ALL_BATTLE is used by the native link engine. Validate it
 * against the outstanding command before an untrusted byte reaches buffer B.
 * Controller-only fields in BattlePokemon are uninitialized on the cable, so
 * do not inspect statStages/types/ability/status2 in this data-only response. */
static bool8 NativeBattleMonValid(const u8 *data)
{
    struct BattlePokemon mon;
    u8 i;
    memcpy(&mon, data, sizeof(mon));
    if (!mon.species || mon.species >= NUM_SPECIES || mon.item >= ITEMS_COUNT
     || !mon.level || mon.level > MAX_LEVEL || mon.experience > 1640000
     || !mon.maxHP || mon.maxHP > 999 || mon.hp > mon.maxHP
     || !mon.attack || mon.attack > 999 || !mon.defense || mon.defense > 999
     || !mon.speed || mon.speed > 999 || !mon.spAttack || mon.spAttack > 999
     || !mon.spDefense || mon.spDefense > 999 || (mon.status1 & ~0xFFFu) || mon.isEgg)
        return FALSE;
    for (i = 0; i < MAX_MON_MOVES; i++)
        if (mon.moves[i] >= MOVES_COUNT || mon.pp[i] > 64)
            return FALSE;
    return TRUE;
}

static bool8 NativeBattleReplyValid(u8 battler, const u8 *data)
{
    const u8 *request = sNativeBattleRequest[battler];
    u16 count = 0, i, mask;
    if (!sNativeBattleRequestPending[battler] || sNativeBattleReplyUsed[battler])
        return FALSE;
    switch (data[0])
    {
    case CONTROLLER_DATATRANSFER:
        if (request[0] != CONTROLLER_GETMONDATA || request[1] != REQUEST_ALL_BATTLE)
            return FALSE;
        mask = request[2];
        if (!mask)
            count = 1;
        for (; mask; mask >>= 1)
            count += mask & 1;
        if ((data[2] | (data[3] << 8)) != count * sizeof(struct BattlePokemon))
            return FALSE;
        for (i = 0; i < count; i++)
            if (!NativeBattleMonValid(data + 4 + i * sizeof(struct BattlePokemon)))
                return FALSE;
        return TRUE;
    case CONTROLLER_CHOSENMONRETURNVALUE:
        if (request[0] != CONTROLLER_CHOOSEPOKEMON
         || (WorldCoop_IsBattle() && !(battler & BIT_SIDE) && data[1] < PARTY_SIZE
             && data[1] / MULTI_PARTY_SIZE != NativeBattleOwner(battler)))
            return FALSE;
        mask = 0;
        for (i = 0; i < PARTY_SIZE; i++)
        {
            u8 slot = (data[2 + i / 2] >> ((i % 2) * 4)) & 15;
            if (slot >= PARTY_SIZE || (mask & (1 << slot)))
                return FALSE;
            mask |= 1 << slot;
        }
        return TRUE;
    case CONTROLLER_TWORETURNVALUES:
        return request[0] == CONTROLLER_CHOOSEACTION || request[0] == CONTROLLER_CHOOSEMOVE
            || request[0] == CONTROLLER_EXPUPDATE || request[0] == CONTROLLER_DRAWPARTYSTATUSSUMMARY;
    case CONTROLLER_ONERETURNVALUE:
    case CONTROLLER_ONERETURNVALUE_DUPLICATE:
        return request[0] == CONTROLLER_OPENBAG && (data[1] | (data[2] << 8)) < ITEMS_COUNT;
    }
    return FALSE;
}

static bool8 NativeBattleRingStateValid(u8 taskId)
{
    return gTasks[taskId].tCurrentBlock_Start >= 0
        && gTasks[taskId].tCurrentBlock_Start < BATTLE_BUFFER_LINK_SIZE
        && gTasks[taskId].tCurrentBlock_End >= 0
        && gTasks[taskId].tCurrentBlock_End < BATTLE_BUFFER_LINK_SIZE
        && gTasks[taskId].tCurrentBlock_WrapFrom >= 0
        && gTasks[taskId].tCurrentBlock_WrapFrom < BATTLE_BUFFER_LINK_SIZE;
}
#endif
/* End native battle payload boundary. */

// We want to send a message. Place it into the "send" buffer.
// First argument is a BATTLELINKCOMMTYPE_...
void PrepareBufferDataTransferLink(u8 bufferId, u16 size, u8 *data)
{
    s32 alignedSize;
    s32 i;

#ifdef PORTABLE
    /* Mirror controllers still ACK animations, but only the battler owner can
     * answer the engine. In PvP both mirrors historically emitted mon data. */
    if (NativeLink_IsActive() && bufferId == B_COMM_TO_ENGINE
     && GetMultiplayerId() != NativeBattleOwner(gActiveBattler))
        return;
#endif
    alignedSize = size - size % 4 + 4;
    if (gTasks[sLinkSendTaskId].tCurrentBlock_End + alignedSize + LINK_BUFF_DATA + 1 > BATTLE_BUFFER_LINK_SIZE)
    {
        gTasks[sLinkSendTaskId].tCurrentBlock_WrapFrom = gTasks[sLinkSendTaskId].tCurrentBlock_End;
        gTasks[sLinkSendTaskId].tCurrentBlock_End      = 0;
    }

    #define BYTE_TO_SEND(offset) \
        gLinkBattleSendBuffer[gTasks[sLinkSendTaskId].tCurrentBlock_End + offset]

    BYTE_TO_SEND(LINK_BUFF_BUFFER_ID)            = bufferId;
    BYTE_TO_SEND(LINK_BUFF_ACTIVE_BATTLER)       = gActiveBattler;
    BYTE_TO_SEND(LINK_BUFF_ATTACKER)             = gBattlerAttacker;
    BYTE_TO_SEND(LINK_BUFF_TARGET)               = gBattlerTarget;
    BYTE_TO_SEND(LINK_BUFF_SIZE_LO)              = alignedSize;
    BYTE_TO_SEND(LINK_BUFF_SIZE_HI)              = (alignedSize & 0x0000FF00) >> 8;
    BYTE_TO_SEND(LINK_BUFF_ABSENT_BATTLER_FLAGS) = gAbsentBattlerFlags;
    BYTE_TO_SEND(LINK_BUFF_EFFECT_BATTLER)       = gEffectBattler;

#ifdef PORTABLE
    if (bufferId == B_COMM_CONTROLLER_IS_DONE)
    {
        /* Stock completion passes one player-id byte with a four-byte cable
         * width. The remaining bytes are padding, not readable stack data. */
        BYTE_TO_SEND(LINK_BUFF_DATA) = data[0];
        for (i = 1; i < alignedSize; i++)
            BYTE_TO_SEND(LINK_BUFF_DATA + i) = 0;
    }
    else
#endif
    for (i = 0; i < size; i++)
        BYTE_TO_SEND(LINK_BUFF_DATA + i) = data[i];

#ifdef PORTABLE
    if (WorldCoop_IsBattle())
        for (; i < alignedSize; i++)
            BYTE_TO_SEND(LINK_BUFF_DATA + i) = 0;
#endif
    #undef BYTE_TO_SEND

    gTasks[sLinkSendTaskId].tCurrentBlock_End = gTasks[sLinkSendTaskId].tCurrentBlock_End + alignedSize + LINK_BUFF_DATA;
}

enum {
   SENDTASK_STATE_INITIALIZE        = 0,
   SENDTASK_STATE_INITIAL_DELAY     = 1,
   SENDTASK_STATE_COUNT_PLAYERS     = 2,
   SENDTASK_STATE_BEGIN_SEND_BLOCK  = 3,
   SENDTASK_STATE_FINISH_SEND_BLOCK = 4,
   SENDTASK_STATE_UNUSED_STATE      = 5,
};

static void Task_HandleSendLinkBuffersData(u8 taskId)
{
    u16 numPlayers;
    u16 blockSize;

    #define BYTE_TO_SEND(offset) \
        gLinkBattleSendBuffer[gTasks[taskId].tCurrentBlock_Start + offset]

    switch (gTasks[taskId].tState)
    {
    case SENDTASK_STATE_INITIALIZE:
        gTasks[taskId].tInitialDelayTimer = 100;
        gTasks[taskId].tState++;
        break;
    case SENDTASK_STATE_INITIAL_DELAY:
        gTasks[taskId].tInitialDelayTimer--;
        if (gTasks[taskId].tInitialDelayTimer == 0)
            gTasks[taskId].tState++;
        break;
    case SENDTASK_STATE_COUNT_PLAYERS:
        if (gWirelessCommType)
        {
            gTasks[taskId].tState++;
        }
        else
        {
            if (gBattleTypeFlags & BATTLE_TYPE_BATTLE_TOWER
#ifdef PORTABLE
                || WorldCoop_IsBattle()
#endif
               )
                numPlayers = 2;
            else
                numPlayers = (gBattleTypeFlags & BATTLE_TYPE_MULTI) ? 4 : 2;

            if (GetLinkPlayerCount_2() >= numPlayers)
            {
                if (IsLinkMaster())
                {
                    CheckShouldAdvanceLinkState();
                    gTasks[taskId].tState++;
                }
                else
                {
                    gTasks[taskId].tState++;
                }
            }
        }
        break;
    case SENDTASK_STATE_BEGIN_SEND_BLOCK:
        if (gTasks[taskId].tCurrentBlock_Start != gTasks[taskId].tCurrentBlock_End)
        {
            if (gTasks[taskId].tBlockSendDelayTimer == 0)
            {
                if (gTasks[taskId].tCurrentBlock_Start >  gTasks[taskId].tCurrentBlock_End
                 && gTasks[taskId].tCurrentBlock_Start == gTasks[taskId].tCurrentBlock_WrapFrom)
                {
                    gTasks[taskId].tCurrentBlock_WrapFrom = 0;
                    gTasks[taskId].tCurrentBlock_Start    = 0;
                }
                blockSize = (BYTE_TO_SEND(LINK_BUFF_SIZE_LO) | (BYTE_TO_SEND(LINK_BUFF_SIZE_HI) << 8)) + LINK_BUFF_DATA;
#ifdef PORTABLE
                /* A busy sender has not accepted this FIFO record. Keep its
                 * head until the block belongs to this controller command. */
                if (NativeLink_IsActive())
                {
                    if (!SendBlock(BitmaskAllOtherLinkPlayers(), &BYTE_TO_SEND(0), blockSize))
                        break;
                }
                else
#endif
                    SendBlock(BitmaskAllOtherLinkPlayers(), &BYTE_TO_SEND(0), blockSize);
                gTasks[taskId].tState++;
            }
            else
            {
                gTasks[taskId].tBlockSendDelayTimer--;
                break;
            }
        }
        break;
    case SENDTASK_STATE_FINISH_SEND_BLOCK:
        if (IsLinkTaskFinished())
        {
            blockSize = BYTE_TO_SEND(LINK_BUFF_SIZE_LO) | (BYTE_TO_SEND(LINK_BUFF_SIZE_HI) << 8);
            gTasks[taskId].tBlockSendDelayTimer = 1;
            gTasks[taskId].tCurrentBlock_Start  = gTasks[taskId].tCurrentBlock_Start + blockSize + LINK_BUFF_DATA;
            gTasks[taskId].tState = SENDTASK_STATE_BEGIN_SEND_BLOCK;
        }
        break;
    case SENDTASK_STATE_UNUSED_STATE:
        if (--gTasks[taskId].tBlockSendDelayTimer == 0)
        {
            gTasks[taskId].tBlockSendDelayTimer = 1;
            gTasks[taskId].tState = SENDTASK_STATE_BEGIN_SEND_BLOCK;
        }
        break;
    }

    #undef BYTE_TO_SEND
}

// We have received a message. Place it into the "receive" buffer.
//
// Counterintuitively, we also "receive" the outbound messages that
// we send to other players. The GBA basically stores communicated
// data for all four players, so inbound and outbound data can be
// handled uniformly unless a game specifically decides to do
// otherwise. Pokemon, evidently, did not specifically decide to do
// otherwise.
void TryReceiveLinkBattleData(void)
{
    u8 i;
    s32 j;
    u8 *recvBuffer;

#ifdef PORTABLE
    if (sNativeBattlePayloadFailed)
        return;
    if (NativeLink_IsActive() && gReceivedRemoteLinkPlayers && (gBattleTypeFlags & BATTLE_TYPE_LINK_IN_BATTLE))
    {
        u16 start, end, wrap, size;
        if (GetLinkPlayerCount() > MAX_LINK_PLAYERS || !NativeBattleRingStateValid(sLinkReceiveTaskId))
        {
            AbortNativeBattlePayload();
            return;
        }
        for (i = 0; i < GetLinkPlayerCount(); i++)
        {
            if (!(GetBlockReceivedStatus() & gBitTable[i]))
                continue;
            size = GetBlockReceivedSize(i);
            if (size < LINK_BUFF_DATA || size > 252)
            {
                AbortNativeBattlePayload();
                return;
            }
            recvBuffer = (u8 *)gBlockRecvBuffer[i];
            {
                int completion = WorldCoop_ReceiveCompletion(recvBuffer, size, i);
                if (completion < 0)
                {
                    AbortNativeBattlePayload();
                    return;
                }
                if (completion)
                {
                    ResetBlockReceivedFlag(i);
                    continue;
                }
            }
            if (!NativeBattleHeaderValid(recvBuffer, size) || !NativeBattleSourceValid(recvBuffer, i))
            {
                AbortNativeBattlePayload();
                return;
            }
            start = gTasks[sLinkReceiveTaskId].tCurrentBlock_Start;
            end = gTasks[sLinkReceiveTaskId].tCurrentBlock_End;
            wrap = gTasks[sLinkReceiveTaskId].tCurrentBlock_WrapFrom;
            if (end + size + 1 > BATTLE_BUFFER_LINK_SIZE)
            {
                if (end < start || (start != end && size >= start))
                {
                    AbortNativeBattlePayload();
                    return;
                }
                wrap = end;
                end = 0;
            }
            else if (end < start && end + size >= start)
            {
                AbortNativeBattlePayload();
                return;
            }
            memcpy(&gLinkBattleRecvBuffer[end], recvBuffer, size);
            sNativeBattleSources[end] = i;
            gTasks[sLinkReceiveTaskId].tCurrentBlock_WrapFrom = wrap;
            gTasks[sLinkReceiveTaskId].tCurrentBlock_End = end + size;
            ResetBlockReceivedFlag(i);
        }
        return;
    }
#endif

    if (gReceivedRemoteLinkPlayers && (gBattleTypeFlags & BATTLE_TYPE_LINK_IN_BATTLE))
    {
        DestroyTask_RfuIdle();
        for (i = 0; i < GetLinkPlayerCount(); i++)
        {
            if (GetBlockReceivedStatus() & gBitTable[i])
            {
                ResetBlockReceivedFlag(i);
                recvBuffer = (u8 *)gBlockRecvBuffer[i];
                {
                    u8 *dest, *src;
                    u16 dataSize = gBlockRecvBuffer[i][2];

                    if (gTasks[sLinkReceiveTaskId].tCurrentBlock_End + 9 + dataSize > 0x1000)
                    {
                        gTasks[sLinkReceiveTaskId].tCurrentBlock_WrapFrom = gTasks[sLinkReceiveTaskId].tCurrentBlock_End;
                        gTasks[sLinkReceiveTaskId].tCurrentBlock_End = 0;
                    }

                    dest = &gLinkBattleRecvBuffer[gTasks[sLinkReceiveTaskId].tCurrentBlock_End];
                    src = recvBuffer;

                    for (j = 0; j < dataSize + 8; j++)
                        dest[j] = src[j];

                    gTasks[sLinkReceiveTaskId].tCurrentBlock_End = gTasks[sLinkReceiveTaskId].tCurrentBlock_End + dataSize + 8;
                }
            }
        }
    }
}

static void Task_HandleCopyReceivedLinkBuffersData(u8 taskId)
{
    u16 blockSize;
    u8 battler;
    u8 playerId;

    #define BYTE_TO_RECEIVE(offset) \
        gLinkBattleRecvBuffer[gTasks[taskId].tCurrentBlock_Start + offset]

#ifdef PORTABLE
    if (sNativeBattlePayloadFailed)
        return;
    if (NativeLink_IsActive())
    {
        u16 start, end, limit;
        if (!NativeBattleRingStateValid(taskId))
        {
            AbortNativeBattlePayload();
            return;
        }
        start = gTasks[taskId].tCurrentBlock_Start;
        end = gTasks[taskId].tCurrentBlock_End;
        if (start == end)
            return;
        limit = end;
        if (start > end)
        {
            limit = gTasks[taskId].tCurrentBlock_WrapFrom;
            if (start > limit)
            {
                AbortNativeBattlePayload();
                return;
            }
            if (start == limit)
            {
                start = 0;
                limit = end;
            }
        }
        if (limit - start < LINK_BUFF_DATA)
        {
            AbortNativeBattlePayload();
            return;
        }
        blockSize = gLinkBattleRecvBuffer[start + LINK_BUFF_SIZE_LO]
                  | (gLinkBattleRecvBuffer[start + LINK_BUFF_SIZE_HI] << 8);
        if (blockSize > limit - start - LINK_BUFF_DATA
            || !NativeBattleHeaderValid(&gLinkBattleRecvBuffer[start], blockSize + LINK_BUFF_DATA)
            || !NativeBattleSourceValid(&gLinkBattleRecvBuffer[start], sNativeBattleSources[start]))
        {
            AbortNativeBattlePayload();
            return;
        }
        /* Commit the wrap only after validating the entire queued record. */
        if (start != gTasks[taskId].tCurrentBlock_Start)
        {
            gTasks[taskId].tCurrentBlock_Start = start;
            gTasks[taskId].tCurrentBlock_WrapFrom = 0;
        }
    }
#endif

    if (gTasks[taskId].tCurrentBlock_Start != gTasks[taskId].tCurrentBlock_End)
    {
        if (gTasks[taskId].tCurrentBlock_Start >  gTasks[taskId].tCurrentBlock_End
         && gTasks[taskId].tCurrentBlock_Start == gTasks[taskId].tCurrentBlock_WrapFrom)
        {
            gTasks[taskId].tCurrentBlock_WrapFrom = 0;
            gTasks[taskId].tCurrentBlock_Start    = 0;
        }
        battler = BYTE_TO_RECEIVE(LINK_BUFF_ACTIVE_BATTLER);
        blockSize = BYTE_TO_RECEIVE(LINK_BUFF_SIZE_LO) | (BYTE_TO_RECEIVE(LINK_BUFF_SIZE_HI) << 8);

        switch (BYTE_TO_RECEIVE(0))
        {
        case B_COMM_TO_CONTROLLER:
            if (IS_BATTLE_CONTROLLER_ACTIVE_ON_LOCAL(battler))
                return;

#ifdef PORTABLE
            if (NativeLink_IsActive())
            {
                sNativeBattleReplyUsed[battler] = FALSE;
                sNativeBattleRequestPending[battler] = TRUE;
                memcpy(sNativeBattleRequest[battler], &BYTE_TO_RECEIVE(LINK_BUFF_DATA),
                    sizeof(sNativeBattleRequest[battler]));
            }
#endif
            memcpy(gBattleBufferA[battler], &BYTE_TO_RECEIVE(LINK_BUFF_DATA), blockSize);
            MarkBattlerReceivedLinkData(battler);

            if (!(gBattleTypeFlags & BATTLE_TYPE_IS_MASTER))
            {
                gBattlerAttacker    = BYTE_TO_RECEIVE(LINK_BUFF_ATTACKER);
                gBattlerTarget      = BYTE_TO_RECEIVE(LINK_BUFF_TARGET);
                gAbsentBattlerFlags = BYTE_TO_RECEIVE(LINK_BUFF_ABSENT_BATTLER_FLAGS);
                gEffectBattler      = BYTE_TO_RECEIVE(LINK_BUFF_EFFECT_BATTLER);
            }
#ifdef PORTABLE
            if (NativeLink_IsActive() && WorldCoop_IsBattle())
                WorldCoop_ObserveController(battler, &BYTE_TO_RECEIVE(LINK_BUFF_DATA));
#endif
            break;
        case B_COMM_TO_ENGINE:
#ifdef PORTABLE
            if (NativeLink_IsActive())
            {
                if (!NativeBattleReplyValid(battler, &BYTE_TO_RECEIVE(LINK_BUFF_DATA)))
                {
                    AbortNativeBattlePayload();
                    return;
                }
                sNativeBattleReplyUsed[battler] = TRUE;
                if (WorldCoop_IsBattle()
                 && BYTE_TO_RECEIVE(LINK_BUFF_DATA) == CONTROLLER_DATATRANSFER
                 && sNativeBattleRequest[battler][0] == CONTROLLER_GETMONDATA
                 && sNativeBattleRequest[battler][1] == REQUEST_ALL_BATTLE)
                {
                    u8 mask = sNativeBattleRequest[battler][2];
                    /* Reserve batches are not public selected-battler data. */
                    if (mask == 0 || (mask & (mask - 1)) == 0)
                    {
                        struct BattlePokemon mon;
                        u8 slot = gBattlerPartyIndexes[battler];
                        if (mask)
                            for (slot = 0; !(mask & (1u << slot)); slot++);
                        memcpy(&mon, &BYTE_TO_RECEIVE(LINK_BUFF_DATA + 4), sizeof(mon));
                        WorldCoop_ObserveMonData(battler, slot, &mon);
                    }
                }
            }
#endif
            memcpy(gBattleBufferB[battler], &gLinkBattleRecvBuffer[gTasks[taskId].tCurrentBlock_Start + LINK_BUFF_DATA], blockSize);
            break;
        case B_COMM_CONTROLLER_IS_DONE:
            playerId = BYTE_TO_RECEIVE(LINK_BUFF_DATA);
            MARK_BATTLE_CONTROLLER_IDLE_FOR_PLAYER(battler, playerId);
            break;
        }

        gTasks[taskId].tCurrentBlock_Start = gTasks[taskId].tCurrentBlock_Start + blockSize + LINK_BUFF_DATA;
    }

    #undef BYTE_TO_RECEIVE
}

#undef tInitialDelayTimer
#undef tState
#undef tCurrentBlock_WrapFrom
#undef tBlockSendDelayTimer
#undef tCurrentBlock_End
#undef tCurrentBlock_Start

void BtlController_EmitGetMonData(u8 bufferId, u8 requestId, u8 monToCheck)
{
    sBattleBuffersTransferData[0] = CONTROLLER_GETMONDATA;
    sBattleBuffersTransferData[1] = requestId;
    sBattleBuffersTransferData[2] = monToCheck;
    sBattleBuffersTransferData[3] = 0;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

static void UNUSED BtlController_EmitGetRawMonData(u8 bufferId, u8 monId, u8 bytes)
{
    sBattleBuffersTransferData[0] = CONTROLLER_GETRAWMONDATA;
    sBattleBuffersTransferData[1] = monId;
    sBattleBuffersTransferData[2] = bytes;
    sBattleBuffersTransferData[3] = 0;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitSetMonData(u8 bufferId, u8 requestId, u8 monToCheck, u8 bytes, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_SETMONDATA;
    sBattleBuffersTransferData[1] = requestId;
    sBattleBuffersTransferData[2] = monToCheck;
    for (i = 0; i < bytes; i++)
        sBattleBuffersTransferData[3 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 3 + bytes);
}

static void UNUSED BtlController_EmitSetRawMonData(u8 bufferId, u8 monId, u8 bytes, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_SETRAWMONDATA;
    sBattleBuffersTransferData[1] = monId;
    sBattleBuffersTransferData[2] = bytes;
    for (i = 0; i < bytes; i++)
        sBattleBuffersTransferData[3 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, bytes + 3);
}

void BtlController_EmitLoadMonSprite(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_LOADMONSPRITE;
    sBattleBuffersTransferData[1] = CONTROLLER_LOADMONSPRITE;
    sBattleBuffersTransferData[2] = CONTROLLER_LOADMONSPRITE;
    sBattleBuffersTransferData[3] = CONTROLLER_LOADMONSPRITE;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitSwitchInAnim(u8 bufferId, u8 partyId, bool8 dontClearSubstituteBit)
{
    sBattleBuffersTransferData[0] = CONTROLLER_SWITCHINANIM;
    sBattleBuffersTransferData[1] = partyId;
    sBattleBuffersTransferData[2] = dontClearSubstituteBit;
    sBattleBuffersTransferData[3] = 5;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitReturnMonToBall(u8 bufferId, bool8 skipAnim)
{
    sBattleBuffersTransferData[0] = CONTROLLER_RETURNMONTOBALL;
    sBattleBuffersTransferData[1] = skipAnim;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 2);
}

void BtlController_EmitDrawTrainerPic(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_DRAWTRAINERPIC;
    sBattleBuffersTransferData[1] = CONTROLLER_DRAWTRAINERPIC;
    sBattleBuffersTransferData[2] = CONTROLLER_DRAWTRAINERPIC;
    sBattleBuffersTransferData[3] = CONTROLLER_DRAWTRAINERPIC;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitTrainerSlide(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_TRAINERSLIDE;
    sBattleBuffersTransferData[1] = CONTROLLER_TRAINERSLIDE;
    sBattleBuffersTransferData[2] = CONTROLLER_TRAINERSLIDE;
    sBattleBuffersTransferData[3] = CONTROLLER_TRAINERSLIDE;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitTrainerSlideBack(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_TRAINERSLIDEBACK;
    sBattleBuffersTransferData[1] = CONTROLLER_TRAINERSLIDEBACK;
    sBattleBuffersTransferData[2] = CONTROLLER_TRAINERSLIDEBACK;
    sBattleBuffersTransferData[3] = CONTROLLER_TRAINERSLIDEBACK;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitFaintAnimation(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_FAINTANIMATION;
    sBattleBuffersTransferData[1] = CONTROLLER_FAINTANIMATION;
    sBattleBuffersTransferData[2] = CONTROLLER_FAINTANIMATION;
    sBattleBuffersTransferData[3] = CONTROLLER_FAINTANIMATION;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

static void UNUSED BtlController_EmitPaletteFade(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_PALETTEFADE;
    sBattleBuffersTransferData[1] = CONTROLLER_PALETTEFADE;
    sBattleBuffersTransferData[2] = CONTROLLER_PALETTEFADE;
    sBattleBuffersTransferData[3] = CONTROLLER_PALETTEFADE;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

static void UNUSED BtlController_EmitSuccessBallThrowAnim(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_SUCCESSBALLTHROWANIM;
    sBattleBuffersTransferData[1] = CONTROLLER_SUCCESSBALLTHROWANIM;
    sBattleBuffersTransferData[2] = CONTROLLER_SUCCESSBALLTHROWANIM;
    sBattleBuffersTransferData[3] = CONTROLLER_SUCCESSBALLTHROWANIM;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitBallThrowAnim(u8 bufferId, u8 caseId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_BALLTHROWANIM;
    sBattleBuffersTransferData[1] = caseId;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 2);
}

static void UNUSED BtlController_EmitPause(u8 bufferId, u8 toWait, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_PAUSE;
    sBattleBuffersTransferData[1] = toWait;
    for (i = 0; i < toWait * 3; i++)
        sBattleBuffersTransferData[2 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, toWait * 3 + 2);
}

void BtlController_EmitMoveAnimation(u8 bufferId, u16 move, u8 turnOfMove, u16 movePower, s32 dmg, u8 friendship, struct DisableStruct *disableStructPtr, u8 multihit)
{
    sBattleBuffersTransferData[0] = CONTROLLER_MOVEANIMATION;
    sBattleBuffersTransferData[1] = move;
    sBattleBuffersTransferData[2] = (move & 0xFF00) >> 8;
    sBattleBuffersTransferData[3] = turnOfMove;
    sBattleBuffersTransferData[4] = movePower;
    sBattleBuffersTransferData[5] = (movePower & 0xFF00) >> 8;
    sBattleBuffersTransferData[6] = dmg;
    sBattleBuffersTransferData[7] = (dmg & 0x0000FF00) >> 8;
    sBattleBuffersTransferData[8] = (dmg & 0x00FF0000) >> 16;
    sBattleBuffersTransferData[9] = (dmg & 0xFF000000) >> 24;
    sBattleBuffersTransferData[10] = friendship;
    sBattleBuffersTransferData[11] = multihit;
    if (WEATHER_HAS_EFFECT2)
    {
        sBattleBuffersTransferData[12] = gBattleWeather;
        sBattleBuffersTransferData[13] = (gBattleWeather & 0xFF00) >> 8;
    }
    else
    {
        sBattleBuffersTransferData[12] = 0;
        sBattleBuffersTransferData[13] = 0;
    }
    sBattleBuffersTransferData[14] = 0;
    sBattleBuffersTransferData[15] = 0;
    memcpy(&sBattleBuffersTransferData[16], disableStructPtr, sizeof(struct DisableStruct));
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 16 + sizeof(struct DisableStruct));
}

void BtlController_EmitPrintString(u8 bufferId, u16 stringId)
{
    s32 i;
    struct BattleMsgData *stringInfo;

    sBattleBuffersTransferData[0] = CONTROLLER_PRINTSTRING;
    sBattleBuffersTransferData[1] = gBattleOutcome;
    sBattleBuffersTransferData[2] = stringId;
    sBattleBuffersTransferData[3] = (stringId & 0xFF00) >> 8;

    stringInfo = (struct BattleMsgData *)(&sBattleBuffersTransferData[4]);
    stringInfo->currentMove = gCurrentMove;
    stringInfo->originallyUsedMove = gChosenMove;
    stringInfo->lastItem = gLastUsedItem;
    stringInfo->lastAbility = gLastUsedAbility;
    stringInfo->scrActive = gBattleScripting.battler;
    stringInfo->bakScriptPartyIdx = gBattleStruct->scriptPartyIdx;
    stringInfo->hpScale = gBattleStruct->hpScale;
    stringInfo->itemEffectBattler = gPotentialItemEffectBattler;
    stringInfo->moveType = gBattleMoves[gCurrentMove].type;

    for (i = 0; i < MAX_BATTLERS_COUNT; i++)
        stringInfo->abilities[i] = gBattleMons[i].ability;
    for (i = 0; i < TEXT_BUFF_ARRAY_COUNT; i++)
    {
        stringInfo->textBuffs[0][i] = gBattleTextBuff1[i];
        stringInfo->textBuffs[1][i] = gBattleTextBuff2[i];
        stringInfo->textBuffs[2][i] = gBattleTextBuff3[i];
    }
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, sizeof(struct BattleMsgData) + 4);
}

void BtlController_EmitPrintSelectionString(u8 bufferId, u16 stringId)
{
    s32 i;
    struct BattleMsgData *stringInfo;

    sBattleBuffersTransferData[0] = CONTROLLER_PRINTSTRINGPLAYERONLY;
    sBattleBuffersTransferData[1] = CONTROLLER_PRINTSTRINGPLAYERONLY;
    sBattleBuffersTransferData[2] = stringId;
    sBattleBuffersTransferData[3] = (stringId & 0xFF00) >> 8;

    stringInfo = (struct BattleMsgData *)(&sBattleBuffersTransferData[4]);
    stringInfo->currentMove = gCurrentMove;
    stringInfo->originallyUsedMove = gChosenMove;
    stringInfo->lastItem = gLastUsedItem;
    stringInfo->lastAbility = gLastUsedAbility;
    stringInfo->scrActive = gBattleScripting.battler;
    stringInfo->bakScriptPartyIdx = gBattleStruct->scriptPartyIdx;

    for (i = 0; i < MAX_BATTLERS_COUNT; i++)
        stringInfo->abilities[i] = gBattleMons[i].ability;
    for (i = 0; i < TEXT_BUFF_ARRAY_COUNT; i++)
    {
        stringInfo->textBuffs[0][i] = gBattleTextBuff1[i];
        stringInfo->textBuffs[1][i] = gBattleTextBuff2[i];
        stringInfo->textBuffs[2][i] = gBattleTextBuff3[i];
    }
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, sizeof(struct BattleMsgData) + 4);
}

// itemId only relevant for B_ACTION_USE_ITEM
void BtlController_EmitChooseAction(u8 bufferId, u8 action, u16 itemId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_CHOOSEACTION;
    sBattleBuffersTransferData[1] = action;
    sBattleBuffersTransferData[2] = itemId;
    sBattleBuffersTransferData[3] = (itemId & 0xFF00) >> 8;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

// Only used by the forfeit prompt in the Battle Frontier
// For other Yes/No boxes in battle, see Cmd_yesnobox
void BtlController_EmitYesNoBox(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_YESNOBOX;
    sBattleBuffersTransferData[1] = CONTROLLER_YESNOBOX;
    sBattleBuffersTransferData[2] = CONTROLLER_YESNOBOX;
    sBattleBuffersTransferData[3] = CONTROLLER_YESNOBOX;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitChooseMove(u8 bufferId, bool8 isDoubleBattle, bool8 noPPNumber, struct ChooseMoveStruct *movePPData)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_CHOOSEMOVE;
    sBattleBuffersTransferData[1] = isDoubleBattle;
    sBattleBuffersTransferData[2] = noPPNumber;
    sBattleBuffersTransferData[3] = 0;
    for (i = 0; i < sizeof(*movePPData); i++)
        sBattleBuffersTransferData[4 + i] = *((u8 *)(movePPData) + i);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, sizeof(*movePPData) + 4);
}

void BtlController_EmitChooseItem(u8 bufferId, u8 *battlePartyOrder)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_OPENBAG;
    for (i = 0; i < PARTY_SIZE / 2; i++)
        sBattleBuffersTransferData[1 + i] = battlePartyOrder[i];
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitChoosePokemon(u8 bufferId, u8 caseId, u8 slotId, u8 abilityId, u8 *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_CHOOSEPOKEMON;
    sBattleBuffersTransferData[1] = caseId;
    sBattleBuffersTransferData[2] = slotId;
    sBattleBuffersTransferData[3] = abilityId;
    for (i = 0; i < 3; i++)
        sBattleBuffersTransferData[4 + i] = data[i];
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 8);  // Only 7 bytes were written.
}

static void UNUSED BtlController_EmitCmd23(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_23;
    sBattleBuffersTransferData[1] = CONTROLLER_23;
    sBattleBuffersTransferData[2] = CONTROLLER_23;
    sBattleBuffersTransferData[3] = CONTROLLER_23;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

// why is the argument u16 if it's being cast to s16 anyway?
void BtlController_EmitHealthBarUpdate(u8 bufferId, u16 hpValue)
{
    sBattleBuffersTransferData[0] = CONTROLLER_HEALTHBARUPDATE;
    sBattleBuffersTransferData[1] = 0;
    sBattleBuffersTransferData[2] = (s16)hpValue;
    sBattleBuffersTransferData[3] = ((s16)hpValue & 0xFF00) >> 8;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

// why is the argument u16 if it's being cast to s16 anyway?
void BtlController_EmitExpUpdate(u8 bufferId, u8 partyId, u16 expPoints)
{
    sBattleBuffersTransferData[0] = CONTROLLER_EXPUPDATE;
    sBattleBuffersTransferData[1] = partyId;
    sBattleBuffersTransferData[2] = (s16)expPoints;
    sBattleBuffersTransferData[3] = ((s16)expPoints & 0xFF00) >> 8;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitStatusIconUpdate(u8 bufferId, u32 status1, u32 status2)
{
    sBattleBuffersTransferData[0] = CONTROLLER_STATUSICONUPDATE;
    sBattleBuffersTransferData[1] = status1;
    sBattleBuffersTransferData[2] = (status1 & 0x0000FF00) >> 8;
    sBattleBuffersTransferData[3] = (status1 & 0x00FF0000) >> 16;
    sBattleBuffersTransferData[4] = (status1 & 0xFF000000) >> 24;
    sBattleBuffersTransferData[5] = status2;
    sBattleBuffersTransferData[6] = (status2 & 0x0000FF00) >> 8;
    sBattleBuffersTransferData[7] = (status2 & 0x00FF0000) >> 16;
    sBattleBuffersTransferData[8] = (status2 & 0xFF000000) >> 24;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 9);
}

void BtlController_EmitStatusAnimation(u8 bufferId, bool8 status2, u32 status)
{
    sBattleBuffersTransferData[0] = CONTROLLER_STATUSANIMATION;
    sBattleBuffersTransferData[1] = status2;
    sBattleBuffersTransferData[2] = status;
    sBattleBuffersTransferData[3] = (status & 0x0000FF00) >> 8;
    sBattleBuffersTransferData[4] = (status & 0x00FF0000) >> 16;
    sBattleBuffersTransferData[5] = (status & 0xFF000000) >> 24;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 6);
}

static void UNUSED BtlController_EmitStatusXor(u8 bufferId, u8 b)
{
    sBattleBuffersTransferData[0] = CONTROLLER_STATUSXOR;
    sBattleBuffersTransferData[1] = b;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 2);
}

void BtlController_EmitDataTransfer(u8 bufferId, u16 size, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_DATATRANSFER;
    sBattleBuffersTransferData[1] = CONTROLLER_DATATRANSFER;
    sBattleBuffersTransferData[2] = size;
    sBattleBuffersTransferData[3] = (size & 0xFF00) >> 8;
    for (i = 0; i < size; i++)
        sBattleBuffersTransferData[4 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, size + 4);
}

#ifndef VER_64BIT
static void UNUSED BtlController_EmitDMA3Transfer(u8 bufferId, void *dst, u16 size, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_DMA3TRANSFER;
    sBattleBuffersTransferData[1] = (u32)(dst);
    sBattleBuffersTransferData[2] = ((u32)(dst) & 0x0000FF00) >> 8;
    sBattleBuffersTransferData[3] = ((u32)(dst) & 0x00FF0000) >> 16;
    sBattleBuffersTransferData[4] = ((u32)(dst) & 0xFF000000) >> 24;
    sBattleBuffersTransferData[5] = size;
    sBattleBuffersTransferData[6] = (size & 0xFF00) >> 8;
    for (i = 0; i < size; i++)
        sBattleBuffersTransferData[7 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, size + 7);
}
#endif

static void UNUSED BtlController_EmitPlayBGM(u8 bufferId, u16 songId, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_PLAYBGM;
    sBattleBuffersTransferData[1] = songId;
    sBattleBuffersTransferData[2] = (songId & 0xFF00) >> 8;

    // Nonsense loop using songId as a size
    // Would go out of bounds for any song id after SE_RG_BAG_POCKET (253)
    for (i = 0; i < songId; i++)
        sBattleBuffersTransferData[3 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, songId + 3);
}

static void UNUSED BtlController_EmitCmd32(u8 bufferId, u16 size, void *data)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_32;
    sBattleBuffersTransferData[1] = size;
    sBattleBuffersTransferData[2] = (size & 0xFF00) >> 8;
    for (i = 0; i < size; i++)
        sBattleBuffersTransferData[3 + i] = *(u8 *)(data++);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, size + 3);
}

void BtlController_EmitTwoReturnValues(u8 bufferId, u8 ret8, u16 ret16)
{
    sBattleBuffersTransferData[0] = CONTROLLER_TWORETURNVALUES;
    sBattleBuffersTransferData[1] = ret8;
    sBattleBuffersTransferData[2] = ret16;
    sBattleBuffersTransferData[3] = (ret16 & 0xFF00) >> 8;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitChosenMonReturnValue(u8 bufferId, u8 partyId, u8 *battlePartyOrder)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_CHOSENMONRETURNVALUE;
    sBattleBuffersTransferData[1] = partyId;
#if defined(UBFIX) || defined(PORTABLE)
    if (battlePartyOrder != NULL)
#endif
    {
    for (i = 0; i < (int)ARRAY_COUNT(gBattlePartyCurrentOrder); i++)
        sBattleBuffersTransferData[2 + i] = battlePartyOrder[i];
    }
#ifdef PORTABLE
    else
    {
        /* Cancel replies still carry a valid order, never prior staging bytes. */
        for (i = 0; i < (int)ARRAY_COUNT(gBattlePartyCurrentOrder); i++)
            sBattleBuffersTransferData[2 + i] = gBattlePartyCurrentOrder[i];
    }
#endif

    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 5);
}

void BtlController_EmitOneReturnValue(u8 bufferId, u16 ret)
{
    sBattleBuffersTransferData[0] = CONTROLLER_ONERETURNVALUE;
    sBattleBuffersTransferData[1] = ret;
    sBattleBuffersTransferData[2] = (ret & 0xFF00) >> 8;
    sBattleBuffersTransferData[3] = 0;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitOneReturnValue_Duplicate(u8 bufferId, u16 ret)
{
    sBattleBuffersTransferData[0] = CONTROLLER_ONERETURNVALUE_DUPLICATE;
    sBattleBuffersTransferData[1] = ret;
    sBattleBuffersTransferData[2] = (ret & 0xFF00) >> 8;
    sBattleBuffersTransferData[3] = 0;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

static void UNUSED BtlController_EmitClearUnkVar(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_CLEARUNKVAR;
    sBattleBuffersTransferData[1] = CONTROLLER_CLEARUNKVAR;
    sBattleBuffersTransferData[2] = CONTROLLER_CLEARUNKVAR;
    sBattleBuffersTransferData[3] = CONTROLLER_CLEARUNKVAR;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

static void UNUSED BtlController_EmitSetUnkVar(u8 bufferId, u8 b)
{
    sBattleBuffersTransferData[0] = CONTROLLER_SETUNKVAR;
    sBattleBuffersTransferData[1] = b;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 2);
}

static void UNUSED BtlController_EmitClearUnkFlag(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_CLEARUNKFLAG;
    sBattleBuffersTransferData[1] = CONTROLLER_CLEARUNKFLAG;
    sBattleBuffersTransferData[2] = CONTROLLER_CLEARUNKFLAG;
    sBattleBuffersTransferData[3] = CONTROLLER_CLEARUNKFLAG;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

static void UNUSED BtlController_EmitToggleUnkFlag(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_TOGGLEUNKFLAG;
    sBattleBuffersTransferData[1] = CONTROLLER_TOGGLEUNKFLAG;
    sBattleBuffersTransferData[2] = CONTROLLER_TOGGLEUNKFLAG;
    sBattleBuffersTransferData[3] = CONTROLLER_TOGGLEUNKFLAG;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitHitAnimation(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_HITANIMATION;
    sBattleBuffersTransferData[1] = CONTROLLER_HITANIMATION;
    sBattleBuffersTransferData[2] = CONTROLLER_HITANIMATION;
    sBattleBuffersTransferData[3] = CONTROLLER_HITANIMATION;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitCantSwitch(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_CANTSWITCH;
    sBattleBuffersTransferData[1] = CONTROLLER_CANTSWITCH;
    sBattleBuffersTransferData[2] = CONTROLLER_CANTSWITCH;
    sBattleBuffersTransferData[3] = CONTROLLER_CANTSWITCH;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitPlaySE(u8 bufferId, u16 songId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_PLAYSE;
    sBattleBuffersTransferData[1] = songId;
    sBattleBuffersTransferData[2] = (songId & 0xFF00) >> 8;
    sBattleBuffersTransferData[3] = 0;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitPlayFanfareOrBGM(u8 bufferId, u16 songId, bool8 playBGM)
{
    sBattleBuffersTransferData[0] = CONTROLLER_PLAYFANFAREORBGM;
    sBattleBuffersTransferData[1] = songId;
    sBattleBuffersTransferData[2] = (songId & 0xFF00) >> 8;
    sBattleBuffersTransferData[3] = playBGM;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitFaintingCry(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_FAINTINGCRY;
    sBattleBuffersTransferData[1] = CONTROLLER_FAINTINGCRY;
    sBattleBuffersTransferData[2] = CONTROLLER_FAINTINGCRY;
    sBattleBuffersTransferData[3] = CONTROLLER_FAINTINGCRY;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitIntroSlide(u8 bufferId, u8 environmentId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_INTROSLIDE;
    sBattleBuffersTransferData[1] = environmentId;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 2);
}

void BtlController_EmitIntroTrainerBallThrow(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_INTROTRAINERBALLTHROW;
    sBattleBuffersTransferData[1] = CONTROLLER_INTROTRAINERBALLTHROW;
    sBattleBuffersTransferData[2] = CONTROLLER_INTROTRAINERBALLTHROW;
    sBattleBuffersTransferData[3] = CONTROLLER_INTROTRAINERBALLTHROW;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitDrawPartyStatusSummary(u8 bufferId, struct HpAndStatus *hpAndStatus, u8 flags)
{
    s32 i;

    sBattleBuffersTransferData[0] = CONTROLLER_DRAWPARTYSTATUSSUMMARY;
    sBattleBuffersTransferData[1] = flags & ~PARTY_SUMM_SKIP_DRAW_DELAY; // If true, skip player side
    sBattleBuffersTransferData[2] = (flags & PARTY_SUMM_SKIP_DRAW_DELAY) >> 7; // If true, skip delay after drawing. True during intro
    sBattleBuffersTransferData[3] = CONTROLLER_DRAWPARTYSTATUSSUMMARY;
    for (i = 0; i < (s32)(sizeof(struct HpAndStatus) * PARTY_SIZE); i++)
        sBattleBuffersTransferData[4 + i] = *(i + (u8 *)(hpAndStatus));
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, sizeof(struct HpAndStatus) * PARTY_SIZE + 4);
}

void BtlController_EmitHidePartyStatusSummary(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_HIDEPARTYSTATUSSUMMARY;
    sBattleBuffersTransferData[1] = CONTROLLER_HIDEPARTYSTATUSSUMMARY;
    sBattleBuffersTransferData[2] = CONTROLLER_HIDEPARTYSTATUSSUMMARY;
    sBattleBuffersTransferData[3] = CONTROLLER_HIDEPARTYSTATUSSUMMARY;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitEndBounceEffect(u8 bufferId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_ENDBOUNCE;
    sBattleBuffersTransferData[1] = CONTROLLER_ENDBOUNCE;
    sBattleBuffersTransferData[2] = CONTROLLER_ENDBOUNCE;
    sBattleBuffersTransferData[3] = CONTROLLER_ENDBOUNCE;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitSpriteInvisibility(u8 bufferId, bool8 isInvisible)
{
    sBattleBuffersTransferData[0] = CONTROLLER_SPRITEINVISIBILITY;
    sBattleBuffersTransferData[1] = isInvisible;
    sBattleBuffersTransferData[2] = CONTROLLER_SPRITEINVISIBILITY;
    sBattleBuffersTransferData[3] = CONTROLLER_SPRITEINVISIBILITY;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

void BtlController_EmitBattleAnimation(u8 bufferId, u8 animationId, u16 argument)
{
    sBattleBuffersTransferData[0] = CONTROLLER_BATTLEANIMATION;
    sBattleBuffersTransferData[1] = animationId;
    sBattleBuffersTransferData[2] = argument;
    sBattleBuffersTransferData[3] = (argument & 0xFF00) >> 8;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 4);
}

// mode is a LINK_STANDBY_* constant
void BtlController_EmitLinkStandbyMsg(u8 bufferId, u8 mode, bool32 record)
{
    bool8 record_ = record;
    sBattleBuffersTransferData[0] = CONTROLLER_LINKSTANDBYMSG;
    sBattleBuffersTransferData[1] = mode;

    if (record_)
        sBattleBuffersTransferData[3] = sBattleBuffersTransferData[2] = RecordedBattle_BufferNewBattlerData(&sBattleBuffersTransferData[4]);
    else
        sBattleBuffersTransferData[3] = sBattleBuffersTransferData[2] = 0;

    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, sBattleBuffersTransferData[2] + 4);
}

void BtlController_EmitResetActionMoveSelection(u8 bufferId, u8 caseId)
{
    sBattleBuffersTransferData[0] = CONTROLLER_RESETACTIONMOVESELECTION;
    sBattleBuffersTransferData[1] = caseId;
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, 2);
}

void BtlController_EmitEndLinkBattle(u8 bufferId, u8 battleOutcome)
{
    sBattleBuffersTransferData[0] = CONTROLLER_ENDLINKBATTLE;
    sBattleBuffersTransferData[1] = battleOutcome;
    sBattleBuffersTransferData[2] = gSaveBlock2Ptr->frontier.disableRecordBattle;
    sBattleBuffersTransferData[3] = gSaveBlock2Ptr->frontier.disableRecordBattle;
    sBattleBuffersTransferData[5] = sBattleBuffersTransferData[4] = RecordedBattle_BufferNewBattlerData(&sBattleBuffersTransferData[6]);
    PrepareBufferDataTransfer(bufferId, sBattleBuffersTransferData, sBattleBuffersTransferData[4] + 6);
}
