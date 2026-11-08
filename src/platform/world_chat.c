#ifdef PORTABLE
#include <stdio.h>
#include <string.h>
#include <SDL2/SDL.h>
#include "gba/types.h"
#include "fonts.h"
#include "platform/world_bridge.h"
#include "platform/world_chat.h"
#include "platform/settings.h"

static struct {
    int editing, releaseKeys;
    unsigned scroll;
    char draft[152], hint[96];
} sChat;

static int Identifier(const char *text)
{
    size_t i, length = strlen(text);
    if (!length || length > 24) return 0;
    for (i = 0; i < length; i++)
        if (!((text[i] >= 'a' && text[i] <= 'z') || (text[i] >= 'A' && text[i] <= 'Z')
           || (text[i] >= '0' && text[i] <= '9') || text[i] == '_' || text[i] == '-')) return 0;
    return 1;
}

static void Submit(void)
{
    char copy[152], *text = copy, *target = "*", *space;
    strcpy(copy, sChat.draft);
    if (!strncmp(copy, "/w ", 3)) {
        target = copy + 3;
        space = strchr(target, ' ');
        if (!space) goto invalid;
        *space = 0;
        text = space + 1;
        if (!Identifier(target)) goto invalid;
    }
    if (!*text || strlen(text) > 120) goto invalid;
    if (!WorldBridge_ChatCommandAllowed(target, text)) {
        strcpy(sChat.hint, "Private commands need a supported client/server session.");
        return;
    }
    if (!WorldBridge_ChatSend(target, text)) {
        strcpy(sChat.hint, "Not sent. Check connection or try again.");
        return;
    }
    /* The server's echo is the delivery receipt, never a fabricated local line. */
    strcpy(sChat.hint, "Queued. Check history for delivery.");
    sChat.draft[0] = 0;
    sChat.editing = 0;
    sChat.scroll = 0;
    sChat.releaseKeys = 1;
    SDL_StopTextInput();
    return;
invalid:
    strcpy(sChat.hint, "1-120 characters. Private: /w trainer text");
}

int WorldChat_OpenGuild(void)
{
    if (!WORLD_CHAT_HEIGHT || !WorldBridge_Enabled() || sChat.editing) return 0;
    sChat.editing = 1;
    sChat.scroll = 0;
    strcpy(sChat.draft, "/guild help");
    strcpy(sChat.hint, "Press Enter for guild commands.");
    SDL_FlushEvent(SDL_TEXTINPUT);
    SDL_StartTextInput();
    return 1;
}

int WorldChat_Event(const SDL_Event *event)
{
    size_t length;
    if (!WORLD_CHAT_HEIGHT || !WorldBridge_Enabled()) return 0;
    if (event->type == SDL_WINDOWEVENT && event->window.event == SDL_WINDOWEVENT_FOCUS_LOST) {
        sChat.editing = 0;
        sChat.releaseKeys = 1;
        SDL_StopTextInput();
        return 0;
    }
    if (event->type == SDL_TEXTINPUT && sChat.editing) {
        const unsigned char *p = (const unsigned char *)event->text.text;
        const unsigned char *check;
        for (check = p; *check; check++) if (*check < 32 || *check > 126) {
            strcpy(sChat.hint, "Chat accepts printable ASCII only.");
            return 1;
        }
        length = strlen(sChat.draft);
        for (; *p; p++) {
            if (*p >= 32 && *p <= 126 && length < sizeof(sChat.draft)-1)
                sChat.draft[length++] = *p;
        }
        sChat.draft[length] = 0;
        return 1;
    }
    if (event->type != SDL_KEYDOWN) return 0;
    if (!sChat.editing && (event->key.keysym.sym == SDLK_PAGEUP || event->key.keysym.sym == SDLK_PAGEDOWN)
     && Input_KeyIsBound(event->key.keysym.scancode)) return 0;
    if (event->key.keysym.sym == SDLK_PAGEUP) {
        if (sChat.scroll < 125) sChat.scroll += 3;
        return 1;
    }
    if (event->key.keysym.sym == SDLK_PAGEDOWN) {
        sChat.scroll = sChat.scroll > 3 ? sChat.scroll - 3 : 0;
        return 1;
    }
    if (!sChat.editing) {
        if (event->key.keysym.sym != SDLK_t || event->key.repeat
         || (event->key.keysym.mod & (KMOD_ALT | KMOD_GUI))) return 0;
        /* Configured game input wins on plain T. Ctrl+T stays available even
         * when T is assigned to Start, another game button, or fast-forward. */
        if (!(event->key.keysym.mod & KMOD_CTRL)
         && Input_KeyIsBound(SDL_GetScancodeFromKey(SDLK_t))) return 0;
        sChat.editing = 1;
        sChat.hint[0] = 0;
        SDL_FlushEvent(SDL_TEXTINPUT);
        SDL_StartTextInput();
        return 1;
    }
    switch (event->key.keysym.sym) {
    case SDLK_RETURN:
        if (!event->key.repeat) Submit();
        break;
    case SDLK_ESCAPE:
        sChat.draft[0] = 0;
        sChat.editing = 0;
        sChat.releaseKeys = 1;
        SDL_StopTextInput();
        break;
    case SDLK_BACKSPACE:
        length = strlen(sChat.draft);
        if (length) sChat.draft[length-1] = 0;
        break;
    default:
        break;
    }
    /* Typing shortcuts cannot reset/pause the game or select battle moves. */
    return 1;
}

int WorldChat_BlocksInput(void)
{
    int count, i;
    const Uint8 *keys;
    if (sChat.editing) return 1;
    if (!sChat.releaseKeys) return 0;
    keys = SDL_GetKeyboardState(&count);
    /* Only game-bound keys can leak a typing action into gameplay. Lock keys
     * (notably Num Lock in Xephyr) may remain reported as down indefinitely. */
    for (i = 0; i < count; i++)
        if (keys[i] && Input_KeyIsBound((SDL_Scancode)i)) return 1;
    sChat.releaseKeys = 0;
    return 0;
}

/* Emerald's existing Latin font supplies letters. These original 5x7 glyphs
 * cover ASCII punctuation that has no glyph in the game font. No text reaches
 * Emerald's command decoder and rendering does not change its font globals. */
static const struct { char ascii; unsigned char rows[7]; } sSymbols[] = {
    {'#',{10,31,10,10,31,10,0}}, {'$',{4,15,20,14,5,30,4}},
    {'%',{17,2,4,8,17,0,0}}, {'&',{12,18,20,8,21,18,13}},
    {'(',{2,4,8,8,8,4,2}}, {')',{8,4,2,2,2,4,8}},
    {'*',{0,21,14,31,14,21,0}}, {'+',{0,4,4,31,4,4,0}},
    {';',{0,4,0,0,4,4,8}}, {'<',{1,2,4,8,4,2,1}},
    {'=',{0,0,31,0,31,0,0}}, {'>',{16,8,4,2,4,8,16}},
    {'@',{14,17,23,21,23,16,14}}, {'[',{14,8,8,8,8,8,14}},
    {'\\',{16,8,8,4,2,2,1}}, {']',{14,2,2,2,2,2,14}},
    {'^',{4,10,17,0,0,0,0}}, {'_',{0,0,0,0,0,0,31}},
    {'`',{8,4,2,0,0,0,0}}, {'{',{2,4,4,8,4,4,2}},
    {'|',{4,4,4,4,4,4,4}}, {'}',{8,4,4,2,4,4,8}},
    {'~',{0,0,9,22,0,0,0}}
};

static unsigned Glyph(unsigned char c)
{
    if (c >= 'A' && c <= 'Z') return 0xBB + c - 'A';
    if (c >= 'a' && c <= 'z') return 0xD5 + c - 'a';
    if (c >= '0' && c <= '9') return 0xA1 + c - '0';
    switch (c) {
    case '!': return 0xAB;
    case '?': return 0xAC;
    case '.': return 0xAD;
    case '-': return 0xAE;
    case '"': return 0xB1;
    case '\'': return 0xB4;
    case ',': return 0xB8;
    case '/': return 0xBA;
    case ':': return 0xF0;
    default: return 0;
    }
}

static unsigned Width(unsigned char c)
{
    unsigned glyph = Glyph(c);
    return glyph ? gFontSmallLatinGlyphWidths[glyph] + 1 : 6;
}

static void DrawGlyph(SDL_Renderer *renderer, unsigned char c, int x, int y)
{
    unsigned glyph = Glyph(c), row, col, i;
    if (glyph) {
        const u16 *data = gFontSmallLatinGlyphs + 32*glyph;
        for (row = 0; row < 12; row++)
            for (col = 0; col < gFontSmallLatinGlyphWidths[glyph]; col++) {
                u16 bits = data[(row/8)*16 + (col/8)*8 + row%8];
                unsigned pixel = (bits >> (2*(7-col%8))) & 3;
                if (pixel == 1) SDL_RenderDrawPoint(renderer, x+col, y+row);
            }
    } else {
        for (i = 0; i < sizeof(sSymbols)/sizeof(sSymbols[0]); i++)
            if (sSymbols[i].ascii == c)
                for (row = 0; row < 7; row++)
                    for (col = 0; col < 5; col++)
                        if (sSymbols[i].rows[row] & (16 >> col))
                            SDL_RenderDrawPoint(renderer, x+col, y+row+3);
    }
}

static void DrawText(SDL_Renderer *renderer, const char *text, int y)
{
    unsigned x = 3;
    for (; *text && x + Width(*text) <= 237; text++) {
        DrawGlyph(renderer, *text, x, y);
        x += Width(*text);
    }
}

void WorldChat_Draw(SDL_Renderer *renderer)
{
    char rows[128][64] = {{0}}, line[184], heading[96];
    unsigned i, row = 0, col = 0, pixels = 0, end, start;
    const char *p, *status;
    const char *shortcut = Input_KeyIsBound(SDL_GetScancodeFromKey(SDLK_t)) ? "Ctrl+T" : "T";
    SDL_Rect strip = {0,0,240,WORLD_CHAT_HEIGHT};
    if (!WORLD_CHAT_HEIGHT || !WorldBridge_Enabled()) return;
    SDL_SetRenderDrawColor(renderer, 16,24,32,255);
    SDL_RenderFillRect(renderer, &strip);
    SDL_SetRenderDrawColor(renderer, 210,235,220,255);
    status = WorldBridge_ChatStatus();
    if (!strcmp(status, "unsupported")) status = "Server does not support chat.";
    else if (!strcmp(status, "slow")) status = "Slow down. Message not sent.";
    else if (!strcmp(status, "unavailable")) status = "Trainer unavailable. Not sent.";
    if (sChat.editing && sChat.hint[0]) snprintf(heading, sizeof(heading), "%s", sChat.hint);
    else snprintf(heading, sizeof(heading), "Chat %s | %s | PgUp/PgDn", status, shortcut);
    DrawText(renderer, heading, 0);
    for (i = 0; i < WorldBridge_ChatCount(); i++) {
        WorldBridge_ChatLine(i, line, sizeof(line));
        col = pixels = 0;
        for (p = line; *p && row < 127; p++) {
            if (pixels + Width(*p) > 234 || col == 63) {
                rows[row++][col] = 0;
                col = pixels = 0;
            }
            rows[row][col++] = *p;
            pixels += Width(*p);
        }
        rows[row++][col] = 0;
        if (row == 128) break;
    }
    if (sChat.scroll > (row > 3 ? row - 3 : 0)) sChat.scroll = row > 3 ? row - 3 : 0;
    end = row - sChat.scroll;
    start = end > 3 ? end - 3 : 0;
    for (i = start; i < end; i++) DrawText(renderer, rows[i], 12+12*(i-start));
    SDL_SetRenderDrawColor(renderer, 255,228,160,255);
    if (sChat.editing) {
        pixels = 0;
        p = sChat.draft + strlen(sChat.draft);
        while (p > sChat.draft && pixels + Width(p[-1]) < 222) pixels += Width(*--p);
        snprintf(line, sizeof(line), "> %s_", p);
        DrawText(renderer, line, 50);
    } else if (sChat.hint[0]) DrawText(renderer, sChat.hint, 50);
    else {
        snprintf(line, sizeof(line), "%s to chat. Private: /w trainer text", shortcut);
        DrawText(renderer, line, 50);
    }
}
#endif /* PORTABLE */

