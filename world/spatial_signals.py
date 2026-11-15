"""Short-lived visible co-op intent, never map objects, rewards or verified danger."""
import json,time
from pathlib import Path
KINDS=('look','meet','help','danger')
MAPS={(r['group'],r['num']):r for r in json.loads(Path(__file__).with_name('map_catalog.json').read_text())['maps'] if r['group']==0 and r['num']<50}

def setup(db):db.execute('CREATE TABLE IF NOT EXISTS spatial_signals(seq INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT,group_id INTEGER,map_id INTEGER,x INTEGER,y INTEGER,kind INTEGER,created REAL)')
def valid(group,num,x,y):
    m=MAPS.get((group,num));return bool(m and 0<=x<m['width'] and 0<=y<m['height'])
def insert(server,source,group,num,x,y,kind):
    setup(server.db);now=time.time()
    if kind not in KINDS or not valid(group,num,x,y):raise ValueError('Signals require a supported public Hoenn town or route')
    server.db.execute('DELETE FROM spatial_signals WHERE created<? OR created>?',(now-8,now))
    prior=server.db.execute('SELECT created FROM spatial_signals WHERE source=? ORDER BY seq DESC LIMIT 1',(source,)).fetchone()
    if prior and now-prior[0]<2:raise ValueError('Wait two seconds between signals')
    server.db.execute('DELETE FROM spatial_signals WHERE source=?',(source,))
    if server.db.execute('SELECT count(*) FROM spatial_signals').fetchone()[0]>=64:raise ValueError('Signal capacity busy')
    seq=server.db.execute('INSERT INTO spatial_signals(source,group_id,map_id,x,y,kind,created) VALUES(?,?,?,?,?,?,?)',(source,group,num,x,y,KINDS.index(kind),now)).lastrowid
    return dict(outcome='spatial_signal_committed',signal=seq,kind=kind,position=[group,num,x,y],expires_seconds=8,limits='Public fictional intent, not verified danger, arrival, assistance or proof anyone rendered it.')
def signal(server,actor,row,args):
    from .spatial_speech import ready_actor
    if set(args)!={'kind'} or type(args['kind']) is not str:raise ValueError('Choose look, meet, help or danger')
    ready=ready_actor(server,actor)
    if not ready or ready[1].get('region_revision'):raise ValueError('Signal requires actual stationary native-map resident')
    obj=ready[1]
    return insert(server,'actor:'+actor,obj['group'],obj['num'],obj['x'],obj['y'],args['kind'])
def handle(server,conn,raw):
    setup(server.db)
    try:
        f=raw.decode('ascii').split(' ')
        if f==['H','OFF']:conn['signals']=False;return 'H CLEAR\n'
        if f==['H','ON']:conn['signals']=True;return 'H CLEAR\n'
        if not conn.get('signals'):raise ValueError()
        peer=conn['presence'];state=peer.get('state');now=time.monotonic()
        if (not state or not state[6] or not 0<=now-peer.get('state_time',0)<=3 or peer.get('closing') or server.link_protocol.busy(conn['id']) or not valid(*state[:4])):raise ValueError()
        group,num,x,y=state[:4]
        if len(f)==3 and f[:2]==['H','SEND']:
            with server.db:insert(server,'player:'+conn['id'],group,num,x,y,f[2])
            return 'H ACK\n'
        if f!=['H','GET']:raise ValueError()
        moment=time.time()
        rows=server.db.execute('SELECT seq,source,x,y,kind,created FROM spatial_signals WHERE group_id=? AND map_id=? AND created<=? AND created>? ORDER BY seq DESC',(group,num,moment,moment-8)).fetchall()
        for seq,source,sx,sy,kind,created in rows:
            if abs(sx-x)+abs(sy-y)>6:continue
            ttl=max(1,int((created+8-moment)*60))
            if conn.get('signal_notice')!=seq:
                conn['signal_notice']=seq
                if peer.get('chat'):server.guild_chat.message(peer,'World',f"{source.split(':',1)[1]} signals {KINDS[kind]} at ({sx},{sy}). Intent, not verified danger.")
            return f'H MARK {seq} {group} {num} {sx} {sy} {ttl} {kind}\n'
        return 'H CLEAR\n'
    except (ValueError,KeyError,UnicodeError):return 'H CLEAR\n'
