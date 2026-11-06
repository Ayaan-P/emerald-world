"""Derive exact common map IDs without renumbering either source tree."""
import json

def ids(doc):
 result={}
 for group,key in enumerate(doc['group_order']):
  if group>255:raise ValueError('map group is too large')
  for number,name in enumerate(doc[key]):
   if number>255 or name in result:raise ValueError('invalid or duplicate map')
   result[name]=(group,number)
 return result

def compatible(world,expansion):
 a,b=ids(world),ids(expansion)
 return sorted((g<<8)|n for name,(g,n) in b.items() if a.get(name)==(g,n))

def source(values):
 if not values:raise ValueError('no compatible maps')
 data=','.join('0x%04x'%v for v in values)
 return '''#include "world/map_compat.h"\n#include <stddef.h>\nstatic const unsigned short sCompatibleMaps[] = {'''+data+'''};\nint EwMapSupported(unsigned group, unsigned map)\n{\n    unsigned key; size_t lo=0,hi=sizeof(sCompatibleMaps)/sizeof(sCompatibleMaps[0]);\n    if (group>255 || map>255) return 0;\n    key=(group<<8)|map;\n    while(lo<hi) { size_t mid=lo+(hi-lo)/2; if(sCompatibleMaps[mid]<key) lo=mid+1; else hi=mid; }\n    return lo<sizeof(sCompatibleMaps)/sizeof(sCompatibleMaps[0]) && sCompatibleMaps[lo]==key;\n}\n'''
