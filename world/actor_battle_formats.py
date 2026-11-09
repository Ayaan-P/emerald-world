"""Optional native battle formats, never campaign or player-party rewrites."""
def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS actor_battle_formats(actor TEXT PRIMARY KEY,revision INTEGER,mode INTEGER)')

def current(server,actor):
    row=server.db.execute('SELECT revision,mode FROM actor_battle_formats WHERE actor=?',(actor,)).fetchone()
    return row or (0,0)

def configure(server,actor,row,args):
    from .characters import records
    if set(args)!={'format'} or args['format'] not in ('singles','doubles'):
        raise ValueError('Choose singles or doubles')
    character=records(server.module_state).get(actor)
    if not character or character['status']!='active':raise ValueError('Active world-owned trainer required')
    mode=int(args['format']=='doubles')
    if mode and (len(character['team'])<2 or not all('individual' in mon for mon in character['team'])):
        raise ValueError('Doubles requires at least two individually owned team members')
    seq=server.memory.append('character_battle_format_changed',dict(character_id=actor,format=args['format'],
        basis='optional_native_challenge_configuration',limits='Player must explicitly accept. No battle, victory, training or party mutation inferred.'))
    server.db.execute('INSERT INTO actor_battle_formats VALUES(?,?,?) ON CONFLICT(actor) DO UPDATE SET revision=excluded.revision,mode=excluded.mode',(actor,seq,mode))
    server.revision=seq
    return dict(outcome='optional_battle_format_configured',revision=seq,format=args['format'])

def line(server,conn,actor,version):
    if not conn.get('character_format_capable'):return None
    revision,mode=current(server,actor)
    return f'CHARACTER_FORMAT {actor} {version} {revision} {mode}'
