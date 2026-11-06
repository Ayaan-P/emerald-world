#!/usr/bin/env python3
"""Expose the donor's own cable-battle task for opt-in world sessions."""
from pathlib import Path
import sys


def generate(source):
    include = '#include "cable_club.h"'
    anchor = 'static void CB2_ReturnFromUnionRoomBattle(void)\n{'
    if source.count(include) != 1 or source.count(anchor) != 1:
        raise ValueError('pinned donor cable-club anchors changed')
    source = source.replace(include, include + '\n#include "load_save.h"', 1)
    helper = '''extern void ExpansionActivity_ReturnToField(void);

static void CB2_ExpansionReturnFromBattle(void)
{
    CB2_ReturnFromCableClubBattle();
    gMain.savedCallback = ExpansionActivity_ReturnToField;
}
static void Task_ExpansionStartBattle(u8 taskId)
{
    Task_StartWiredCableClubBattle(taskId);
    if (gMain.callback2 == CB2_InitBattle)
        gMain.savedCallback = CB2_ExpansionReturnFromBattle;
}
int ExpansionActivity_StartBattle(unsigned mode)
{
    u8 taskId;
    if (mode != 1 && mode != 2) return FALSE;
    taskId = CreateTask(Task_ExpansionStartBattle, 80);
    if (taskId == TASK_NONE) return FALSE;
    SavePlayerParty();
    LoadPlayerBag();
    gSpecialVar_0x8004 = mode == 2 ? USING_DOUBLE_BATTLE : USING_SINGLE_BATTLE;
    gLinkPlayers[0].id = 0;
    gLinkPlayers[1].id = 1;
    return TRUE;
}

'''
    return source.replace(anchor, helper + anchor, 1)

if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('usage: patch_expansion_cable.py DONOR OUTPUT')
    source, output = map(Path, sys.argv[1:])
    result = generate(source.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result)
