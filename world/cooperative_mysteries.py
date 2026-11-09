"""Two-role field puzzles. Private clues require fresh station occupancy.

This coordinates existing native walking/chat, not new map geometry or rewards.
Locations remain client reports under the existing world's trust model.
"""
import json
import re
import secrets
import sqlite3
import time


def dump(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def label(value,limit=110):
    if type(value) is not str or not 1<=len(value)<=limit or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError('Use bounded plain ASCII puzzle text.')


def validate(pack,coords):
    if type(pack) is not dict or set(pack)!={'id','title','roles','stages','ending'} or len(dump(pack))>16384:raise ValueError('Invalid mystery pack.')
    if type(pack['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,15}',pack['id']):raise ValueError('Invalid mystery identifier.')
    label(pack['title'],60);label(pack['ending'])
    if type(pack['roles']) is not list or len(pack['roles'])!=2:raise ValueError('Mysteries need exactly two distinct roles.')
    for role in pack['roles']:label(role,24)
    if pack['roles'][0]==pack['roles'][1]:raise ValueError('Roles must differ.')
    if type(pack['stages']) is not list or not 1<=len(pack['stages'])<=12:raise ValueError('Mysteries need 1..12 stages.')
    for stage in pack['stages']:
        if type(stage) is not dict or set(stage)!={'title','stations','answer','result'}:raise ValueError('Invalid mystery stage.')
        label(stage['title'],60);label(stage['result'])
        if type(stage['answer']) is not str or not re.fullmatch('[A-Z0-9]{2,16}',stage['answer']):raise ValueError('Answers must be 2..16 uppercase letters or digits.')
        stations=stage['stations']
        if type(stations) is not list or len(stations)!=2:raise ValueError('Each stage needs two stations.')
        for station in stations:
            if type(station) is not dict or set(station)!={'at','clue'}:raise ValueError('Invalid station.')
            at=station['at']
            if type(at) is not list or len(at)!=4 or any(type(n) is not int for n in at):raise ValueError('Invalid station position.')
            coords(*at);label(station['clue'])
        if stations[0]['at']==stations[1]['at']:raise ValueError('Partners need different stations.')
    return pack


class Mysteries:
    def __init__(self,server,coords,freshness):
        self.s=server;self.db=server.db;self.coords=coords;self.freshness=freshness
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS mystery_packs(id TEXT PRIMARY KEY,document TEXT);
        CREATE TABLE IF NOT EXISTS mystery_runs(id TEXT PRIMARY KEY,pack TEXT,stage INTEGER,status TEXT);
        CREATE TABLE IF NOT EXISTS mystery_members(run TEXT,role INTEGER,trainer TEXT,PRIMARY KEY(run,role),UNIQUE(run,trainer));
        CREATE TABLE IF NOT EXISTS mystery_clues(run TEXT,stage INTEGER,role INTEGER,PRIMARY KEY(run,stage,role));
        CREATE TABLE IF NOT EXISTS mystery_solved(run TEXT,stage INTEGER,PRIMARY KEY(run,stage));
        ''');self.db.commit()

    def publish(self,pack):
        validate(pack,self.coords)
        for stage in pack['stages']:
            if any(tuple(s['at'][:2]) in (self.s.cave_map,self.s.wilds_map) for s in stage['stations']):raise ValueError('Mysteries require stable standard maps.')
        document=dump(pack)
        with self.db:
            old=self.db.execute('SELECT document FROM mystery_packs WHERE id=?',(pack['id'],)).fetchone()
            if old and old[0]!=document:raise ValueError('Mystery identity already names different content.')
            if not old:
                if self.db.execute('SELECT count(*) FROM mystery_packs').fetchone()[0]>=64:raise ValueError('Mystery capacity reached.')
                self.db.execute('INSERT INTO mystery_packs VALUES(?,?)',(pack['id'],document))
        return dict(ok=True,id=pack['id'])

    def _current(self,trainer,active=True):
        return self.db.execute('''SELECT r.id,r.pack,r.stage,r.status,m.role FROM mystery_runs r
          JOIN mystery_members m ON m.run=r.id WHERE m.trainer=? '''+
          ("AND r.status IN ('waiting','active') " if active else '')+'ORDER BY r.rowid DESC LIMIT 1',(trainer,)).fetchone()

    def _pack(self,key):
        row=self.db.execute('SELECT document FROM mystery_packs WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Unknown mystery.')
        return json.loads(row[0])

    def _at(self,trainer,position):
        peer=self.s.peers.get(trainer)
        if not peer or peer.get('closing'):return False
        state=peer.get('state');updated=peer.get('state_time')
        return bool(state and state[6] and state[:4]==position and updated is not None and 0<=time.monotonic()-updated<=self.freshness)

    def completed(self,trainer,pack):
        return self.db.execute("SELECT 1 FROM mystery_runs r JOIN mystery_members m ON m.run=r.id WHERE r.pack=? AND m.trainer=? AND r.status='completed' LIMIT 1",(pack,trainer)).fetchone() is not None

    def status(self,trainer):
        run=self._current(trainer) or self._current(trainer,False)
        if not run:return ['Use /mystery list, /mystery start PACK, or /mystery join CODE.']
        rid,key,index,state,role=run;pack=self._pack(key)
        if state=='completed':return [pack['ending'],'Mystery completed. Read /story here for unlocked opportunities.']
        if state=='cancelled':return ['This mystery was ended by a participant.']
        lines=[pack['title']+' - '+pack['roles'][role]]
        if state=='waiting':lines+=['Share this invitation with one partner: /mystery join '+rid]
        station=pack['stages'][index]['stations'][role];at=station['at'];place=self.coords(*at)['name']
        lines += [f"Stage {index+1}: {pack['stages'][index]['title']}",f'Your station: {place} ({at[2]},{at[3]}).',
                  'At your station, use /mystery clue. Both partners must be present to solve.']
        if role==1:lines.append(f'/mystery solve {index+1} ANSWER')
        return lines

    def command(self,trainer,words):
        if len(words)==2 and words[0] in ('start','join') and getattr(self.s,'races',None) and self.s.races.current(trainer):raise ValueError('Leave your current race first.')
        if not words or words==['status']:return self.status(trainer)
        with self.db:
            if words==['list']:
                return [key+': '+self._pack(key)['title'] for key, in self.db.execute('SELECT id FROM mystery_packs ORDER BY id LIMIT 12')] or ['No mysteries have been published.']
            if len(words)==2 and words[0]=='start':
                self._pack(words[1]);old=self._current(trainer)
                if old:
                    if old[1]!=words[1]:raise ValueError('Finish or /mystery leave your current expedition first.')
                else:
                    rid=secrets.token_hex(8)
                    self.db.execute('INSERT INTO mystery_runs VALUES(?,?,0,?)',(rid,words[1],'waiting'))
                    self.db.execute('INSERT INTO mystery_members VALUES(?,0,?)',(rid,trainer))
                return self.status(trainer)
            if len(words)==2 and words[0]=='join':
                old=self._current(trainer)
                if old:
                    if old[0]!=words[1]:raise ValueError('You already have an unfinished mystery.')
                    return self.status(trainer)
                row=self.db.execute('SELECT status FROM mystery_runs WHERE id=?',(words[1],)).fetchone()
                if not row or row[0]!='waiting':raise ValueError('That invitation is unavailable.')
                self.db.execute('INSERT INTO mystery_members VALUES(?,1,?)',(words[1],trainer))
                self.db.execute("UPDATE mystery_runs SET status='active' WHERE id=?",(words[1],))
                return self.status(trainer)
            run=self._current(trainer)
            if not run:raise ValueError('Join or start a mystery first.')
            rid,key,index,state,role=run;pack=self._pack(key);stage=pack['stages'][index]
            if words==['leave']:
                self.db.execute("UPDATE mystery_runs SET status='cancelled' WHERE id=?",(rid,))
                return ['Mystery ended for both participants. No saves or inventory changed.']
            if words==['clue']:
                if state!='active':raise ValueError('Wait for your partner to join before reading clues.')
                if not self._at(trainer,stage['stations'][role]['at']):raise ValueError('Stand ready at your current station to read its clue.')
                self.db.execute('INSERT OR IGNORE INTO mystery_clues VALUES(?,?,?)',(rid,index,role))
                return [stage['stations'][role]['clue'],'Tell your partner what you discovered.']
            if len(words)==3 and words[0]=='solve':
                if role!=1:raise ValueError('Your partner is the solver. Share your clue with them.')
                if not words[1].isascii() or not words[1].isdecimal() or int(words[1])!=index+1:raise ValueError('That is not the current stage. Use /mystery status.')
                members=self.db.execute('SELECT role,trainer FROM mystery_members WHERE run=? ORDER BY role',(rid,)).fetchall()
                if state!='active' or len(members)!=2 or not all(self._at(t,stage['stations'][r]['at']) for r,t in members):raise ValueError('Both partners must stand ready at their current stations.')
                if self.db.execute('SELECT count(*) FROM mystery_clues WHERE run=? AND stage=?',(rid,index)).fetchone()[0]!=2:raise ValueError('Both partners must read their current clue first.')
                if words[2]!=stage['answer']:return ['That answer does not fit. Compare your two clues again.']
                self.db.execute('INSERT INTO mystery_solved VALUES(?,?)',(rid,index))
                finished=index+1==len(pack['stages'])
                self.db.execute('UPDATE mystery_runs SET stage=?,status=? WHERE id=?',(index+1,'completed' if finished else 'active',rid))
                return [stage['result']]+self.status(trainer)
            raise ValueError('Use /mystery list, status, clue, leave, or the displayed solve line.')

    def handle(self,conn,message):
        words=message.split()
        if not words or words[0]!='/mystery':return False
        try:
            with self.s.lock:lines=self.command(conn['id'],words[1:])
        except (ValueError,TypeError,sqlite3.Error) as exc:
            lines=[str(exc) if isinstance(exc,ValueError) else 'Mystery transaction failed; check /mystery status.']
        for line in lines[:12]:self.s.guild_chat.message(conn,conn['id'],line[:120])
        conn['chat_status']='sent';self.s._queue(conn,self.s._snapshot(conn));return True
