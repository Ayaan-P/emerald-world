"""Conservative source-derived visitor sites, not a native navigation mesh."""
import hashlib,itertools,json,re,struct
from pathlib import Path

PATH=Path(__file__).with_name('native_resident_sites.json')

def connected(floor):
 if not floor:return False
 reached={next(iter(floor))};todo=list(reached)
 for x,y in todo:
  for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
   if p in floor and p not in reached:reached.add(p);todo.append(p)
 return len(reached)==len(floor)

def build(root,engine,candidates=None):
 root=Path(root);inputs={}
 def read(path):
  value=(root/path).read_bytes();inputs[path]=hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest();return value
 field=read('include/global.fieldmap.h').decode()
 if not all(token in field for token in ('MAPGRID_COLLISION_MASK   0x0C00','MAPGRID_ELEVATION_MASK   0xF000','METATILE_ATTR_BEHAVIOR_MASK 0x00FF')):raise ValueError('Unreviewed native block encoding')
 behavior=read('include/constants/metatile_behaviors.h').decode()
 if not re.search(r'enum\s*\{\s*MB_NORMAL\s*,',behavior):raise ValueError('Unreviewed normal floor behavior')
 headers=read('src/data/tilesets/headers.h').decode();arrays=read('src/data/tilesets/metatiles.h').decode()
 attrs=dict(re.findall(r'const u16 (gMetatileAttributes_\w+)\[\] = INCBIN_U16\("([^"]+)"\);',arrays))
 tiles={name:re.search(r'\.metatileAttributes\s*=\s*(\w+)',body).group(1) for name,body in re.findall(r'const struct Tileset (\w+)\s*=\s*\{(.*?)\};',headers,re.S)}
 layouts={x['id']:x for x in json.loads(read('data/layouts/layouts.json'))['layouts']}
 groups=json.loads(read('data/maps/map_groups.json'));indices={name:(g,n) for g,label in enumerate(groups['group_order']) for n,name in enumerate(groups[label])}
 sites={}
 for name,(g,n) in indices.items():
  if candidates is not None and name not in candidates:continue
  # Ordinary residence interiors only, not facilities, unused or prototype content.
  if not re.fullmatch(r'[A-Za-z]+(?:City|Town)_(?:House\d*|Flat\d+_\d+F)',name):continue
  base='data/maps/'+name+'/';m=json.loads((root/(base+'map.json')).read_bytes());script=(root/(base+'scripts.inc')).read_text()
  if m.get('region')!='REGION_HOENN' or m.get('map_type')!='MAP_TYPE_INDOOR' or m.get('coord_events') or m.get('bg_events') or m.get('connections'):continue
  if not re.match(re.escape(name)+r'_MapScripts::\s*\.byte 0\s',script):continue
  ops=[line.strip().split()[0] for line in script.splitlines() if line.strip() and not line.strip().startswith(('.', '@', '//')) and not line.strip().endswith(':')]
  if set(ops)-{'msgbox','end','lock','faceplayer','release','waitmessage','waitbuttonpress'}:continue
  if any(o.get('movement_type') not in ('MOVEMENT_TYPE_NONE','MOVEMENT_TYPE_FACE_DOWN','MOVEMENT_TYPE_FACE_UP','MOVEMENT_TYPE_FACE_LEFT','MOVEMENT_TYPE_FACE_RIGHT','MOVEMENT_TYPE_WANDER_AROUND','MOVEMENT_TYPE_WANDER_UP_AND_DOWN','MOVEMENT_TYPE_WANDER_LEFT_AND_RIGHT') for o in m['object_events']):continue
  layout=layouts[m['layout']]
  if layout.get('layout_version','emerald')!='emerald':continue
  width,height=layout['width'],layout['height'];raw=(root/layout['blockdata_filepath']).read_bytes()
  if len(raw)!=width*height*2:raise ValueError('Invalid block allocation')
  banks=[]
  for key in ('primary_tileset','secondary_tileset'):
   path=attrs[tiles[layout[key]]];values=read(path);banks.append(struct.unpack('<'+'H'*(len(values)//2),values))
  blocks=struct.unpack('<'+'H'*(width*height),raw);floor=set()
  for i,block in enumerate(blocks):
   tile=block&1023;bank=0 if tile<512 else 1;index=tile%512
   if not block&0xc00 and block>>12==3 and index<len(banks[bank]) and banks[bank][index]&255==0:floor.add((i%width,i//width))
  if not connected(floor):continue
  protected=set();positions=[];combinations=1
  for o in m['object_events']:
   rx=o.get('movement_range_x',0);ry=o.get('movement_range_y',0)
   if type(rx) is not int or type(ry) is not int or not 0<=rx<=15 or not 0<=ry<=15:raise ValueError('Unknown movement extent')
   possible={(x,y) for x in range(o['x']-rx,o['x']+rx+1) for y in range(o['y']-ry,o['y']+ry+1)} & floor
   positions.append(possible or {(o['x'],o['y'])});combinations*=len(positions[-1])
   protected.update((x,y) for x in range(o['x']-rx-2,o['x']+rx+3) for y in range(o['y']-ry-2,o['y']+ry+3))
  if combinations>4096:continue
  for w in m['warp_events']:
   protected.update((x,y) for x in range(w['x']-2,w['x']+3) for y in range(w['y']-2,w['y']+3))
  available=[p for p in sorted(floor) if 1<=p[0]<width-1 and 1<=p[1]<height-1 and p not in protected and connected(floor-{p}) and sum(q in floor for q in ((p[0]-1,p[1]),(p[0]+1,p[1]),(p[0],p[1]-1),(p[0],p[1]+1)))>=3]
  # Preserve each existing connected component for every conservative stock
  # wander placement, rather than assuming original NPCs never obstruct ground.
  def preserves(point,occupied):
   ground=floor-set(occupied);remaining=ground-{point}
   neighbors=[p for p in ((point[0]-1,point[1]),(point[0]+1,point[1]),(point[0],point[1]-1),(point[0],point[1]+1)) if p in remaining]
   if not neighbors:return False
   reached={neighbors[0]};todo=list(reached)
   for x,y in todo:
    for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
     if p in remaining and p not in reached:reached.add(p);todo.append(p)
   return all(p in reached for p in neighbors)
  available=[p for p in available if all(preserves(p,occupied) for occupied in itertools.product(*positions))]
  if not available:continue
  read(base+'map.json');read(base+'scripts.inc');read(layout['blockdata_filepath'])
  sites[name]=dict(group=g,num=n,sites=[list(p) for p in available],width=width,height=height)
 return dict(version=1,engine_commit=engine,inputs=inputs,maps=sites)

def catalog():
 from scripts.build_expansion import PIN
 value=json.loads(PATH.read_text())
 if value.get('version')!=1 or value.get('engine_commit')!=PIN:raise ValueError('Resident sites require the exact reviewed native asset pin')
 from .build_catalog import catalog_maps
 for name,row in value['maps'].items():
  if catalog_maps().get((row['group'],row['num']),{}).get('name')!=name:raise ValueError('Resident map catalog differs from native source')
 return value['maps']

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('engine');parser.add_argument('output');args=parser.parse_args()
 Path(args.output).write_text(json.dumps(build(args.root,args.engine),sort_keys=True,indent=2)+'\n')
