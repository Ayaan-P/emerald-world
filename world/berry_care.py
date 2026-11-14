"""Optional shared soil care, not shared trees or inventory.

A client-reported completed native watering leaves one hour of care for that
plot and growth stage. Later visitors apply only the stock stage watering bit
on their OWN plant. No species, harvest, bag or catch identity is replicated.
"""
import json
from pathlib import Path
import time

PLOTS = json.loads(Path(__file__).with_name('berry_care_plots.json').read_text())

def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS shared_soil_care(plot INTEGER NOT NULL, stage INTEGER NOT NULL, expires REAL NOT NULL, PRIMARY KEY(plot,stage))')

def inspect(server):
    setup(server.db)
    return dict(map='Route104', care=[dict(plot=p, stage=s, expires=e) for p,s,e in server.db.execute('SELECT * FROM shared_soil_care WHERE expires>?',(time.time(),))], basis='client_reported_native_watering', limits='Stage care only. Trees, species, growth clocks and harvests remain private. No planted or harvested item is asserted.')

def handle(server, channel, raw):
    try:
        w=raw.decode('ascii').split()
        if len(w)!=5 or w[0]!='BC' or w[1] not in ('WATER','GET'):raise ValueError()
        if any(not v.isascii() or not v.isdigit() or len(v)>10 for v in w[2:]):raise ValueError()
        seq,plot,stage=map(int,w[2:])
        if not 0<seq<=0xffffffff or not 1<=stage<=4:raise ValueError()
        peer=channel['presence'];state=peer.get('state')
        if (server.link_channels.get(channel['id']) is not channel or server.peers.get(channel['id']) is not peer or peer.get('closing') or not state or not state[6] or tuple(state[:2])!=(PLOTS['group'],PLOTS['num']) or not 0<=time.monotonic()-peer.get('state_time',0)<=3):raise ValueError()
        target=next((p for p in PLOTS['plots'] if p['id']==plot),None)
        dx,dy={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(state[4],(0,0))
        if not target or (state[2]+dx,state[3]+dy)!=(target['x'],target['y']):raise ValueError()
        # Social tag membership is not a lock; actual encounters/native sessions are.
        protocol=server.link_protocol
        if channel['id'] in protocol.sessions._locks or channel['id'] in protocol._encounters:raise ValueError()
        previous=channel.get('soil_last')
        if previous and seq<=previous[0]:
            return previous[2] if (seq,tuple(w))==previous[:2] else 'BC FAIL\n'
        now=time.time();setup(server.db)
        if w[1]=='WATER':
            # Never extend an existing interval on duplicate/replayed watering.
            # There is no finite commodity or spender transaction in this rule.
            with server.db:
                old=server.db.execute('SELECT expires FROM shared_soil_care WHERE plot=? AND stage=?',(plot,stage)).fetchone()
                if not old or old[0]<=now:
                    server.db.execute('INSERT OR REPLACE INTO shared_soil_care VALUES(?,?,?)',(plot,stage,now+3600))
            reply=f'BC STORED {seq}\n'
            channel['soil_last']=(seq,tuple(w),reply)
            return reply
        row=server.db.execute('SELECT expires FROM shared_soil_care WHERE plot=? AND stage=?',(plot,stage)).fetchone()
        reply=f'BC CARE {seq} {plot} {stage}\n' if row and row[0]-now>=3 else f'BC NONE {seq}\n'
        channel['soil_last']=(seq,tuple(w),reply)
        return reply
    except (ValueError,KeyError,TypeError,UnicodeError):
        return 'BC FAIL\n'
