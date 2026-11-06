#ifndef EW_MAP_COMPAT_H
#define EW_MAP_COMPAT_H
/* True only when Expansion and the existing authority name this map at the
 * same group and map number. Generated maps are not supported by this slice. */
int EwMapSupported(unsigned group, unsigned map);
#endif
