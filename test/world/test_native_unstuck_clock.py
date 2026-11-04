"""Compile the real cooldown store against disposable private files."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NativeUnstuckClockTests(unittest.TestCase):
    def test_cooldown_persistence_override_and_unsafe_files(self):
        source = r'''
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <unistd.h>
#include "platform/native_unstuck.h"
int main(int argc, char **argv) {
 char save[4096], side[4096]; unsigned left=0; FILE *f;
 assert(argc==2); snprintf(save,sizeof(save),"%s/game.sav",argv[1]);
 snprintf(side,sizeof(side),"%s/game.sav.unstuck",argv[1]);
 f=fopen(save,"w"); assert(f); fputs("private save sentinel",f); fclose(f); chmod(save,0600);
 char saveAlias[4096], linkedSave[4096];
 snprintf(saveAlias,sizeof(saveAlias),"%s/save-link",argv[1]);
 snprintf(linkedSave,sizeof(linkedSave),"%s/save-hardlink",argv[1]);
 assert(symlink(save,saveAlias)==0);
 assert(NativeUnstuck_Reserve(saveAlias,1000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(unlink(saveAlias)==0); assert(link(save,linkedSave)==0);
 assert(NativeUnstuck_Reserve(save,1000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(unlink(linkedSave)==0);
 assert(NativeUnstuck_Reserve("relative.sav",1000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(NativeUnstuck_Reserve(save,0,0,&left)==NATIVE_UNSTUCK_BAD_CLOCK);
 assert(NativeUnstuck_Reserve(save,1000,0,&left)==NATIVE_UNSTUCK_ALLOWED);
 assert(NativeUnstuck_Reserve(save,1100,0,&left)==NATIVE_UNSTUCK_COOLDOWN && left==200);
 assert(NativeUnstuck_Reserve(save,999,0,&left)==NATIVE_UNSTUCK_COOLDOWN);
 assert(NativeUnstuck_Reserve(save,1100,1,&left)==NATIVE_UNSTUCK_ALLOWED);
 assert(NativeUnstuck_Reserve(save,1399,0,&left)==NATIVE_UNSTUCK_COOLDOWN && left==1);
 assert(NativeUnstuck_Reserve(save,1400,0,&left)==NATIVE_UNSTUCK_ALLOWED);
 f=fopen(save,"r"); assert(f); char original[32]; assert(fgets(original,sizeof(original),f)); fclose(f);
 assert(!strcmp(original,"private save sentinel")); /* save remains byte-identical */
 char alias[4096]; snprintf(alias,sizeof(alias),"%s/alias",argv[1]);
 assert(link(side,alias)==0);
 assert(NativeUnstuck_Reserve(save,2000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(unlink(alias)==0); assert(chmod(side,0644)==0);
 assert(NativeUnstuck_Reserve(save,2000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(chmod(side,0600)==0); int lockfd=open(side,O_RDWR); assert(lockfd>=0 && !flock(lockfd,LOCK_EX|LOCK_NB));
 assert(NativeUnstuck_Reserve(save,2000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR); close(lockfd);
 assert(unlink(side)==0); assert(symlink("target",side)==0);
 assert(NativeUnstuck_Reserve(save,2000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 assert(unlink(side)==0); f=fopen(side,"w"); assert(f); fclose(f); chmod(side,0600);
 assert(NativeUnstuck_Reserve(save,2000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 f=fopen(side,"w"); assert(f); fputs("not our data",f); fclose(f);
 assert(NativeUnstuck_Reserve(save,2000,0,&left)==NATIVE_UNSTUCK_STORAGE_ERROR);
 f=fopen(side,"r"); assert(f); char b[32]; assert(fgets(b,sizeof(b),f)); fclose(f); assert(!strcmp(b,"not our data"));
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='unstuck-clock-') as d:
            c, exe = Path(d)/'test.c', Path(d)/'test'
            c.write_text(source)
            subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE', '-iquote',str(ROOT/'include'), str(c),str(ROOT/'src/platform/native_unstuck.c'),str(ROOT/'src/platform/native_save.c'),'-o',str(exe)],check=True,capture_output=True)
            subprocess.run([str(exe), d],check=True,capture_output=True)
