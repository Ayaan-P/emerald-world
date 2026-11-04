"""Fault-inject real production save commits; no SDL or native game launch.

The engine serialization boundary is stubbed, not its completion/status code.
The production StoreSaveFile, Platform_StoreSaveFile, HandleSavingData and
TrySavingData bodies execute with real stdio and link-wrapped failure syscalls.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.name == 'posix' and shutil.which('gcc'), 'POSIX gcc required')
class NativeSaveCommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='save-commit-component-')
        p = Path(cls.temp.name)
        source_root = Path(os.environ.get('NATIVE_SAVE_SOURCE', ROOT))
        sdl = (source_root / 'src/platform/sdl2.c').read_text()
        save = (source_root / 'src/save.c').read_text()
        failed = (source_root / 'src/save_failed_screen.c').read_text()
        code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "platform/native_save.h"
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define SAVE_STATUS_OK 1
#define SAVE_STATUS_ERROR 255
#define FULL_SAVE_SLOT 65535
#define SAVE_NORMAL 0
#define SAVE_LINK 1
#define SAVE_EREADER 2
#define SAVE_HALL_OF_FAME 3
#define SAVE_OVERWRITE_DIFFERENT_FILE 4
#define SAVE_HALL_OF_FAME_ERASE_BEFORE 5
#define SECTOR_ID_HOF_1 28
#define SECTOR_ID_HOF_2 29
#define SECTORS_COUNT 32
#define GAME_STAT_ENTERED_HOF 0
#define SECTOR_DATA_SIZE 3968
#define SECTOR_ID_SAVEBLOCK2 0
#define SECTOR_ID_SAVEBLOCK1_END 4
static int fault, seekCalls, writeCalls, flushCalls, syncCalls, failureScreen;
static FILE *sSaveFile;
static unsigned char FLASH_BASE[131072];
static u32 tick, *gTrainerHillVBlankCounter = &tick;
static u8 gFlashMemoryPresent = TRUE, gSaveAttemptStatus;
static u16 gLastWrittenSector = 3, gLastKnownGoodSector = 3;
static u32 gSaveCounter = 9, gLastSaveCounter = 9, gDamagedSaveSectors;
static u8 gDecompressionBuffer[2*SECTOR_DATA_SIZE];
static int gRamSaveSectorLocations[14];
static void UpdateSaveAddresses(void) {}
static void CopyPartyAndObjectsToSave(void) {}
static unsigned GetGameStat(unsigned x) {(void)x;return 0;}
static void IncrementGameStat(unsigned x) {(void)x;}
static void EraseFlashSector(unsigned x) {(void)x;}
static void WriteSaveSectorOrSlot(unsigned sector, const void *locations)
{
    (void)sector; (void)locations;
    gLastKnownGoodSector=gLastWrittenSector;gLastSaveCounter=gSaveCounter;
    gLastWrittenSector++;gSaveCounter++;
}
static void HandleWriteSectorNBytes(unsigned x, const void *p, unsigned n) {(void)x;(void)p;(void)n;}
static void HandleReplaceSector(unsigned x, const void *p) {(void)x;(void)p;}
static void WriteSectorSignatureByte_NoOffset(unsigned x, const void *p) {(void)x;(void)p;}
static void DoSaveFailedScreen(unsigned type) {(void)type;failureScreen++;}
int __real_fseek(FILE *, long, int);
size_t __real_fwrite(const void *, size_t, size_t, FILE *);
int __real_fflush(FILE *);
int __real_fsync(int);
int __wrap_fseek(FILE *stream, long offset, int whence)
{
    seekCalls++;
    if(fault==1) {errno=EIO;return -1;}
    return __real_fseek(stream,offset,whence);
}
size_t __wrap_fwrite(const void *data, size_t size, size_t count, FILE *stream)
{
    writeCalls++;
    if(fault==2) {errno=ENOSPC;return 0;}
    return __real_fwrite(data,size,count,stream);
}
int __wrap_fflush(FILE *stream)
{
    flushCalls++;
    if(fault==3) {errno=ENOSPC;return EOF;}
    return __real_fflush(stream);
}
int __wrap_fsync(int fd)
{
    syncCalls++;
    if(fault==4) {errno=EIO;return -1;}
    if(fault==5 && syncCalls==1) {errno=EINTR;return -1;}
    return __real_fsync(fd);
}
'''
        code += function(sdl, 'StoreSaveFile')
        code += function(sdl, 'Platform_StoreSaveFile')
        # The baseline publishes a void API, so its callers assume completion.
        # This adapter exposes that original behavior, not a fabricated success
        # from the corrected bool8 API.
        if 'bool8 Platform_StoreSaveFile(' in sdl:
            code += 'static bool8 Commit(void) {return Platform_StoreSaveFile();}\n'
        else:
            code += 'static bool8 Commit(void) {Platform_StoreSaveFile();return TRUE;}\n'
        code += function(save, 'HandleSavingData')
        code += function(save, 'TrySavingData')
        code += r'''
#define TEXT_WIN_ID 0
#define CLOCK_RUNNING 0
#define PIXEL_FILL(x) (x)
static u8 sClockInfo[1], sWindowIds[1], sSaveFailedType;
static void (*gGameContinueCallback)(void), (*nextCallback)(void);
static int savedMessage;
static const char gText_BackupMemoryDamaged[]="damaged";
static const char gText_CheckCompleted[]="checked";
static const char gText_SaveFailedCheckingBackup[]="retry";
static const char gText_SaveCompleteGameCannotContinue[]="saved_no_continue";
static const char gText_SaveCompletePressA[]="saved_continue";
static int WipeSectors(u32 sectors) {(void)sectors;gDamagedSaveSectors=0;return 0;}
static void FillWindowPixelBuffer(u8 id, u8 fill) {(void)id;(void)fill;}
static void SaveFailedScreenTextPrint(const char *text, int x, int y)
{
    (void)x;(void)y;
    if(text==gText_SaveCompleteGameCannotContinue || text==gText_SaveCompletePressA) savedMessage++;
}
static void CB2_GameplayCannotBeContinued(void) {}
static void CB2_FadeAndReturnToTitleScreen(void) {}
static void SetMainCallback2(void (*next)(void)) {nextCallback=next;}
'''
        code += function(failed, 'CB2_WipeSave')
        code += r'''
int main(int argc, char **argv)
{
    (void)argc;
    fault=atoi(argv[1]);
    char path[]="/tmp/save-commit-XXXXXX";
    int fd=mkstemp(path);
    assert(fd>=0);
    sSaveFile=fdopen(fd,"w+b");
    assert(sSaveFile);
    memset(FLASH_BASE,0x3a,sizeof(FLASH_BASE));
    if(strcmp(argv[2],"missing")==0) {fclose(sSaveFile);sSaveFile=NULL;}
    int status;
    if(strcmp(argv[2],"save")==0 || strcmp(argv[2],"no-flash")==0)
    {
        if(strcmp(argv[2],"no-flash")==0) gFlashMemoryPresent=FALSE;
        status=TrySavingData(SAVE_NORMAL);
    }
    else if(strcmp(argv[2],"screen")==0)
    {
        gDamagedSaveSectors=1;
        CB2_WipeSave();
        status=nextCallback==CB2_GameplayCannotBeContinued ? SAVE_STATUS_ERROR : SAVE_STATUS_OK;
    }
    else
        status=Commit();
    int retryStatus=-1;
    if(strcmp(argv[2],"retry")==0)
    {
        fault=0;
        retryStatus=Commit();
    }
    printf("{\"status\":%d,\"attempt\":%u,\"seek\":%d,\"write\":%d,\"flush\":%d,\"sync\":%d,\"counter\":%u,\"sector\":%u,\"damaged\":%u,\"failure_screen\":%d,\"clock_restored\":%d,\"saved_message\":%d,\"retry_status\":%d}\n",
           status,gSaveAttemptStatus,seekCalls,writeCalls,flushCalls,syncCalls,
           gSaveCounter,gLastWrittenSector,gDamagedSaveSectors,failureScreen,gTrainerHillVBlankCounter==&tick,savedMessage,retryStatus);
    if(sSaveFile) fclose(sSaveFile);
    unlink(path);
    return 0;
}
'''
        (p / 'probe.c').write_text(code)
        cls.binary = p / 'probe'
        command = ['gcc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-DPORTABLE',
                   '-iquote', str(ROOT / 'include'), str(p / 'probe.c'),
                   str(ROOT / 'src/platform/native_save.c'),
                   '-Wl,--wrap=fseek', '-Wl,--wrap=fwrite', '-Wl,--wrap=fflush', '-Wl,--wrap=fsync']
        if os.environ.get('NATIVE_SAVE_SANITIZE') == '1':
            command += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-pie', '-no-pie']
        command += ['-o', str(cls.binary)]
        built = subprocess.run(command, capture_output=True, text=True)
        if built.returncode:
            raise AssertionError(built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, fault=0, mode='commit'):
        result = subprocess.run([str(self.binary), str(fault), mode], capture_output=True,
                                text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_missing_save_stream_cannot_report_success(self):
        self.assertEqual(self.run_case(mode='missing')['status'], 0)

    def test_seek_failure_prevents_success_and_later_writes(self):
        state = self.run_case(1)
        self.assertEqual(state['status'], 0)
        self.assertEqual(state['write'], 0)
        self.assertEqual(state['sync'], 0)

    def test_short_write_cannot_report_success(self):
        self.assertEqual(self.run_case(2)['status'], 0)

    def test_flush_failure_cannot_report_success(self):
        self.assertEqual(self.run_case(3)['status'], 0)

    def test_sync_failure_cannot_report_success(self):
        self.assertEqual(self.run_case(4)['status'], 0)

    def test_interrupted_sync_retries_without_rewriting(self):
        state = self.run_case(5)
        self.assertEqual(state['status'], 1)
        self.assertEqual(state['sync'], 2)
        self.assertEqual(state['write'], 1)

    def test_ordinary_save_failure_restores_rotation_without_wiping_good_sectors(self):
        for fault in (1, 2, 3, 4):
            with self.subTest(fault=fault):
                state = self.run_case(fault, 'save')
                self.assertEqual(state['status'], 255)
                self.assertEqual(state['attempt'], 255)
                self.assertEqual(state['counter'], 9)
                self.assertEqual(state['sector'], 3)
                self.assertEqual(state['damaged'], 0)
                self.assertEqual(state['failure_screen'], 0)
                self.assertEqual(state['clock_restored'], 1)

    def test_successful_ordinary_save_publishes_once(self):
        state = self.run_case(mode='save')
        self.assertEqual(state['status'], 1)
        self.assertEqual(state['attempt'], 1)
        self.assertEqual(state['write'], 1)
        self.assertEqual(state['sync'], 1)
        self.assertEqual(state['counter'], 10)

    def test_explicit_retry_can_commit_after_flush_fault_is_cleared(self):
        state = self.run_case(3, 'retry')
        self.assertEqual(state['status'], 0)
        self.assertEqual(state['retry_status'], 1)
        self.assertEqual(state['sync'], 1)

    def test_recovery_screen_cannot_claim_saved_when_host_file_commit_fails(self):
        state = self.run_case(3, 'screen')
        self.assertEqual(state['status'], 255)
        self.assertEqual(state['saved_message'], 0)
        self.assertEqual(state['clock_restored'], 1)

    def test_no_flash_preserves_existing_failure_contract(self):
        state = self.run_case(mode='no-flash')
        self.assertEqual(state['status'], 255)
        self.assertEqual(state['write'], 0)
        self.assertEqual(state['counter'], 9)


if __name__ == '__main__':
    unittest.main()
