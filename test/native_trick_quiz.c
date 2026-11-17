#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;typedef unsigned char bool8;
#define TRUE 1
#define FALSE 0
#define MAP_ROUTE110_TRICK_HOUSE_PUZZLE5 7431
#define MAP_GROUP(m) ((m)>>8)
#define MAP_NUM(m) ((m)&255)
#define VAR_TRICK_HOUSE_LEVEL 1
#define VAR_TEMP_8 2
#define EOS 255
#define CHAR_A 'A'
#define CHAR_a 'a'
#define CHAR_0 '0'
#define CHAR_PROMPT_SCROLL 250
#define CHAR_NEWLINE '\n'
#define CHAR_PERIOD '.'
#define CHAR_COMMA ','
#define CHAR_QUESTION_MARK '?'
#define CHAR_EXCL_MARK '!'
#define CHAR_SGL_QUOTE_RIGHT '\''
#define CHAR_HYPHEN '-'
#define CHAR_SPACE ' '
struct {int inBattle;}gMain;
struct SB1 {struct {unsigned mapGroup,mapNum;}location;} b1,*gSaveBlock1Ptr=&b1;
struct SB2 {u8 playerTrainerId[4];}b2,*gSaveBlock2Ptr=&b2;
struct ListMenuItem {const u8 *name;int id;};
unsigned gSpecialVar_Result,level=4,doll=1,sends,fail_alloc;
u8 gStringVar1[32],gStringVar4[1000];
unsigned VarGet(unsigned v){return v==VAR_TRICK_HOUSE_LEVEL?level:doll;}
void *Alloc(unsigned n){return fail_alloc?NULL:malloc(n);}void *AllocZeroed(unsigned n){return fail_alloc?NULL:calloc(1,n);}void Free(void *p){free(p);}
bool8 ScriptMenu_MultichoiceDynamic(unsigned a,unsigned b,unsigned count,struct ListMenuItem *items,unsigned c,unsigned d,unsigned e,unsigned f){unsigned i;(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;assert(count==3);for(i=0;i<count;i++){assert(items[i].id==(int)i);Free((void*)items[i].name);}Free(items);gSpecialVar_Result=255;return TRUE;}
int LinkTransport_TrickQuizSend(const char *s){assert(!strncmp(s,"TQ GET ",7));sends++;return 1;}
#include "ACTUAL_SOURCE"
#if EW_TRICK_QUIZ
static void line(char *s){char *t[16],*v=strtok(s," \n");unsigned n=0;while(v){t[n++]=v;v=strtok(NULL," \n");}WorldTrickQuiz_Line(n,t);}
static void pack(unsigned nonce){char s[300];unsigned i;snprintf(s,sizeof(s),"TQ BEGIN %u 1 5061636b",nonce);line(s);for(i=0;i<5;i++){snprintf(s,sizeof(s),"TQ ROW %u 1 %u 1 57686963683f 4f6e65 54776f 5468726565",nonce,i);line(s);}snprintf(s,sizeof(s),"TQ END %u 1",nonce);line(s);}
#endif
int main(void){
#if EW_TRICK_QUIZ
 unsigned old;b1.location.mapGroup=29;b1.location.mapNum=7;b2.playerTrainerId[0]=42;
 WorldTrickQuiz_Enter();WorldTrickQuiz_Update();assert(sends==1);old=sQuiz.nonce;pack(old+1);assert(!sQuiz.ready);pack(old);assert(sQuiz.ready);
 WorldTrickQuiz_Prepare();assert(gSpecialVar_Result==1);WorldTrickQuiz_Accept();assert(gSpecialVar_Result==2&&sQuiz.decision==1);
 WorldTrickQuiz_Reset();assert(sQuiz.ready); /* immutable accepted questions survive disconnect */
 WorldTrickQuiz_Choices();assert(gSpecialVar_Result==255);gSpecialVar_Result=1;WorldTrickQuiz_Grade();assert(gSpecialVar_Result==2);
 WorldTrickQuiz_Grade();assert(gSpecialVar_Result==0); /* no stale double answer */
 WorldTrickQuiz_Prepare();WorldTrickQuiz_Accept();WorldTrickQuiz_Choices();gSpecialVar_Result=0;WorldTrickQuiz_Grade();assert(gSpecialVar_Result==1);
 WorldTrickQuiz_Choices();gSpecialVar_Result=127;WorldTrickQuiz_Grade();assert(gSpecialVar_Result==0);
 fail_alloc=1;WorldTrickQuiz_Choices();assert(gSpecialVar_Result==0);fail_alloc=0;
 b2.playerTrainerId[0]++;WorldTrickQuiz_Prepare();assert(gSpecialVar_Result==0);b2.playerTrainerId[0]--;
 WorldTrickQuiz_Enter();assert(!sQuiz.ready);pack(old);assert(!sQuiz.ready);pack(sQuiz.nonce);WorldTrickQuiz_Decline();WorldTrickQuiz_Prepare();assert(gSpecialVar_Result==0);
 WorldTrickQuiz_Enter();pack(sQuiz.nonce);WorldTrickQuiz_Reset();assert(!sQuiz.ready);
 WorldTrickQuiz_Enter();for(old=0;old<601;old++)WorldTrickQuiz_Update();assert(!sQuiz.nonce);
 WorldTrickQuiz_Enter();pack(sQuiz.nonce);level=5;WorldTrickQuiz_Prepare();assert(gSpecialVar_Result==0);
#else
 WorldTrickQuiz_Enter();WorldTrickQuiz_Update();WorldTrickQuiz_Prepare();assert(!gSpecialVar_Result&&!sends);
#endif
 return 0;}
