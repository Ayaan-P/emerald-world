"""Deferred RC tests. Do not run until the parent authorizes integrated RC.

Run with python3 -m unittest discover -s test/world -p test_native_summary_detail.py
These compile only the actual guarded arithmetic helper, not the game.
Native rendering/input and save immutability still need the RC cases in JSON.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class NativeSummaryDetailTests(unittest.TestCase):
    def test_hidden_power_matches_gen_three_for_every_low_bit_pattern(self):
        program = r'''
#include <stdint.h>
typedef uint8_t u8;
#include "platform/summary_detail.h"
int main(void)
{
    static const u8 types[] = {1,2,3,4,5,6,7,8,10,11,12,13,14,15,16,17};
    unsigned pattern, stat;
    for (pattern = 0; pattern < 4096; ++pattern)
    {
        u8 ivs[6], type, power;
        unsigned parity = 0, second = 0;
        for (stat = 0; stat < 6; ++stat)
        {
            ivs[stat] = (pattern >> (stat * 2)) & 3;
            parity += (ivs[stat] % 2) * (1u << stat);
            second += ((ivs[stat] / 2) % 2) * (1u << stat);
        }
        SummaryDetail_CalculateHiddenPower(ivs, &type, &power);
        if (type != types[parity * 15 / 63] || power != 30 + second * 40 / 63)
            return 1;
        /* Upper IV bits do not contribute. This also includes all-31 IVs. */
        for (stat = 0; stat < 6; ++stat)
            ivs[stat] += 28;
        SummaryDetail_CalculateHiddenPower(ivs, &type, &power);
        if (type != types[parity * 15 / 63] || power != 30 + second * 40 / 63)
            return 2;
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "summary.c"
            binary = pathlib.Path(directory) / "summary"
            source.write_text(program)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-DPORTABLE", "-I", str(ROOT / "include"),
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_native_panel_reads_all_six_raw_iv_ev_fields(self):
        source = (ROOT / "src/pokemon_summary_screen.c").read_text()
        panel = source.split("static void OpenSummaryDetail(void)\n{", 1)[1].split(
            "static void CloseSummaryDetail(void)\n{", 1)[0]
        for stat in ("HP", "ATK", "DEF", "SPEED", "SPATK", "SPDEF"):
            self.assertIn("MON_DATA_" + stat + "_IV", panel)
            self.assertIn("MON_DATA_" + stat + "_EV", panel)
        for writer in ("SetMonData", "SetBoxMonData", "CalculateMonStats", "memcpy"):
            self.assertNotIn(writer, panel)
        self.assertIn("SummaryDetail_CalculateHiddenPower", panel)
        self.assertIn("GetMonData(&sMonSummaryScreen->currentMon", panel)

    def test_control_and_privacy_are_wired_to_native_input(self):
        source = (ROOT / "src/pokemon_summary_screen.c").read_text()
        input_handler = source.split("static void Task_HandleInput(u8 taskId)\n{", 1)[1].split(
            "static void ChangeSummaryPokemon(u8 taskId", 1)[0]
        self.assertIn("JOY_NEW(SELECT_BUTTON)", input_handler)
        self.assertIn("CanShowSummaryDetail()", input_handler)
        self.assertIn("CloseSummaryDetail();", input_handler)
        gate = source.split("static bool8 CanShowSummaryDetail(void)\n{", 1)[1].split(
            "static void PrintSummaryDetailHint(void)\n{", 1)[0]
        for check in ("WorldCoop_IsBattle()", "gMain.inBattle", "InBattleFactory()",
                      "InSlateportBattleTent()", "gPlayerParty", "GetBoxedMonPtr",
                      "SUMMARY_MODE_BOX", "SUMMARY_MODE_NORMAL", "summary.isEgg",
                      "summary.sanity", "MON_DATA_SANITY_IS_BAD_EGG"):
            self.assertIn(check, gate)


if __name__ == "__main__":
    unittest.main()
