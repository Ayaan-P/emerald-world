#include <stdint.h>
struct Pokemon { unsigned slot; };
extern struct Pokemon gParties[4][6]; extern uint8_t gPartiesCount[4];
enum { MON_DATA_SPECIES, MON_DATA_LEVEL, MON_DATA_HP, MON_DATA_MAX_HP, MON_DATA_STATUS, MON_DATA_MOVE1, MON_DATA_PP1=9, MON_DATA_EXP=13 };
unsigned GetMonData(struct Pokemon *, int);
