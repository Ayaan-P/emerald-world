"""Best-effort cosmetic live receipts; never replay history or grant gameplay."""
import json,time
from .region_characters import scoped


def remember(server,request):
    target=request['target']
    server.db.execute('CREATE TABLE IF NOT EXISTS world_move_visuals(id TEXT PRIMARY KEY,target TEXT NOT NULL)')
    server.db.execute('INSERT OR IGNORE INTO world_move_visuals VALUES(?,?)',(request['id'],json.dumps({k:target[k] for k in ('group','num','x','y','region_revision') if k in target},sort_keys=True)))


def committed(server,identity,seq,move):
    if not 0<seq<=0xffffffff:return
    if not server.db.execute("SELECT 1 FROM sqlite_master WHERE name='world_move_visuals'").fetchone():return
    row=server.db.execute('SELECT target FROM world_move_visuals WHERE id=?',(identity,)).fetchone()
    if not row:return
    target=json.loads(row[0])
    for channel in list(server.link_channels.values()):
        conn=channel.get('presence');state=(conn or {}).get('state')
        if (not channel.get('move_feedback') or channel.get('closing') or not conn or server.peers.get(channel['id']) is not conn
            or conn.get('closing') or not state or not state[6] or server.link_protocol.busy(channel['id'])
            or not 0<=time.monotonic()-conn.get('state_time',0)<=5
            or not scoped(server,conn,target,target.get('region_revision'))
            or state[:2]!=[target['group'],target['num']]
            or abs(state[2]-target['x'])>10 or abs(state[3]-target['y'])>10):continue
        server._queue(channel,'FM FX %s %s %s %s %s %s\n'%(seq,target['group'],target['num'],target['x'],target['y'],move))
