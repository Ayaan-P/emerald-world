"""Opt-in cargo relocation only at existing confirmed cave-link arrival."""
import json,time


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS player_cargo_link_settings(owner TEXT PRIMARY KEY,enabled INTEGER NOT NULL)')


def setting(server,owner):
    setup(server.db)
    return bool(owner and server.db.execute('SELECT 1 FROM player_cargo_link_settings WHERE owner=? AND enabled=1',(owner,)).fetchone())


def configure(server,conn,words):
    from .player_cargo import identity
    from .guilds import GuildError
    if len(words)!=2 or words[1] not in ('on','off'):raise GuildError('Use /guild cargo travel on or off.')
    owner=identity(server,conn)
    if not owner:raise GuildError('Take a portable world prop with this save first.')
    if conn.get('cave_link_pending'):raise GuildError('Finish or cancel the current passage before changing cargo travel.')
    setup(server.db)
    with server.db:server.db.execute('INSERT OR REPLACE INTO player_cargo_link_settings VALUES(?,?)',(owner,int(words[1]=='on')))
    return ['Portal cargo travel '+words[1]+'. Applies to this save only.',
            'When on, carried props from the source follow confirmed cave portals. Menu travel does not move cargo.',
            'Shared object locations change publicly; your bag and other saves do not. Failed transfers leave cargo unchanged.']


def freeze(server,conn,pending):
    from .player_cargo import identity
    from .guilds import GuildError
    try:owner=identity(server,conn)
    except GuildError:return
    if not setting(server,owner):return
    rows=[list(r) for r in server.db.execute('SELECT id,object,version FROM world_prop_custody WHERE owner=? ORDER BY id',(owner,)) if json.loads(r[1])['region_revision']==pending['source']]
    if rows:pending['cargo']=dict(owner=owner,trainer=conn['id'],lineage=conn['campaign_run'],rows=rows)


def validate(server,conn,pending):
    frozen=pending.get('cargo')
    if not frozen:return
    if conn.get('id')!=frozen['trainer'] or conn.get('campaign_run')!=frozen['lineage']:raise ValueError('Cargo save lineage changed during transfer')
    for identity,raw,version in frozen['rows']:
        current=server.db.execute('SELECT owner,object,version FROM world_prop_custody WHERE id=?',(identity,)).fetchone()
        if current!=(frozen['owner'],raw,version):raise ValueError('Carried cargo changed during transfer')


def arrived(server,conn,pending):
    # Caller encloses this and the existing arrival receipt in one DB transaction.
    validate(server,conn,pending);frozen=pending.get('cargo')
    if not frozen:return
    target=pending['target'].identity
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing')
        or conn.get('cave_ack')!=target or not conn.get('region_cave') or conn['region_cave'].identity!=target
        or not 0<=time.monotonic()-conn.get('state_time',0)<=5):
        raise ValueError('Fresh authenticated destination admission required for cargo')
    for identity,raw,version in frozen['rows']:
        obj=json.loads(raw);obj.update(group=server.cave_map[0],num=server.cave_map[1],region_revision=target)
        server.db.execute('UPDATE world_prop_custody SET object=?,version=? WHERE id=?',(json.dumps(obj,sort_keys=True),version+1,identity))
    return server.memory.append('player_cargo_link_arrived',dict(source=pending['source'],destination=target,objects=[r[0] for r in frozen['rows']],basis='negotiated_link_and_client_attested_entry',limits='Existing world props relocated with confirmed portal arrival. No bag items, trainer identity, save lineage, anti-cheat or physical carrying animation.'))
