"""Extract only unambiguous literal native move traits; never evaluate C config."""
import hashlib,json,re,sys
from pathlib import Path

def extract(constants,info,names):
    symbols={};value=-1
    body=constants.split('enum __attribute__((packed)) Move',1)[1].split('{',1)[1].split('};',1)[0]
    for part in re.sub(r'//[^\n]*','',body).split(','):
        part=part.strip()
        if not part:continue
        match=re.fullmatch(r'(\w+)(?:\s*=\s*(\w+))?',part)
        if not match:raise ValueError('Unsupported move enum expression')
        key,assigned=match.groups();value=(int(assigned) if assigned.isdigit() else symbols[assigned]) if assigned else value+1;symbols[key]=value
    found={};excluded=[]
    blocks=list(re.finditer(r'^    \[(MOVE_\w+)\] =',info,re.M))
    for i,b in enumerate(blocks):
        identity=str(symbols[b[1]])
        if identity not in names:continue
        block=info[b.end():blocks[i+1].start() if i+1<len(blocks) else len(info)]
        types=re.findall(r'\.type\s*=\s*([^,\n]+)',block);categories=re.findall(r'\.category\s*=\s*([^,\n]+)',block)
        if len(types)!=1 or len(categories)!=1 or not re.fullmatch('TYPE_[A-Z]+',types[0]) or not re.fullmatch('DAMAGE_CATEGORY_(PHYSICAL|SPECIAL|STATUS)',categories[0]):
            excluded.append(identity);continue
        found[identity]=dict(type=types[0][5:].lower(),category=categories[0][16:].lower())
    return found,sorted(excluded,key=int)

def blob(text):return hashlib.sha1(b'blob '+str(len(text.encode())).encode()+b'\0'+text.encode()).hexdigest()
if __name__=='__main__':
    root=Path(sys.argv[1]);constants=(root/'include/constants/moves.h').read_text();info=(root/'src/data/moves_info.h').read_text()
    names=json.loads(Path(sys.argv[2]).read_text())['names'];traits,excluded=extract(constants,info,names)
    print(json.dumps(dict(native='c727376a85d9a5dedc5207e435d66417d46a01f5',sources={'include/constants/moves.h':blob(constants),'src/data/moves_info.h':blob(info)},traits=traits,excluded=excluded),sort_keys=True,separators=(',',':')))
