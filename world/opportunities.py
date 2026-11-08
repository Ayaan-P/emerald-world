"""State-driven shared-place stories with private participant history.

These effects change narrative state, never native money, creatures or map bytes.
Authored packs are immutable. The authority, not a model or player, evaluates
requirements and commits a choice and its resulting opportunities together.
"""
import hashlib
import json
import re


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def identity(value):
    if type(value) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,15}',value):raise ValueError('Use a short lowercase story identifier.')
    return value

def text(value,limit=110):
    if type(value) is not str or not 1<=len(value)<=limit or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError('Story text must be bounded plain ASCII.')


def validate(pack,places):
    if type(pack) is not dict or set(pack)!={'id','title','qualities','scenes'} or len(encoded(pack))>16384:raise ValueError('Invalid story pack.')
    identity(pack['id']);text(pack['title'],60)
    qualities=pack['qualities'];scenes=pack['scenes']
    if type(qualities) is not dict or not 1<=len(qualities)<=32:raise ValueError('A story needs 1..32 qualities.')
    for key,q in qualities.items():
        identity(key)
        if (type(q) is not dict or set(q)!={'scope','initial','max'} or q['scope'] not in ('place','player')
                or type(q['max']) is not int or not 1<=q['max']<=1000 or type(q['initial']) is not int or not 0<=q['initial']<=q['max']):raise ValueError('Invalid quality bounds.')
    if type(scenes) is not dict or not 1<=len(scenes)<=32:raise ValueError('A story needs 1..32 scenes.')
    def requirements(req):
        if type(req) is not dict or len(req)>32:raise ValueError('Invalid story requirements.')
        for key,bounds in req.items():
            if key not in qualities or type(bounds) is not list or len(bounds)!=2 or any(type(n) is not int for n in bounds) or not 0<=bounds[0]<=bounds[1]<=qualities[key]['max']:raise ValueError('Invalid quality requirement.')
    for key,scene in scenes.items():
        identity(key)
        if type(scene) is not dict or set(scene)!={'place','text','requires','once','choices'}:raise ValueError('Invalid scene.')
        if scene['place'] not in places or scene['once'] not in ('player','world'):raise ValueError('Invalid scene place or repetition rule.')
        text(scene['text']);requirements(scene['requires'])
        choices=scene['choices']
        if type(choices) is not dict or not 1<=len(choices)<=3:raise ValueError('Scenes need 1..3 choices.')
        for choice,action in choices.items():
            identity(choice)
            if type(action) is not dict or set(action)!={'text','requires','effects','result'}:raise ValueError('Invalid story choice.')
            text(action['text'],55);text(action['result']);requirements(action['requires'])
            effects=action['effects']
            if type(effects) is not dict or not 1<=len(effects)<=16:raise ValueError('Choices need bounded consequences.')
            for quality,delta in effects.items():
                if quality not in qualities or type(delta) is not int or not -1000<=delta<=1000 or not delta:raise ValueError('Invalid story consequence.')
    return pack


class Opportunities:
    def __init__(self,db,places):
        self.db=db;self.places=set(places)
        db.executescript('''
        CREATE TABLE IF NOT EXISTS story_packs(id TEXT PRIMARY KEY,document TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS story_places(pack TEXT,place TEXT,revision INTEGER,state TEXT,played TEXT,PRIMARY KEY(pack,place));
        CREATE TABLE IF NOT EXISTS story_players(pack TEXT,trainer TEXT,state TEXT,played TEXT,PRIMARY KEY(pack,trainer));
        CREATE TABLE IF NOT EXISTS story_receipts(pack TEXT,trainer TEXT,request TEXT,payload TEXT,result TEXT,PRIMARY KEY(pack,trainer,request));
        CREATE TABLE IF NOT EXISTS story_consequences(pack TEXT,place TEXT,revision INTEGER,scene TEXT,choice TEXT,changes TEXT,PRIMARY KEY(pack,place,revision));
        ''')
        db.commit()

    def publish(self,pack):
        validate(pack,self.places);document=encoded(pack)
        with self.db:
            old=self.db.execute('SELECT document FROM story_packs WHERE id=?',(pack['id'],)).fetchone()
            if old and old[0]!=document:raise ValueError('Story identity already names different content.')
            if not old:
                if self.db.execute('SELECT count(*) FROM story_packs').fetchone()[0]>=64:raise ValueError('World story capacity reached.')
                self.db.execute('INSERT INTO story_packs VALUES(?,?)',(pack['id'],document))
        return dict(ok=True,id=pack['id'],digest=hashlib.sha256(document.encode()).hexdigest())

    def _load(self,pack_id,trainer,place):
        row=self.db.execute('SELECT document FROM story_packs WHERE id=?',(pack_id,)).fetchone()
        if not row:raise ValueError('Unknown story.')
        pack=json.loads(row[0]);q=pack['qualities']
        shared={k:v['initial'] for k,v in q.items() if v['scope']=='place'}
        private={k:v['initial'] for k,v in q.items() if v['scope']=='player'}
        row=self.db.execute('SELECT revision,state,played FROM story_places WHERE pack=? AND place=?',(pack_id,place)).fetchone()
        revision=0;world_played=[];player_played=[]
        if row:revision,raw,played=row;shared=json.loads(raw);world_played=json.loads(played)
        row=self.db.execute('SELECT state,played FROM story_players WHERE pack=? AND trainer=?',(pack_id,trainer)).fetchone()
        if row:private=json.loads(row[0]);player_played=json.loads(row[1])
        return pack,revision,shared,private,world_played,player_played

    @staticmethod
    def _matches(requirements,values):return all(low<=values[key]<=high for key,(low,high) in requirements.items())

    def _eligible(self,pack,place,shared,private,world_played,player_played):
        values=dict(shared,**private);result=[]
        for key,scene in pack['scenes'].items():
            played=world_played if scene['once']=='world' else player_played
            if scene['place']!=place or key in played or not self._matches(scene['requires'],values):continue
            choices=[]
            for cid,action in scene['choices'].items():
                if self._matches(action['requires'],values) and all(0<=values[k]+delta<=pack['qualities'][k]['max'] for k,delta in action['effects'].items()):
                    choices.append(dict(id=cid,text=action['text']))
            if choices:result.append(dict(id=key,text=scene['text'],choices=choices))
        return result

    def offers(self,trainer,place,pack_id=None):
        identities=[pack_id] if pack_id else [row[0] for row in self.db.execute('SELECT id FROM story_packs ORDER BY id')]
        results=[]
        for key in identities:
            pack,revision,shared,private,wp,pp=self._load(key,trainer,place)
            scenes=self._eligible(pack,place,shared,private,wp,pp)
            if scenes:results.append(dict(id=key,title=pack['title'],revision=revision,scenes=scenes))
        return results

    def choose(self,trainer,place,pack_id,scene_id,choice_id,revision,request):
        identity(request)
        if type(revision) is not int or revision<0:raise ValueError('Invalid story revision.')
        payload=encoded(dict(place=place,scene=scene_id,choice=choice_id,revision=revision))
        with self.db:
            old=self.db.execute('SELECT payload,result FROM story_receipts WHERE pack=? AND trainer=? AND request=?',(pack_id,trainer,request)).fetchone()
            if old:
                if old[0]!=payload:raise ValueError('Choice receipt already names a different request.')
                return json.loads(old[1])
            pack,current,shared,private,wp,pp=self._load(pack_id,trainer,place)
            if current!=revision:raise ValueError('This place changed. Read /story again before choosing.')
            offers=self._eligible(pack,place,shared,private,wp,pp)
            if not any(s['id']==scene_id and any(c['id']==choice_id for c in s['choices']) for s in offers):raise ValueError('That choice is no longer available here.')
            scene=pack['scenes'][scene_id];action=scene['choices'][choice_id];public={}
            for key,delta in action['effects'].items():
                target=shared if pack['qualities'][key]['scope']=='place' else private
                target[key]+=delta
                if target is shared:public[key]=delta
            (wp if scene['once']=='world' else pp).append(scene_id)
            self.db.execute('INSERT OR REPLACE INTO story_places VALUES(?,?,?,?,?)',(pack_id,place,current+1,encoded(shared),encoded(wp)))
            self.db.execute('INSERT OR REPLACE INTO story_players VALUES(?,?,?,?)',(pack_id,trainer,encoded(private),encoded(pp)))
            self.db.execute('INSERT INTO story_consequences VALUES(?,?,?,?,?,?)',(pack_id,place,current+1,scene_id,choice_id,encoded(public)))
            result=dict(ok=True,revision=current+1,text=action['result'])
            self.db.execute('INSERT INTO story_receipts VALUES(?,?,?,?,?)',(pack_id,trainer,request,payload,encoded(result)))
            return result
