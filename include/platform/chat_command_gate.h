#ifndef GUARD_CHAT_COMMAND_GATE_H
#define GUARD_CHAT_COMMAND_GATE_H
#include <string.h>
/* Protocol records, never CHATMSG text, authorize a command family. */
#define CHAT_COMMAND_STORY 1u
#define CHAT_COMMAND_MYSTERY 2u
#define CHAT_COMMAND_GUILD 4u
#define CHAT_COMMAND_EXPLORE 8u
static inline int ChatCommandGate_Record(unsigned *mask, unsigned *seen,
                                        unsigned version, unsigned incoming, int negotiated)
{
    if (!negotiated || *seen || version != 1 || incoming > 15) return 0;
    *mask = incoming; *seen = 1;
    return 1;
}
static inline int ChatCommandGate_Complete(int negotiated, unsigned seen)
{
    return negotiated ? seen == 1 : seen == 0;
}
static inline int ChatCommandGate_Allowed(unsigned mask, const char *target, const char *text)
{
    char name[10]; unsigned length = 0, bit = 0;
    while (*text == ' ') text++;
    if (*text != '/') return 1;
    if (strcmp(target, "*")) return 0;
    while (*text && *text != ' ') {
        unsigned char c = *text++;
        if (length + 1 >= sizeof(name)) return 0;
        name[length++] = c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c;
    }
    name[length] = 0;
    if (!strcmp(name, "/story")) bit = CHAT_COMMAND_STORY;
    else if (!strcmp(name, "/mystery")) bit = CHAT_COMMAND_MYSTERY;
    else if (!strcmp(name, "/guild") || !strcmp(name, "/g")) bit = CHAT_COMMAND_GUILD;
    else if (!strcmp(name, "/explore")) bit = CHAT_COMMAND_EXPLORE;
    return bit && (mask & bit);
}
#endif
