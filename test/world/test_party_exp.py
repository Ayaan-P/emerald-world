"""Focused helper and source-wiring checks; not native gameplay acceptance."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class PartyExpTests(unittest.TestCase):
    def test_actual_c_award_and_eligibility_helpers(self):
        source=r'''
#include <assert.h>
#include <stdint.h>
typedef uint16_t u16; typedef uint32_t u32; typedef uint8_t u8; typedef uint8_t bool8;
#define SPECIES_NONE 0
#include "party_exp.h"
int main(void) {
  assert(PartyExp_BaseAward(100, 2, 1) == 50);
  assert(PartyExp_BaseAward(100, 2, 0) == 50);
  assert(PartyExp_BaseAward(101, 1, 1) == 101);
  assert(PartyExp_BaseAward(101, 1, 0) == 50);
  assert(PartyExp_BaseAward(0, 1, 0) == 1);
  assert(PartyExp_BaseAward(100, 0, 1) == 0);
  assert(PartyExp_Eligible(1, 20, 0));
  assert(!PartyExp_Eligible(0, 20, 0));
  assert(!PartyExp_Eligible(1, 0, 0));
  assert(!PartyExp_Eligible(1, 20, 1));
  assert(PartyExp_RecipientBase(100,50,1,0,1) == 100);
  assert(PartyExp_RecipientBase(100,50,1,0,0) == 50);
  assert(PartyExp_RecipientBase(100,50,1,1,1) == 100);
  assert(PartyExp_RecipientBase(100,50,1,1,0) == 50);
  assert(PartyExp_RecipientBase(100,50,0,1,1) == 150);
  assert(PartyExp_RecipientBase(100,50,0,1,0) == 50);
  assert(PartyExp_RecipientBase(100,50,0,0,0) == 0);
  assert(PartyExp_RecipientBase(65535,65535,0,1,1) == 131070);
  return 0;
}'''
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/'test.c'; exe=Path(d)/'test';c.write_text(source)
            subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT/'include'),str(c),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)
    def test_game_and_menu_wiring(self):
        battle=(ROOT/'src/battle_script_commands.c').read_text()
        menu=(ROOT/'src/platform/world_menu.c').read_text()
        flags=(ROOT/'include/constants/flags.h').read_text()
        self.assertIn('WorldRules_Enabled(WORLD_RULE_PARTY_EXP)',battle)
        self.assertIn('!(gBattleTypeFlags & BATTLE_TYPE_INGAME_PARTNER)',battle)
        self.assertIn('PartyExp_Eligible(',battle)
        self.assertIn('PartyExp_RecipientBase(',battle)
        self.assertNotIn('FlagSet(FLAG_PARTY_EXP_SHARE)',menu)
        self.assertNotIn('FlagClear(FLAG_PARTY_EXP_SHARE)',menu)
        self.assertIn('#define FLAG_PARTY_EXP_SHARE',flags)

if __name__=='__main__':unittest.main()
