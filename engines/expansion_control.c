/* Opt-in Expansion control bridge. Its observation schema is intentionally
 * limited and does not claim vanilla player-state compatibility. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "platform/frame.h"
#include "platform/gba_memmap.h"
#include "platform/inspect.h"
#include "platform/player_control.h"

static bool active, previous_tick;
static void observation(FILE *out, uint32_t frame)
{
    char map[64] = "", pos[64] = "", battle[64] = "";
    unsigned group = 0, number = 0, x = 0, y = 0;
    inspect_get("map", map, sizeof map);
    inspect_get("pos", pos, sizeof pos);
    inspect_get("in_battle", battle, sizeof battle);
    bool has_map = sscanf(map, "%u.%u", &group, &number) == 2;
    bool has_pos = sscanf(pos, "%u,%u", &x, &y) == 2;
    fprintf(out, "{\"frame\":%u,\"engine\":\"expansion-native\",\"schema\":\"expansion-observation-1\",\"map\":", frame);
    if (has_map) fprintf(out, "[%u,%u]", group, number); else fputs("null", out);
    fputs(",\"pos\":", out);
    if (has_pos) fprintf(out, "[%u,%u]", x, y); else fputs("null", out);
    fprintf(out, ",\"battle\":%s}", battle[0] == '1' && battle[1] == '\0' ? "true" : battle[0] == '0' && battle[1] == '\0' ? "false" : "null");
}
static bool screenshot(FILE *out)
{
    const uint16_t *pixels = frame_pixels();
    if (!pixels || fprintf(out, "P6\n240 160\n255\n") < 0) return false;
    for (size_t i = 0; i < 240u * 160u; i++) {
        uint16_t v = pixels[i];
        unsigned char rgb[3] = {(v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3};
        if (fwrite(rgb, 1, 3, out) != 3) return false;
    }
    return !ferror(out);
}
/* Called just before the donor frame, after the game consumed the preceding
 * keypad sample. Calling AfterFrame any earlier would acknowledge a press
 * before the game ran with it. */
bool ExpansionControl_BeforeFrame(void)
{
    static bool attempted;
    if (!attempted) {
        attempted = true;
        const char *endpoint = getenv("EW_EXPANSION_CONTROL");
        const char *save = getenv("EW_EXPANSION_SAVE");
        if (endpoint) {
            if (!save || !PlayerControl_Init(endpoint, save, observation, screenshot)) return false;
            active = true;
        }
    }
    if (active && previous_tick) PlayerControl_AfterFrame(frame_count());
    return true;
}
/* KEYINPUT is active-low. The donor writes host input during frame_run; agent
 * control is exclusive and replaces it only when explicitly enabled. */
void ExpansionControl_AfterFrame(void)
{
    if (!active) return;
    PlayerControl_BeforeFrame();
    *gba_io_u16(0x130) = (uint16_t)(~PlayerControl_Buttons() & 0x03ff);
    previous_tick = true;
}
