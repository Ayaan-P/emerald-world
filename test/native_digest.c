#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8;typedef uint32_t u32;typedef unsigned bool8;
#define TRUE 1
#define FALSE 0
#define WORLD_BASE_WIRE_SIZE 154
#define WORLD_BASE_ROOM_BYTES 46
#define PLAYER_NAME_LENGTH 7
#define TRAINER_ID_LENGTH 4
#define DECOR_MAX_SECRET_BASE 16
#define PARTY_SIZE 6
#define MAX_MON_MOVES 4
#define SECRET_BASES_COUNT 20
#define FLAG_RECEIVED_SECRET_POWER 1
#define VAR_CURRENT_SECRET_BASE 1
#define GAME_LANGUAGE 2
#define NUM_DECORATIONS 120
#define MAP_SECRET_BASE_RED_CAVE1 0
#define MAP_GROUP(x) 25
struct SecretBase{u8 secretBaseId,gender,language,trainerName[7],trainerId[4],decorations[16],decorationPositions[16];struct{u32 personality[6];unsigned moves[24],species[6],heldItems[6],levels[6],EVs[6];}party;};
static struct{struct SecretBase secretBases[20];struct{unsigned mapGroup,mapNum;}location;}save,*gSaveBlock1Ptr=&save;
static unsigned index_,isbase=1,flag=1;static unsigned VarGet(unsigned x){(void)x;return index_;}static unsigned FlagGet(unsigned x){(void)x;return flag;}static unsigned CurMapIsSecretBase(void){return isbase;}
ACTUAL_HELPERS
int main(void){char out[65];unsigned g;save.location.mapGroup=25;save.secretBases[0].secretBaseId=1;save.secretBases[0].language=2;
 assert(WorldBase_RoomDigest(out));puts(out);save.secretBases[0].party.species[0]=999;save.secretBases[0].party.personality[0]=1234;assert(WorldBase_RoomDigest(out));puts(out);
 save.secretBases[0].decorations[0]=1;assert(WorldBase_RoomDigest(out));puts(out);
 for(g=0;g<24;g++){save.secretBases[0].secretBaseId=g*10+1;save.location.mapNum=(g%4)*6+g/4;assert(WorldBase_RoomDigest(out));save.location.mapNum=(save.location.mapNum+1)%24;assert(!WorldBase_RoomDigest(out));}
 index_=20;assert(!WorldBase_RoomDigest(out));index_=0;isbase=0;assert(!WorldBase_RoomDigest(out));return 0;}
