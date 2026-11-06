#include <assert.h>
#include <stdlib.h>
static int unlocked;
int FlagGet(int id){assert(id==0x4007);return unlocked;}
void FlagSet(int id){assert(id==0x4007);unlocked=1;}
void FlagClear(int id){assert(id==0x4007);unlocked=0;}
int ExpansionDexNav_Enabled(void);void ExpansionDexNav_Update(void);
int main(void){unsetenv("EW_EXPERIMENTAL_EXPANSION_DEXNAV");ExpansionDexNav_Update();assert(!unlocked&&!ExpansionDexNav_Enabled());setenv("EW_EXPERIMENTAL_EXPANSION_DEXNAV","1",1);ExpansionDexNav_Update();assert(unlocked&&ExpansionDexNav_Enabled());setenv("EW_EXPERIMENTAL_EXPANSION_DEXNAV","0",1);ExpansionDexNav_Update();assert(!unlocked);return 0;}
