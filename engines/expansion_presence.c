/* Read-only adapter compiled against the donor's public inspection interface.
 * No vanilla engine headers, Pokemon layouts or save bytes cross this seam.
 * --wrap affects BIOS calls to frame_run, preserving the donor's frame hook. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "platform/frame.h"
#include "platform/inspect.h"

void ExpansionPeers_Update(int overworld);
enum frame_result __real_frame_run(void);
enum frame_result __wrap_frame_run(void)
{
    enum frame_result result = __real_frame_run();
    const char *path = getenv("EW_EXPANSION_PRESENCE");
    if (path == NULL || frame_count() % 6 != 0)
        return result;
    char map[256], pos[256], callback[256], battle[256];
    inspect_get("map", map, sizeof map);
    inspect_get("pos", pos, sizeof pos);
    inspect_get("callback2", callback, sizeof callback);
    inspect_get("in_battle", battle, sizeof battle);
    unsigned group = 0, num = 0, x = 0, y = 0;
    int field = sscanf(map, "%u.%u", &group, &num) == 2
             && sscanf(pos, "%u,%u", &x, &y) == 2
             && strcmp(callback, "CB2_Overworld") == 0
             && strcmp(battle, "0") == 0;
    if (getenv("EW_EXPERIMENTAL_EXPANSION_PEERS") != NULL)
        ExpansionPeers_Update(field);
    char temporary[4096];
    if (snprintf(temporary, sizeof temporary, "%s.tmp", path) >= (int)sizeof temporary)
        return result;
    FILE *out = fopen(temporary, "w");
    if (out != NULL) {
        int written = fprintf(out, "{\"schema\":1,\"engine\":\"expansion-native\",\"frame\":%u,"
                          "\"field\":%s,\"group\":%u,\"num\":%u,\"x\":%u,\"y\":%u}\n",
                          frame_count(), field ? "true" : "false", group, num, x, y);
        int closed = fclose(out);
        if (written > 0 && closed == 0)
            (void)rename(temporary, path);
    }
    return result;
}

