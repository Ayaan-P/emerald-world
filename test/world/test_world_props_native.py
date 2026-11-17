"""Compile actual Expansion prop parser and graphics selector with explicit engine doubles."""
import os,subprocess,tempfile,unittest
from pathlib import Path

def parser_binary(root,directory):
 source=(Path(root)/'src/world/world_bridge.c').read_text()
 begin=source.index('    if (!strcmp(tokens[0], "OBJECT") ||')
 brace=source.index('{',begin);depth=1;end=brace+1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 block=source[begin:end]
 start=source.index('static u16 WorldPropGraphics(');stop=source.index('\n}',start)+2
 c=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
typedef int bool8;typedef unsigned short u16;
#define TRUE 1
#define FALSE 0
#define GENERATED_WORLD_XL 1
#define GENERATED_MAP_READY 1
#define WB_REMOTES 16
#define WB_OBJECTS 8
#define OBJ_EVENT_GFX_BREAKABLE_ROCK 86
#define OBJ_EVENT_GFX_PUSHABLE_BOULDER 87
struct Peer {char id[26],text[58],characterRegion[65];unsigned group,num,x,y,gfx,facing,ready,propKind;};
static struct {int worldPropsLegacy,characterRegionLegacy,characterLegacy;struct {unsigned peerCount,objectCount;struct Peer peers[16];}stage;}sWorld;
static char *region;
static int CharacterRegionReady(char *v){return !strcmp(v,region);}
static int Identifier(char *v){return strlen(v)>0&&strlen(v)<=24;}
static int ObjectText(char *v,char *out){if(strlen(v)>112)return 0;strcpy(out,"text");return 1;}
static int Decimal(char *v,unsigned *out){char *end;unsigned long n=strtoul(v,&end,10);if(!*v||*end||n>65535)return 0;*out=n;return 1;}
static int IsGeneratedCaveMap(unsigned g,unsigned n){(void)g;(void)n;return 1;}
static int MapCoords(unsigned g,unsigned n,unsigned x,unsigned y){return g<256&&n<256&&x<127&&y<127;}
'''+source[start:stop]+'\nstatic int Parse(unsigned n,char **tokens){unsigned i,v[8];\n'+block+'\nreturn 0;}\n'+r'''
int main(int argc,char **argv){char *tokens[16],*p;unsigned n=0;if(argc!=4)return 2;region=argv[2];sWorld.worldPropsLegacy=atoi(argv[3]);for(p=strtok(argv[1]," ");p&&n<16;p=strtok(NULL," "))tokens[n++]=p;int ok=Parse(n,tokens);printf("%d %u %u\n",ok,sWorld.stage.peers[0].propKind,ok?WorldPropGraphics(sWorld.stage.peers[0].propKind):0);return 0;}
'''
 path=Path(directory)/'props.c';path.write_text(c);binary=Path(directory)/'props'
 subprocess.run(['cc','-std=c99','-Wall','-Werror',str(path),'-o',str(binary)],check=True,capture_output=True)
 return binary

class NativePropTests(unittest.TestCase):
 def test_actual_region_prop_parser_and_graphics_selection(self):
  root=os.environ.get('EW_NATIVE_SOURCE')
  if not root:self.skipTest('Exact native candidate required')
  revision='a'*64
  with tempfile.TemporaryDirectory() as tmp:
   binary=parser_binary(root,tmp)
   def run(line,legacy='0'):return subprocess.check_output([str(binary),line,revision,legacy],text=True).strip()
   row='REGION_PROP '+revision+' fixture 0 1 72 70 0 4869'
   self.assertEqual(run(row),'1 1 86');self.assertEqual(run(row.replace('70 0','70 1')),'1 2 87')
   self.assertTrue(run(row,'1').startswith('0 '));self.assertTrue(run(row.replace(revision,'b'*64)).startswith('0 '))
   self.assertTrue(run(row.replace('70 0','70 7')).startswith('0 '))
   self.assertTrue(run(row.replace('REGION_PROP','REGION_OBJECT')).startswith('0 '))
