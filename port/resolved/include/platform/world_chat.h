#ifndef GUARD_PLATFORM_WORLD_CHAT_H
#define GUARD_PLATFORM_WORLD_CHAT_H
#ifdef PORTABLE
#include <SDL2/SDL.h>
#ifdef _WIN32
/* Windows client integration remains separately owned. */
#define WORLD_CHAT_HEIGHT 0
#else
#define WORLD_CHAT_HEIGHT 64
#endif
/* Graphical thread only. Rendering is outside the deterministic GBA image. */
int WorldChat_Event(const SDL_Event *event);
int WorldChat_BlocksInput(void);
void WorldChat_Draw(SDL_Renderer *renderer);
#endif
#endif
