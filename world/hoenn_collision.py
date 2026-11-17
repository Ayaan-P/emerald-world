"""Conservative native-map facts and planning, never character execution/admission.

No generated-region identity is fabricated and no CHARACTER_WALK is emitted.
Current-view inputs must eventually come from a separately reviewed authenticated
native collision survey; this module deliberately has no live collector.
"""
import argparse,hashlib,json,re,struct
from collections import deque
from pathlib import Path

MAPS=('Route102','Route103','Route104','Route116','OldaleTown','PetalburgCity','RustboroCity')
# Only direction-independent ordinary walking surfaces. Unknown means blocked.
SAFE_BEHAVIORS=('MB_NORMAL','MB_TALL_GRASS','MB_SHORT_GRASS','MB_CAVE','MB_NO_RUNNING','MB_INDOOR_ENCOUNTER')

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def blob_hash(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def build(root,manifest):
 root=Path(root).resolve();files=manifest['files'];read={}
 if not re.fullmatch('[0-9a-f]{40}',manifest['commit']):raise ValueError('Exact native commit required')
 def source(path):
  p=(root/path).resolve()
  if not p.is_relative_to(root) or path not in files:raise ValueError('Unverified source dependency: '+path)
  data=p.read_bytes()
  if blob_hash(data)!=files[path]:raise ValueError('Source hash differs: '+path)
  read[path]=files[path];return data
 layouts={r['id']:r for r in json.loads(source('data/layouts/layouts.json'))['layouts']}
 groups=json.loads(source('data/maps/map_groups.json'))
 addresses={name:[group,num] for group,key in enumerate(groups['group_order']) for num,name in enumerate(groups[key])}
 arrays=dict(re.findall(r'const u16 (\w+)\[\] = INCBIN_U16\("([^"]+)"\);',source('src/data/tilesets/metatiles.h').decode()))
 headers=dict(re.findall(r'const struct Tileset (\w+)\s*=\s*\{(.*?)\};',source('src/data/tilesets/headers.h').decode(),re.S))
 behaviors={};index=0
 body=re.search(r'enum\s*\{(.*?)\};',source('include/constants/metatile_behaviors.h').decode(),re.S).group(1)
 body=re.sub(r'//[^\n]*|/\*.*?\*/','',body,flags=re.S)
 for token in body.split(','):
  token=token.strip()
  if not token or token=='NUM_METATILE_BEHAVIORS':continue
  parts=token.split('=')
  if len(parts)==2:index=int(parts[1].strip(),0)
  if not re.fullmatch('MB_[A-Z0-9_]+',parts[0].strip()):raise ValueError('Unsupported behavior enumeration')
  behaviors[parts[0].strip()]=index;index+=1
 masks=source('include/global.fieldmap.h').decode()
 for name,value in [('MAPGRID_METATILE_ID_MASK',0x3ff),('MAPGRID_COLLISION_MASK',0xc00),('MAPGRID_ELEVATION_MASK',0xf000),('METATILE_ATTR_BEHAVIOR_MASK',0xff)]:
  match=re.search(r'#define\s+'+name+r'\s+(0x[0-9a-fA-F]+)',masks)
  if not match or int(match[1],16)!=value:raise ValueError('Native map ABI changed')
 safe={behaviors[n] for n in SAFE_BEHAVIORS};maps={}
 def attributes(name):
  match=re.search(r'\.metatileAttributes\s*=\s*(\w+)\s*,',headers[name])
  data=source(arrays[match[1]])
  if len(data)%2 or len(data)>1024:raise ValueError('Unsupported tileset allocation')
  return struct.unpack('<'+'H'*(len(data)//2),data)
 for name in MAPS:
  spec=json.loads(source(f'data/maps/{name}/map.json'));layout=layouts[spec['layout']]
  if layout.get('layout_version','emerald')!='emerald':raise ValueError('Not Emerald metatile format')
  w,h=layout['width'],layout['height']
  if type(w) is not int or type(h) is not int or not 2<w<=256 or not 2<h<=256:raise ValueError('Unsupported dimensions')
  data=source(layout['blockdata_filepath'])
  if len(data)!=w*h*2:raise ValueError('Invalid map allocation')
  words=struct.unpack('<'+'H'*(w*h),data)
  primary,secondary=attributes(layout['primary_tileset']),attributes(layout['secondary_tileset'])
  # Retain every stock NPC's possible ordinary movement range regardless of
  # its private visibility flag. Live surveys additionally exclude scripted movers.
  reserved=set()
  for obj in spec.get('object_events',[]):
   x,y=obj['x'],obj['y'];rx=obj.get('movement_range_x',0);ry=obj.get('movement_range_y',0)
   if any(type(v) is not int or v<0 for v in (x,y,rx,ry)):raise ValueError('Unsupported native object range')
   reserved.update((a,b) for a in range(max(0,x-rx),min(w,x+rx+1)) for b in range(max(0,y-ry),min(h,y+ry+1)))
  triggers={(e['x'],e['y']) for key in ('warp_events','coord_events','bg_events') for e in spec.get(key,[])}
  reserved.update(triggers)
  scripts=source(f'data/maps/{name}/scripts.inc').decode()
  facts=[];candidates=[]
  for y in range(h):
   collision=[];elevation=[];behavior=[];candidate=[]
   for x in range(w):
    word=words[y*w+x];tile=word&0x3ff;attrs=primary if tile<512 else secondary;offset=tile if tile<512 else tile-512
    if offset>=len(attrs):raise ValueError('Unresolved metatile: '+name)
    c=(word>>10)&3;e=word>>12;b=attrs[offset]&255
    collision.append(str(c));elevation.append(format(e,'x'));behavior.append(format(b,'02x'))
    # Elevation 0 transitions / 15 multi-level / 1 Surf deliberately unsupported.
    candidate.append(format(e,'x') if not c and e in range(2,15) and b in safe and 0<x<w-1 and 0<y<h-1 and (x,y) not in reserved else '0')
   facts.append(dict(collision=''.join(collision),elevation=''.join(elevation),behavior=''.join(behavior)));candidates.append(''.join(candidate))
  row=dict(name=name,map=addresses[name],width=w,height=h,facts=facts,candidates=candidates,
   reserved=[list(p) for p in sorted(reserved)],triggers=[list(p) for p in sorted(triggers)],connections=spec.get('connections',[]),
   dynamic_script_indicators=sorted(set(re.findall(r'\b(?:setmetatile|setobjectxy|setobjectxyperm|applymovement|addobject|removeobject|setmaplayoutindex)\b',scripts))),
   requires_current_native_views=True)
  row['digest']=digest(row);maps[name]=row
 return dict(schema=1,native_commit=manifest['commit'],source_blobs=read,policy='conservative_same_map_same_elevation_no_execution',maps=maps)

def checked_map(catalog,name):
 if catalog.get('schema')!=1:raise ValueError('Unknown collision catalog')
 row=catalog['maps'][name]
 if row.get('digest')!=digest({k:v for k,v in row.items() if k!='digest'}):raise ValueError('Collision catalog changed')
 return row

def point(value,row):
 if type(value) not in (list,tuple) or len(value)!=2 or any(type(v) is not int for v in value):raise ValueError('Integer tile required')
 x,y=value
 if not 0<=x<row['width'] or not 0<=y<row['height']:raise ValueError('Outside map')
 return x,y

def static_cells(row,elevation):
 if type(elevation) is not int or elevation not in range(2,15):raise ValueError('Unsupported elevation')
 return {(x,y) for y,line in enumerate(row['candidates']) for x,v in enumerate(line) if v==format(elevation,'x')}

def search(row,start,target,allowed,max_steps):
 start,target=point(start,row),point(target,row)
 if type(max_steps) is not int or not 1<=max_steps<=64:raise ValueError('Bounded 1..64 step route required')
 if start not in allowed or target not in allowed:raise ValueError('Endpoint not conservatively traversable')
 queue=deque([start]);parents={start:None};depth={start:0}
 while queue:
  p=queue.popleft()
  if p==target:break
  if depth[p]==max_steps:continue
  x,y=p
  for q in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
   if q in allowed and q not in parents:parents[q]=p;depth[q]=depth[p]+1;queue.append(q)
 if target not in parents:raise ValueError('No safe bounded route')
 path=[];p=target
 while p is not None:path.append(list(p));p=parents[p]
 return path[::-1]

def preview(catalog,name,start,target,*,elevation=3,max_steps=64):
 """Offline static candidate only: NEVER admission or evidence of NPC movement."""
 row=checked_map(catalog,name)
 return dict(status='static_preview_not_executable',map=name,map_digest=row['digest'],path=search(row,start,target,static_cells(row,elevation),max_steps))

def current_cells(row,views,sessions,epoch,now,elevation):
 if type(sessions) not in (set,frozenset) or not sessions or len(sessions)>8 or any(type(s) is not str or not s for s in sessions):raise ValueError('Exact current authenticated observer sessions required')
 if type(views) is not list or len(views)!=len(sessions) or {v.get('session') for v in views}!=sessions:raise ValueError('Missing/duplicate/extra current view')
 if type(epoch) is not int or epoch<0 or type(now) not in (int,float):raise ValueError('Invalid authority context')
 allowed=static_cells(row,elevation);versions={}
 for view in views:
  if (view.get('map_digest')!=row['digest'] or view.get('map')!=row['map'] or view.get('elevation')!=elevation or view.get('movement')!='walk' or view.get('epoch')!=epoch or type(view.get('revision')) is not int or view['revision']<0
      or type(view.get('observed_at')) not in (float,int) or not 0<=now-view['observed_at']<=2
      or view.get('complete') is not True):raise ValueError('Stale, incomplete or wrong-map native view')
  if type(view.get('walkable')) is not list or type(view.get('blocked')) is not list:raise ValueError('Current native collision and occupancy required')
  cells={point(p,row) for p in view['walkable']};blocked={point(p,row) for p in view['blocked']}
  allowed.intersection_update(cells-blocked);versions[view['session']]=view['revision']
 return allowed,versions

def plan(catalog,name,start,target,*,views,sessions,epoch,now,elevation=3,max_steps=64):
 """Pure authority planning contract. Caller must authenticate/collect views.
 No production collector exists yet; this function does not create one.
 """
 row=checked_map(catalog,name);allowed,versions=current_cells(row,views,sessions,epoch,now,elevation)
 return dict(status='planned_not_executed',map=name,map_digest=row['digest'],epoch=epoch,versions=versions,elevation=elevation,
             path=search(row,start,target,allowed,max_steps))

def revalidate_step(catalog,proposal,index,*,views,sessions,epoch,now):
 row=checked_map(catalog,proposal['map'])
 if proposal.get('status')!='planned_not_executed' or proposal.get('map_digest')!=row['digest'] or proposal.get('epoch')!=epoch:raise ValueError('Plan context changed')
 allowed,versions=current_cells(row,views,sessions,epoch,now,proposal['elevation'])
 if versions!=proposal['versions']:raise ValueError('Native state changed; replan')
 path=proposal['path']
 if type(index) is not int or not 0<=index<len(path)-1:raise ValueError('Invalid next step')
 a,b=point(path[index],row),point(path[index+1],row)
 if a not in allowed or b not in allowed or abs(a[0]-b[0])+abs(a[1]-b[1])!=1:raise ValueError('Step no longer safe')
 return b

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 Path(a.output).write_text(json.dumps(build(a.root,json.loads(Path(a.manifest).read_text())),sort_keys=True,indent=2)+'\n')
