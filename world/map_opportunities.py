"""Read-only projection of actual public configuration, never sightings or rewards."""
import json,re,time
from .build_catalog import catalog_maps
TOWNS=('LittlerootTown','OldaleTown','DewfordTown','LavaridgeTown','FallarborTown','VerdanturfTown','PacifidlogTown','PetalburgCity','SlateportCity','MauvilleCity','RustboroCity','FortreeCity','LilycoveCity','MossdeepCity','SootopolisCity','EverGrandeCity')
PLACES=set(TOWNS)|{'Route'+str(n) for n in range(101,135)}
def short(text):return re.sub('[^A-Za-z0-9 .!?-]',' ',str(text))[:16]
def rows(db,table,sql,args):
 if not db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table',table)).fetchone():return []
 return db.execute(sql,args).fetchall()
def pages(server,name,features):
 now=time.time();out=[['World settings','Not sightings','Local rules apply','Travel is yours']];expiry=now+5
 land=rows(server.db,'shared_outbreaks','SELECT species,level,chance,expires FROM shared_outbreaks WHERE map=? AND expires>?',(name,now))
 if features&1:
  for species,level,chance,until in land:
   out.append(['Land encounter',short(species),f'Lv {level} {chance} pct','Saved rules win']);expiry=min(expiry,until)
 fish=rows(server.db,'shared_fishing','SELECT population,expires FROM shared_fishing WHERE map=? AND expires>?',(name,now))
 if features&2:
  weights={'old':[70,30],'good':[60,20,20],'super':[40,40,15,4,1]}
  for population,until in fish:
   data=json.loads(population);expiry=min(expiry,until)
   for rod in weights:
    for i,(species,lo,hi) in enumerate(data[rod]):
     out.append([f'{rod.title()} rod {i+1}',short(species),f'Lv {lo}-{hi} {weights[rod][i]} pct','Native rules win'])
 if features&4:
  from .actor_shops import ITEMS
  shelves=rows(server.db,'hoenn_market_shelves','SELECT items,expires FROM hoenn_market_shelves WHERE site=? AND expires>?',(name+'_Mart',now))
  for items,until in shelves:
   expiry=min(expiry,until)
   for item in json.loads(items):out.append(['Visiting stock',short(ITEMS[item]),'Buy at town mart','Normal price'])
 if len(out)==1:out.append(['No active offers','for this client','Original play','still available'])
 return out,max(0,min(5,int(expiry-now)))
def wire(server,conn,raw):
 try:
  fields=raw.decode('ascii').split();nonce=fields[4] if len(fields)==6 else '0'
  if (len(fields)!=6 or fields[:2]!=['WM','GET'] or fields[2] not in PLACES
      or not all(re.fullmatch('[0-9]{1,10}',s) for s in fields[3:])
      or not 0<=int(fields[3])<32 or not 1<=int(nonce)<=2147483647 or not 0<=int(fields[5])<=7):raise ValueError('request')
  peer=conn['presence']
  if not peer.get('state') or time.monotonic()-peer.get('state_time',0)>5:raise ValueError('stale')
  if fields[2] not in {m['name'] for m in catalog_maps().values()}:raise ValueError('map')
  features=int(fields[5]) & ((1 if peer.get('outbreak_capable') else 0)|(2 if peer.get('fishing_capable') else 0)|4)
  listing,ttl=pages(server,fields[2],features);page=int(fields[3])%len(listing)
  text='|'.join(short(s) for s in listing[page])
  return f'WM PAGE {nonce} {page} {len(listing)} {ttl} {text.encode().hex()}\n'
 except (ValueError,KeyError,IndexError,UnicodeError,TypeError):return 'WM NONE '+(nonce if 'nonce' in locals() and re.fullmatch('[0-9]{1,10}',nonce) else '0')+'\n'
