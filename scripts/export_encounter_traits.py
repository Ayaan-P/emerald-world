#!/usr/bin/env python3
"""Extract bounded encounter traits from preprocessed enabled native definitions.

Scalar arithmetic is evaluated by the host C compiler, not Python guesses.
The metadata checkout must be verified against the selected engine commit.
"""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path

def export(engine,catalogue,output,commit):
 engine=Path(engine);enabled=json.loads(Path(catalogue).read_text())['species'];rows=[];sources={}
 constants=engine/'include/constants/species.h'
 enums=dict(re.findall(r'^\s*(SPECIES_[A-Z0-9_]+)\s*=\s*([^,]+),?\s*$',constants.read_text(),re.M))
 def species_value(name,trail=()):
  if name in trail or name not in enums:raise ValueError('Unresolved native species identity')
  value=enums[name].strip()
  return int(value) if value.isdigit() else species_value(value,trail+(name,))
 sources['include/constants/species.h']=hashlib.sha256(constants.read_bytes()).hexdigest()
 dexfile=engine/'include/constants/pokedex.h'
 dexbody=re.search(r'enum NationalDexOrder\s*\{(.*?)\};',dexfile.read_text(),re.S)[1]
 dexnames=re.findall(r'^\s*NATIONAL_DEX_([A-Z0-9_]+)\s*,',dexbody,re.M)
 dex={name:i for i,name in enumerate(dexnames)}
 sources['include/constants/pokedex.h']=hashlib.sha256(dexfile.read_bytes()).hexdigest()
 boundaries=[dex[name] for name in ('MEW','CELEBI','DEOXYS','ARCEUS','GENESECT','VOLCANION','MELMETAL','ENAMORUS','PECHARUNT')]
 for path in sorted((engine/'src/data/pokemon/species_info').glob('gen_*_families.h')):
  command=['gcc','-E','-P','-x','c','-I',str(engine/'include'),'-DTRUE=1','-DFALSE=0','-include','config/species_enabled.h','-include','config/pokemon.h','-include','constants/global.h',str(path)]
  text=subprocess.run(command,check=True,capture_output=True,text=True).stdout
  # Preprocessor dependency list captures the configuration used for all entries.
  deps=subprocess.run(command[:1]+['-MM']+command[3:],check=True,capture_output=True,text=True).stdout
  for name in deps.replace('\\\n',' ').split(':',1)[1].split():
   f=Path(name);sources[str(f.relative_to(engine))]=hashlib.sha256(f.read_bytes()).hexdigest()
  entries=list(re.finditer(r'^\s*\[SPECIES_([A-Z0-9_]+)\]\s*=',text,re.M))
  for i,match in enumerate(entries):
   name=match[1];body=text[match.end():entries[i+1].start() if i+1<len(entries) else len(text)]
   if name not in enabled or not re.search(r'\.natDexNum\s*=\s*NATIONAL_DEX_'+re.escape(name)+r'\s*,',body):continue
   types=re.search(r'\.types\s*=\s*MON_TYPES\((TYPE_[A-Z]+)(?:,\s*(TYPE_[A-Z]+))?\)',body)
   fields=[re.search(r'\.'+key+r'\s*=\s*([^,\n]+)',body) for key in ('baseHP','baseAttack','baseDefense','baseSpAttack','baseSpDefense','baseSpeed','catchRate')]
   if not types or not all(fields):continue
   expressions=[f[1] for f in fields]
   # Only preprocessed numeric scalar expressions; fail closed on native macros.
   if any(not re.fullmatch(r'[0-9 ()?:<>=!+*/%&|~-]+',e) for e in expressions):continue
   special=bool(re.search(r'\.(?:isRestrictedLegendary|isSubLegendary|isMythical|isUltraBeast|isParadox)\s*=\s*1\s*,',body))
   if species_value('SPECIES_'+name)!=enabled[name]:raise ValueError('Enabled catalogue disagrees with native species identity')
   generation=next(i+1 for i,end in enumerate(boundaries) if dex[name]<=end)
   rows.append(dict(name=name,species=enabled[name],national_dex=dex[name],generation=generation,types=list(dict.fromkeys(t[5:].lower() for t in types.groups() if t)),special=special,expressions=expressions))
 with tempfile.TemporaryDirectory() as tmp:
  source='#include <stdio.h>\nint main(void){\n'+''.join('printf("'+str(i)+' %d %d %d %d %d %d %d\\n",'+','.join('('+e+')' for e in r['expressions'])+');\n' for i,r in enumerate(rows))+'return 0;}\n'
  c=Path(tmp)/'traits.c';binary=Path(tmp)/'traits';c.write_text(source)
  subprocess.run(['gcc',str(c),'-o',str(binary)],check=True)
  for line in subprocess.check_output([str(binary)],text=True).splitlines():
   i,*values=map(int,line.split());rows[i].pop('expressions');rows[i].update(bst=sum(values[:6]),catch_rate=values[6])
 data=dict(engine_commit=commit,source='compiler-preprocessed native species definitions; numeric expressions evaluated by C',sources=sources,species=rows)
 Path(output).write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n');return data
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('engine');p.add_argument('catalogue');p.add_argument('output');p.add_argument('--commit',required=True);a=p.parse_args();d=export(a.engine,a.catalogue,a.output,a.commit);print(len(d['species']))
