/* Synthetic pixel fixtures for the actual native OBJ renderer, not gameplay
 * evidence. Checks RC7's extra tile bank, sorted overlap and bad metadata. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gba_memmap.h"
#include "ppu_internal.h"

static void word(uintptr_t address, uint16_t value)
{
    *(volatile uint16_t *)address = value;
}
static void attr(unsigned obj, unsigned field, uint16_t value)
{
    word(GBA_OAM_BASE + obj * 8u + field * 2u, value);
}
int main(void)
{
    assert(gba_memmap_init() == GBA_MEMMAP_OK);
    assert(GBA_VRAM_SIZE == 0x20000u);
    assert(GBA_OAM_SIZE == 0x600u);
    for (unsigned i = 0; i < 192u; ++i) {
        attr(i, 0, 0x0200u);
        attr(i, 1, 0); attr(i, 2, 0); attr(i, 3, 0);
    }
    memset((void *)(uintptr_t)(GBA_VRAM_BASE + 0x10000u), 0x11, 32);
    memset((void *)(uintptr_t)(GBA_VRAM_BASE + 0x18000u), 0x22, 32);
    word(GBA_PALETTE_RAM_BASE + (256u + 1u) * 2u, 0x001fu);
    word(GBA_PALETTE_RAM_BASE + (256u + 2u) * 2u, 0x03e0u);
    attr(0, 0, 0); attr(128, 0, 0);
    attr(128, 3, 0x8000u);
    attr(191, 0, 0xc2ffu); attr(191, 1, 0xc1ffu);
    attr(191, 2, 0xffffu); // The priority bits are deliberately not zero.
    attr(191, 3, 0x4000u | (1u << 8u) | 1u);
    struct ppu_regs regs = {0};
    regs.dispcnt = PPU_DISPCNT_OBJ_1D;
    struct ppu_obj_line line;
    ppu_obj_render_line(&regs, 0, &line);
    assert(line.colour[0] == 0x03e0u);
    attr(128, 3, 0x8001u);
    ppu_obj_render_line(&regs, 0, &line);
    assert(line.colour[0] == 0x001fu);
    attr(128, 3, 0x8002u); // Out-of-range rank must fail closed to physical order.
    ppu_obj_render_line(&regs, 0, &line);
    assert(line.colour[0] == 0x001fu);
    puts("PASS: native extra-bank pixels, shared draw order, malformed metadata fallback");
    gba_memmap_shutdown();
    return 0;
}
