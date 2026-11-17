#include <assert.h>
#include <stddef.h>
typedef unsigned char u8;typedef short s16;
#define TRUE 1
#define MART_TYPE_NORMAL 0
#define MART_TYPE_DECOR 1
#define WIN_ITEM_LIST 0
#define FLAG_SET_ITEM_OBTAINED 1
#define GAME_STAT_SHOPPED 1
#define SE_SHOP 1
#define WIN_MONEY 1
#define tItemId data[5]
#define tItemCount data[1]
struct{ s16 data[8];void(*func)(u8);}gTasks[1];
struct{unsigned totalCost;}shop,*sShopData=&shop;
struct{unsigned money;}save,*gSaveBlock1Ptr=&save;
struct{int martType;}sMartInfo;
static int sCommunityPurchase,room=1,credits,reports,moneyRemoved;static void(*next)(u8);
static const u8 gText_HereYouGoThankYou[1],gText_NoMoreRoomForThis[1],gText_ThankYouIllSendItHome[1],gText_ThanksIllSendItHome[1],gText_SpaceForVar1Full[1];
void PutWindowTilemap(int w){(void)w;}int AddBagItem(int item,int qty){assert(item==43&&qty==3);credits+=room;return room;}
void GetSetItemObtained(int i,int f){(void)i;(void)f;}void RecordItemPurchase(u8 t){(void)t;}
void BuyMenuReturnToItemList(u8 t){(void)t;}void BuyMenuSubtractMoney(u8);
void BuyMenuDisplayMessage(u8 t,const u8*text,void(*cb)(u8)){(void)t;(void)text;next=cb;}
int DecorationAdd(int item){(void)item;return 0;}void IncrementGameStat(int s){(void)s;}
void RemoveMoney(unsigned*p,unsigned cost){assert(credits>0);*p-=cost;moneyRemoved++;}
int WorldMarket_Purchased(unsigned item,unsigned qty){assert(item==43&&qty==3&&moneyRemoved);reports++;return 1;}
void PlaySE(int s){(void)s;}unsigned GetMoney(unsigned*p){return *p;}void PrintMoneyAmountInMoneyBox(int w,unsigned n,int c){(void)w;(void)n;(void)c;}
void Task_ReturnToItemListAfterItemPurchase(u8 t){(void)t;}void Task_ReturnToItemListAfterDecorationPurchase(u8 t){(void)t;}
ACTUAL_FUNCTIONS
int main(void){gTasks[0].data[5]=43;gTasks[0].data[1]=3;shop.totalCost=300;save.money=1000;sCommunityPurchase=1;
 room=0;BuyMenuTryMakePurchase(0);assert(!credits&&!reports&&save.money==1000&&next==BuyMenuReturnToItemList);
 room=1;BuyMenuTryMakePurchase(0);assert(credits==1&&!reports&&save.money==1000&&next==BuyMenuSubtractMoney);next(0);assert(save.money==700&&reports==1);
 sCommunityPurchase=0;BuyMenuTryMakePurchase(0);next(0);assert(save.money==400&&reports==1);return 0;}
