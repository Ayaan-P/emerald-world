"""Exercise Dot's real native sidecar implementation with disposable files."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]

class UnstuckStorageTests(unittest.TestCase):
    def test_private_trainer_bound_cooldown_and_boxed_waiver(self):
        source = r'''
#include <assert.h>
#include <unistd.h>
#include <sys/stat.h>
#include "src/platform/native_save.c"
#include "src/platform/native_unstuck.c"
int main(int argc,char **argv) {
 unsigned left=0; struct stat st; char path[4096];
 assert(argc==2); FILE *save=NativeSave_Open(argv[1]); assert(save);
 assert(NativeUnstuck_SetSavePath(argv[1]));
 assert(NativeUnstuck_ReserveCurrent(123,1000,0,&left)==NATIVE_UNSTUCK_ALLOWED);
 assert(NativeUnstuck_ReserveCurrent(123,1299,0,&left)==NATIVE_UNSTUCK_COOLDOWN && left==1);
 assert(NativeUnstuck_ReserveCurrent(124,1300,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(NativeUnstuck_ReserveCurrent(123,1300,0,&left)==NATIVE_UNSTUCK_ALLOWED);
 assert(NativeUnstuck_ReserveCurrent(123,1200,0,&left)==NATIVE_UNSTUCK_COOLDOWN && left==300);
 assert(NativeUnstuck_ReserveCurrent(123,1301,1,&left)==NATIVE_UNSTUCK_ALLOWED);
 assert(NativeUnstuck_ReserveCurrent(123,1302,0,&left)==NATIVE_UNSTUCK_COOLDOWN && left==299);
 snprintf(path,sizeof(path),"%s.unstuck",argv[1]);
 assert(!stat(path,&st) && (st.st_mode & 0777)==0600 && st.st_size==41);
 assert(!chmod(path,0644));
 assert(NativeUnstuck_ReserveCurrent(123,2000,1,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(!unlink(path)); assert(!symlink(argv[1],path));
 assert(NativeUnstuck_ReserveCurrent(123,2000,1,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(!unlink(path)); FILE *bad=fopen(path,"wb");assert(bad);fclose(bad);
 assert(NativeUnstuck_ReserveCurrent(123,2000,1,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(NativeUnstuck_ReserveCurrent(123,0,1,&left)==NATIVE_UNSTUCK_BAD_CLOCK);
 assert(!NativeUnstuck_SetSavePath(NULL));
 assert(NativeUnstuck_ReserveCurrent(123,2000,1,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 fclose(save); return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='unstuck-storage-') as tmp:
            tmp=Path(tmp); c=tmp/'test.c'; exe=tmp/'test'; save=tmp/'game.sav'
            c.write_text(source); save.write_bytes(b'disposable save bytes')
            before=save.read_bytes()
            result=subprocess.run(['cc','-std=gnu99','-DPORTABLE','-Wall','-Wextra','-Werror',
                '-iquote',str(ROOT),'-iquote',str(ROOT/'include'),str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe),str(save)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(save.read_bytes(),before)
