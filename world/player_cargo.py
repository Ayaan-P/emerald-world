"""Save-lineage custody of portable world props, never native bag inventory."""
import copy,json,secrets,time
from .guilds import GuildError


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS player_prop_carriers(owner TEXT PRIMARY KEY,trainer TEXT,lineage TEXT,UNIQUE(trainer,lineage))')


def is_player(db,owner):
    setup(db)
    return db.execute('SELECT 1 FROM player_prop_carriers WHERE owner=?',(owner,)).fetchone() is not None


def identity(server,conn):
    setup(server.db)
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not conn.get('private_commands')
        or not conn.get('world_props_capable') or not conn.get('campaign_run')):
        raise GuildError('Cargo needs an authenticated matched client and an active save lineage.')
    row=server.db.execute('SELECT owner FROM player_prop_carriers WHERE trainer=? AND lineage=?',(conn['id'],conn['campaign_run'])).fetchone()
    return row[0] if row else None


def ready(server,conn):
    s=conn.get('state')
    if not s or not s[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or conn.get('character_pending'):
        raise GuildError('Stand ready in the field before moving world cargo.')
    if server.job is not None or server.deployment is not None or not server.candidate or getattr(server,'object_use_pending',None):
        raise GuildError('World changes are pending. Try again when the world is ready.')
    return s


def command(server,conn,words):
    from .prop_custody import install,project
    from .object_choices import facing
    from .region_characters import scoped,validate_region_objects
    from .characters import validate_transition
    install(server.db);owner=identity(server,conn)
    if words and words[0]=='travel':
        from .player_cargo_links import configure
        return configure(server,conn,words)
    if not words:
        held=server.db.execute('SELECT id,object FROM world_prop_custody WHERE owner=? ORDER BY id',(owner,)).fetchall() if owner else []
        return ['World cargo: /guild cargo take while facing a portable prop; /guild cargo drop ID to place ahead.',
                'Shared objects only, not bag items. Custody survives restart for this save; no carrying animation.',
                'Default: cargo stays in its map. /guild cargo travel on enables confirmed cave portals for this save.']+[
                    f'{i}: map {json.loads(raw)["region_revision"][:12]}' for i,raw in held]
    if words!=['take'] and not (len(words)==2 and words[0]=='drop'):
        raise GuildError('Use /guild cargo, take, or drop ID.')
    if conn.get('cave_link_pending'):raise GuildError('Finish or cancel the passage before taking or placing cargo.')
    s=ready(server,conn)
    taking=words==['take']
    state=copy.deepcopy(server.module_state)
    if taking:
        obj=copy.deepcopy(facing(server,conn))
        if obj.get('portable') is not True or not obj.get('region_revision'):
            raise GuildError('Only explicitly portable generated-world props can be carried.')
        prior=server.db.execute('SELECT owner,version FROM world_prop_custody WHERE id=?',(obj['id'],)).fetchone()
        if prior and prior[0] is not None:raise GuildError('This prop already has a carrier.')
        if owner and server.db.execute('SELECT count(*) FROM world_prop_custody WHERE owner=?',(owner,)).fetchone()[0]>=4:
            raise GuildError('Place some cargo first; each save can carry four props.')
        if not prior and server.db.execute('SELECT count(*) FROM world_prop_custody').fetchone()[0]>=32:
            raise GuildError('World custody capacity reached.')
        version=prior[1]+1 if prior else 1
    else:
        saved=server.db.execute('SELECT owner,object,version FROM world_prop_custody WHERE id=?',(words[1],)).fetchone()
        if not owner or not saved or saved[0]!=owner:raise GuildError('This save does not carry that prop.')
        obj=json.loads(saved[1]);version=saved[2]+1
        if not scoped(server,conn,obj,obj['region_revision']):raise GuildError('Return to the exact original map revision before placing this cargo.')
        dx,dy={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(s[4],(0,0))
        if not (dx or dy):raise GuildError('Face a clear adjacent tile.')
        obj.update(x=s[2]+dx,y=s[3]+dy)
        state.setdefault('world_object_controls',{}).setdefault(obj['id'],{'state':{}})['object']={k:obj[k] for k in ('x','y','gfx','text')}
    try:
        with server.db:
            if taking and owner is None:
                owner='player:'+secrets.token_hex(16)
                server.db.execute('INSERT INTO player_prop_carriers VALUES(?,?,?)',(owner,conn['id'],conn['campaign_run']))
            server.db.execute('INSERT OR REPLACE INTO world_prop_custody VALUES(?,?,?,?)',
                (obj['id'],owner if taking else None,json.dumps(obj,sort_keys=True),version))
            projected=project(server,dict(state=state,objects=server.objects+([] if taking else [obj]),tiles=[]))
            state_json,_=server._validated(projected);objects=projected['objects']
            validate_transition(server.module_state,state,objects,server.db);validate_region_objects(server,objects,state)
            source=server.db.execute('SELECT sha256 FROM module WHERE singleton=1').fetchone()
            if not source or source[0]!=server.candidate.sha256:raise ValueError('Durable mechanic changed')
            server.db.execute('UPDATE module SET state=?,objects=? WHERE singleton=1',(state_json,json.dumps(objects)))
            seq=server.memory.append('player_world_cargo_changed',dict(object=obj['id'],operation='take' if taking else 'drop',version=version,
                revision=obj['region_revision'],position=[obj['x'],obj['y']],basis='authority_custody_with_client_attested_position',
                limits='Public object change; no trainer identity, save data, native item, physical carrying animation or travel proof.'))
    except ValueError as exc:raise GuildError(str(exc)) from None
    server.module_state=state;server.objects=objects;server.revision=seq
    return [('Carrying ' if taking else 'Placed ')+obj['id']+'. Shared world custody committed; your native bag is unchanged.']
