#include "stub.h"
#include <assert.h>
#include <stddef.h>
#include <string.h>
static u32 tera=1, dynamax, item, ball=1, move;
u32 GetMonData(struct Pokemon *p,u32 field) {
 if(field==MON_DATA_SPECIES)return p->box.nickname[0];
 if(field==MON_DATA_HELD_ITEM)return item;
 if(field==MON_DATA_POKEBALL)return ball;
 if(field==MON_DATA_TERA_TYPE)return tera;
 if(field==MON_DATA_DYNAMAX_LEVEL)return dynamax;
 if(field==MON_DATA_EXP)return 1;
 if(field>=MON_DATA_MOVE1 && field<MON_DATA_MOVE1+4)return move;
 return 0;
}
int IsSpeciesEnabled(u32 s){return s==1;}
int ExpansionTrade_PairValid(const void *,size_t);
int main(void){
 struct Pokemon pair[2]; memset(pair,0,sizeof pair);
 pair[0].box.nickname[0]=1;pair[0].box.language=2;pair[0].box.hasSpecies=1;
 pair[0].level=5;pair[0].mail=MAIL_NONE;pair[0].hp=5;pair[0].maxHP=5;
 assert(ExpansionTrade_PairValid(pair,sizeof pair));
 assert(!ExpansionTrade_PairValid(pair,sizeof pair-1));
 pair[0].box.checksum=1;assert(!ExpansionTrade_PairValid(pair,sizeof pair));pair[0].box.checksum=0;
 pair[0].box.nickname[0]=2;assert(!ExpansionTrade_PairValid(pair,sizeof pair));pair[0].box.nickname[0]=1;
 tera=NUMBER_OF_MON_TYPES;assert(!ExpansionTrade_PairValid(pair,sizeof pair));tera=1;
 dynamax=11;assert(!ExpansionTrade_PairValid(pair,sizeof pair));dynamax=0;
 move=MOVES_COUNT;assert(!ExpansionTrade_PairValid(pair,sizeof pair));move=0;
 item=ITEMS_COUNT;assert(!ExpansionTrade_PairValid(pair,sizeof pair));item=0;
 pair[0].box.nickname[1]=0xFC;assert(!ExpansionTrade_PairValid(pair,sizeof pair));
 return 0;
}
