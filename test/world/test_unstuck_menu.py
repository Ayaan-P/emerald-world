"""Compile the real menu builders and confirmation callbacks with controlled stubs."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_save_isolation import function

ROOT = Path(__file__).resolve().parents[2]

class UnstuckMenuTests(unittest.TestCase):
    def test_offline_menu_confirmation_and_online_exclusion(self):
        code=(ROOT/'src/start_menu.c').read_text()
        source=r'''
#include <assert.h>
typedef unsigned char u8; typedef unsigned char bool8;
#define FALSE 0
#define TRUE 1
#define FLAG_SYS_POKEDEX_GET 1
#define FLAG_SYS_POKEMON_GET 2
#define FLAG_SYS_POKENAV_GET 3
#define MENU_B_PRESSED -1
#define SAVE_IN_PROGRESS 0
#define SAVE_SUCCESS 1
#define SAVE_CANCELED 2
enum { MENU_ACTION_POKEDEX, MENU_ACTION_POKEMON, MENU_ACTION_BAG, MENU_ACTION_POKENAV, MENU_ACTION_PLAYER, MENU_ACTION_SAVE, MENU_ACTION_OPTION, MENU_ACTION_EXIT, MENU_ACTION_UNSTUCK };
enum WorldUnstuckUseResult { UNSTUCK_USE_STARTED,UNSTUCK_USE_ONLINE_UNSUPPORTED,UNSTUCK_USE_BLOCKED,UNSTUCK_USE_COOLDOWN,UNSTUCK_USE_STORAGE_ERROR };
static int online, chosen, begins, count; static u8 items[12];
static const u8 sText_UnstuckCooldown[]= "cooldown", sText_UnstuckStorage[]="storage", sText_UnstuckUnavailable[]="unavailable";
static u8 (*sSaveDialogCallback)(void);
static bool8 FlagGet(int f) {(void)f;return TRUE;}
static bool8 WorldBridge_Enabled(void) {return online;}
static void AddStartMenuAction(u8 item) {items[count++]=item;}
static void DisplayYesNoMenuWithDefault(int x) {assert(x==1);}
static int Menu_ProcessInputNoWrapClearOnChoose(void) {return chosen;}
static enum WorldUnstuckUseResult useResult;
static enum WorldUnstuckUseResult WorldUnstuck_Begin(void) {begins++;return useResult;}
static u8 UnstuckDismissCallback(void) {return 0;}
static void ShowSaveMessage(const u8 *message,u8 (*cb)(void)) {(void)message;sSaveDialogCallback=cb;}
static u8 UnstuckChoiceCallback(void);
'''
        for name in ('BuildNormalStartMenu','UnstuckYesNoCallback','UnstuckChoiceCallback'):
            source+=function(code,name)
        source+=r'''
int main(void) {
 BuildNormalStartMenu(); assert(count==9 && items[7]==MENU_ACTION_UNSTUCK && items[8]==MENU_ACTION_EXIT);
 count=0;online=1;BuildNormalStartMenu();assert(count==8 && items[7]==MENU_ACTION_EXIT);online=0;
 assert(UnstuckYesNoCallback()==SAVE_IN_PROGRESS && sSaveDialogCallback==UnstuckChoiceCallback);
 chosen=1;assert(UnstuckChoiceCallback()==SAVE_CANCELED && begins==0);
 chosen=MENU_B_PRESSED;assert(UnstuckChoiceCallback()==SAVE_CANCELED && begins==0);
 chosen=0;useResult=UNSTUCK_USE_COOLDOWN;assert(UnstuckChoiceCallback()==SAVE_IN_PROGRESS && begins==1 && sSaveDialogCallback==UnstuckDismissCallback);
 useResult=UNSTUCK_USE_STARTED;assert(UnstuckChoiceCallback()==SAVE_SUCCESS && begins==2);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='unstuck-menu-') as d:
            c,exe=Path(d)/'test.c',Path(d)/'test';c.write_text(source)
            p=subprocess.run(['cc','-std=gnu99','-DPORTABLE','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            subprocess.run([str(exe)],check=True,capture_output=True)
