"""Compile real move-category helpers; not full engine or gameplay acceptance."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
class CategoryTests(unittest.TestCase):
    def test_native_and_legacy_modes_use_expected_categories(self):
        source=r'''
#include <stdint.h>
#include <assert.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint8_t bool8;
#define FALSE 0
#define TYPE_MYSTERY 9
#define TYPE_NORMAL 0
#define TYPE_FIRE 10
#define TYPE_DARK 17
#define BATTLE_TYPE_LINK 1
#define BATTLE_TYPE_RECORDED 2
#define BATTLE_TYPE_RECORDED_LINK 4
#define IS_TYPE_PHYSICAL(t) ((t)<TYPE_MYSTERY)
#define IS_TYPE_SPECIAL(t) ((t)>TYPE_MYSTERY)
uint32_t gBattleTypeFlags;int flag,linked;
int FlagGet(int id) {(void)id;return flag;}
int NativeLink_IsActive(void) {return linked;}
#include "battle_move_split.h"
#include "battle_rules_wire.h"
int main(void) {
 assert(BattleRules_LinkType(0x2233,1)==0xA233);
 assert(BattleRules_LinkType(0x2233,0)==0x2233);
 assert(BattleRules_LinkType(0x1111,1)==0x1111);
 flag=0;
 assert(BattleMove_IsSpecial(MOVE_FIRE_PUNCH,TYPE_FIRE));
 assert(BattleMove_IsSpecial(MOVE_BITE,TYPE_DARK));
 assert(BattleMove_IsPhysical(MOVE_RAZOR_WIND,TYPE_NORMAL));
 flag=1;
 assert(BattleMove_IsPhysical(MOVE_FIRE_PUNCH,TYPE_FIRE));
 assert(BattleMove_IsPhysical(MOVE_BITE,TYPE_DARK));
 assert(BattleMove_IsSpecial(MOVE_RAZOR_WIND,TYPE_NORMAL));
 assert(!BattleMove_IsPhysical(MOVE_SWORDS_DANCE,TYPE_NORMAL));
 assert(!BattleMove_IsSpecial(MOVE_SWORDS_DANCE,TYPE_NORMAL));
 assert(!BattleMove_IsPhysical(MOVE_FIRE_PUNCH,TYPE_MYSTERY));
 assert(!BattleMove_IsSpecial(MOVE_ICE_BEAM,TYPE_MYSTERY));
 assert(!BattleMove_IsPhysical(MOVES_COUNT,TYPE_NORMAL));
 gBattleTypeFlags=BATTLE_TYPE_LINK;linked=0;
 assert(BattleMove_IsSpecial(MOVE_FIRE_PUNCH,TYPE_FIRE));
 linked=1;
 assert(BattleMove_IsPhysical(MOVE_FIRE_PUNCH,TYPE_FIRE));
 gBattleTypeFlags=BATTLE_TYPE_RECORDED;
 assert(BattleMove_IsSpecial(MOVE_FIRE_PUNCH,TYPE_FIRE));
 gBattleTypeFlags=BATTLE_TYPE_RECORDED_LINK;
 assert(BattleMove_IsSpecial(MOVE_FIRE_PUNCH,TYPE_FIRE));
 for(int i=0;i<MOVES_COUNT;i++) assert(sModernMoveCategory[i]<=MOVE_SPLIT_STATUS);
 return 0;
}'''
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'constants').mkdir();(root/'platform').mkdir()
            (root/'event_data.h').write_text('int FlagGet(int);\n')
            (root/'constants/flags.h').write_text('#define FLAG_MODERN_MOVE_SPLIT 1\n')
            # Real original move IDs, copied into the isolated test include tree.
            (root/'constants/moves.h').write_text((ROOT/'include/constants/moves.h').read_text())
            (root/'platform/native_link.h').write_text('int NativeLink_IsActive(void);\n')
            (root/'battle_move_split.h').write_text((ROOT/'include/battle_move_split.h').read_text())
            (root/'battle_rules_wire.h').write_text((ROOT/'include/platform/battle_rules_wire.h').read_text())
            c=root/'t.c';exe=root/'t';c.write_text(source)
            result=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-I',str(root),str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_engine_and_recording_are_wired_to_rule(self):
        battle=(ROOT/'src/battle_main.c').read_text()
        link=(ROOT/'src/link.c').read_text()
        scripts=(ROOT/'src/battle_script_commands.c').read_text()
        self.assertIn('disableRecordBattle = BattleRules_UseModernSplit()',battle)
        self.assertIn('BattleRules_LinkType(gLinkType, FlagGet(FLAG_MODERN_MOVE_SPLIT))',link)
        self.assertIn('BattleMove_IsPhysical(gCurrentMove, moveType)',scripts)
        self.assertIn('BattleRules_UseModernSplit() && gSpecialStatuses[gBattlerTarget].physicalDmg',scripts)

    def test_all_native_move_ids_have_explicit_categories(self):
        import re
        ids=(ROOT/'include/constants/moves.h').read_text()
        header=(ROOT/'include/battle_move_split.h').read_text()
        names={m.group(1) for m in re.finditer(r'^#define (MOVE_\w+) (\d+)$',ids,re.M) if int(m.group(2))<=354}
        rows=re.findall(r'^\s*\[(MOVE_\w+)\]\s*=',header,re.M)
        self.assertEqual(len(rows),355);self.assertEqual(len(set(rows)),355)
        self.assertEqual(set(rows),names)

if __name__=='__main__':unittest.main()
