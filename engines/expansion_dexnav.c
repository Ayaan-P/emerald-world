/* Runtime gate for the donor's existing DexNav. The unlock flag is transient:
 * this never writes a persistent trainer flag, and defaults to disabled. */
#include <stdlib.h>
#include <string.h>
#include "global.h"
#include "event_data.h"
#include "config/dexnav.h"
bool8 ExpansionDexNav_Enabled(void)
{
    const char *enabled=getenv("EW_EXPERIMENTAL_EXPANSION_DEXNAV");
    return enabled && !strcmp(enabled,"1");
}
void ExpansionDexNav_Update(void)
{
    if (ExpansionDexNav_Enabled()) FlagSet(DN_FLAG_DEXNAV_GET);
    else FlagClear(DN_FLAG_DEXNAV_GET);
}
