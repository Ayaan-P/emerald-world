"""Optional local native services following an actual canonical conversation.

An admitted attempt freezes one offer; no public teaching outcome is inferred.
"""
import secrets
import time
from .actor_tutors import MOVES

def validate(service, identity):
    if service is None:return
    if (type(service) is not dict or set(service)!={'move','appearances'}
            or type(service['move']) is not int or service['move'] not in MOVES
            or type(service['appearances']) is not list or not service['appearances']
            or any(type(k) is not str for k in service['appearances'])
            or len(service['appearances'])>2 or len(set(service['appearances']))!=len(service['appearances'])):
        raise ValueError('Tutor requires a reviewed move and explicit conversation appearances')
    from .canonical_cast import location
    if any(type(key) is not str or location(key)[0]!=identity for key in service['appearances']):
        raise ValueError('Tutor appearance must belong to this original character')

def hint(row,key):
    service=row.get('tutor')
    return 'Optional tutor: /history tutor '+key if service and key in service['appearances'] else ''

def handle(server,conn,run,key,guard):
    from .canonical_cast import records,location
    identity,map_name=location(key)
    row=records(server.module_state).get(identity)
    service=(row or {}).get('tutor')
    reached=conn.get('canonical_location') or {}
    if (not service or key not in service['appearances'] or conn.get('core_active_run')!=run
            or reached.get('actor')!=identity or reached.get('map')!=map_name or reached.get('run')!=run
            or reached.get('version')!=row['version'] or reached.get('expires',0)<time.monotonic()
            or not (conn.get('state') or [0]*7)[6]):
        conn.pop('canonical_tutor_preview',None)
        raise ValueError('Talk to this character at the current appearance before tutoring')
    server.core_story._place(conn,map_name)
    if guard=='preview':
        token=secrets.token_hex(16)
        conn['canonical_tutor_preview']=dict(token=token,run=run,key=key,version=row['version'],move=service['move'],until=time.monotonic()+60)
        return dict(tutor_move=service['move'],tutor_token=token)
    preview=conn.pop('canonical_tutor_preview',None)
    if (not preview or guard!=preview['token'] or preview['run']!=run or preview['key']!=key
            or preview['version']!=row['version'] or preview['move']!=service['move']
            or preview['until']<time.monotonic()):
        raise ValueError('Tutor preview expired or changed; preview again')
    # Consume once. No automatic retry, save write, teaching record or reward.
    return dict(tutor_move=service['move'],tutor_token='accepted')
