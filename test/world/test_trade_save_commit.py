"""Execute production trade save callbacks with injected persistence failures."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from test_link_trade_payloads import function

ROOT = Path(__file__).resolve().parents[2]


class TradeSaveCommit(unittest.TestCase):
    def run_c(self, code):
        with tempfile.TemporaryDirectory(prefix='trade-commit-') as tmp:
            c = Path(tmp) / 'test.c'
            exe = Path(tmp) / 'test'
            c.write_text('#include <assert.h>\n#include <stdint.h>\n'
                         'typedef uint8_t u8; typedef uint16_t u16; typedef u8 bool8;\n'
                         '#define TRUE 1\n#define FALSE 0\n' + code)
            subprocess.run(['cc', '-std=gnu99', '-DPORTABLE', '-fsanitize=address,undefined',
                            '-fno-pie', '-no-pie', str(c), '-o', str(exe)], check=True,
                           capture_output=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True,
                                    env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=0',
                                         'UBSAN_OPTIONS': 'halt_on_error=1'})
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_signature_reports_failed_durable_store_without_destroying_backup(self):
        code = r'''
#define NUM_SECTORS_PER_SLOT 14
#define SAVE_NORMAL 0
#define SAVE_STATUS_OK 1
#define SAVE_STATUS_ERROR 255
int gRamSaveSectorLocations, gDamagedSaveSectors, gSaveAttemptStatus;
int signatures, stores, failedScreens, durable;
void CopySectorSignatureByte(int sectors,int addresses) { signatures++; }
int Platform_StoreSaveFile(void) { stores++; return durable; }
void DoSaveFailedScreen(int kind) { failedScreens++; }
'''
        code += function((ROOT / 'src/save.c').read_text(), 'LinkFullSave_SetLastSectorSignature')
        code += r'''
int main(void) {
 durable=0;
 assert(LinkFullSave_SetLastSectorSignature()==TRUE);
 assert(stores==1 && signatures==1 && !gDamagedSaveSectors && !failedScreens);
 assert(gSaveAttemptStatus==SAVE_STATUS_ERROR);
 durable=1;
 assert(LinkFullSave_SetLastSectorSignature()==FALSE);
 assert(stores==2 && signatures==2 && !gDamagedSaveSectors && !failedScreens);
 assert(gSaveAttemptStatus==SAVE_STATUS_OK);
 return 0;
}
'''
        self.run_c(code)

    def test_trade_does_not_advance_past_failed_save_commit(self):
        code = r'''
#define PALETTES_ALL 0
#define RGB_BLACK 0
#define GAME_STAT_POKEMON_TRADES 0
#define CARD_STAT_NUM_TRADES 0
int gWirelessCommType, gSoftResetDisabled, gReceivedRemoteLinkPlayers;
int standby, durable, commits;
struct { int active; } gPaletteFade;
struct { int state; void (*savedCallback)(void); } gMain;
struct { int timer; } anim, *sTradeAnim=&anim;
struct { int trainerId; } gLinkPlayers[2];
char gStringVar4[4], gText_CommunicationStandby5[4], gText_SavingDontTurnOffPower[4];
void CB2_StartCreateTradeMenu(void) {}
void CB2_FreeTradeAnim(void) {}
void StringExpandPlaceholders(char *a,char *b) {}
void DrawTextOnTradeWindow(int a,char *b,int c) {}
void SetTradeLinkStandbyCallback(int a) { standby++; }
int _IsLinkTaskFinished(void) { return 1; }
int InUnionRoom(void) { return 0; }
void IncrementGameStat(int a) {}
void MysteryGift_TryIncrementStat(int a,int b) {}
int GetMultiplayerId(void) { return 0; }
void SetContinueGameWarpStatusToDynamicWarp(void) {}
void LinkFullSave_Init(void) {}
int LinkFullSave_WriteSector(void) { return 1; }
void ClearContinueGameWarpStatus2(void) {}
void LinkFullSave_ReplaceLastSector(void) {}
int Random(void) { return 0; }
int LinkFullSave_SetLastSectorSignature(void) { commits++; return !durable; }
void BeginNormalPaletteFade(int a,int b,int c,int d,int e) {}
void FadeOutBGM(int a) {}
int IsBGMStopped(void) { return 1; }
void SetCloseLinkCallback(void) {}
void SetMainCallback2(void (*cb)(void)) {}
int HasLinkErrorOccurred(void) { return 0; }
void RunTasks(void) {}
void AnimateSprites(void) {}
void BuildOamBuffer(void) {}
void UpdatePaletteFade(void) {}
'''
        code += function((ROOT / 'src/trade.c').read_text(), 'CB2_SaveAndEndTrade')
        code += function((ROOT / 'src/trade.c').read_text(), 'CB2_SaveAndEndWirelessTrade')
        code += r'''
int main(void) {
 gMain.state=42; durable=0;
 CB2_SaveAndEndTrade();
 assert(commits==1 && gMain.state==42 && standby==0);
 durable=1; CB2_SaveAndEndTrade();
 assert(commits==2 && gMain.state==5 && standby==0);
 gMain.state=8; durable=0;
 CB2_SaveAndEndWirelessTrade(); CB2_SaveAndEndWirelessTrade();
 assert(commits==4 && gMain.state==8 && standby==0);
 durable=1; CB2_SaveAndEndWirelessTrade();
 assert(commits==5 && gMain.state==9 && standby==0);
 return 0;
}
'''
        self.run_c(code)


if __name__ == '__main__':
    unittest.main()
