"""Explicit local-host controls over the existing session author lifecycle."""
import os
from .session import SessionError
from .canonical_cast import BINDINGS,records
from .author_backends import API_BACKENDS,validate


def action(session,worlds,command,payload):
    fields={'world'}
    if command=='cast_agent_enroll_cast':fields|={'confirmed'}
    elif command=='cast_agent_start':fields|={'provider','model','confirmed'}
    elif command in ('cast_agent_follow','cast_agent_initialize'):fields|={'actor','purpose','confirmed'}
    elif command=='cast_agent_unfollow':fields|={'actor'}
    elif command not in ('cast_agent_read','cast_agent_stop'):raise SessionError('Unknown living-cast control')
    server=session.server
    if (type(payload) is not dict or set(payload)!=fields or session.engine!='expansion-native'
            or session.state is None or payload['world']!=session.state.name
            or payload['world'] not in {w['key'] for w in worlds} or server is None or server._closed):
        raise SessionError('Open this local Expansion host before using living-cast controls.')
    try:
        if command=='cast_agent_enroll_cast':
            if payload['confirmed'] is not True:raise ValueError('Confirm public cast enrollment')
            from .canonical_seeds import initialize
            queue=session._gm_queue()
            try:initialize(queue,server)
            finally:queue.close()
        elif command=='cast_agent_start':
            if payload['confirmed'] is not True or payload['provider'] not in API_BACKENDS:raise ValueError('Explicit API provider confirmation required')
            validate(payload['provider'],payload['model'],30)
            session.start_gm(provider=payload['provider'],model=payload['model'])
        elif command=='cast_agent_stop':session.stop_gm()
        elif command in ('cast_agent_follow','cast_agent_initialize','cast_agent_unfollow'):
            actor=payload['actor']
            if actor not in BINDINGS:raise ValueError('Unknown original actor')
            if command!='cast_agent_unfollow':
                if payload['confirmed'] is not True or type(payload['purpose']) is not str or not 1<=len(payload['purpose'].strip())<=1024:raise ValueError('Confirm a bounded character purpose')
            with server.lock:inspection=server.inspect();existing=records(server.module_state)
            queue=session._gm_queue()
            try:
                from .character_reactions import configure,unfollow
                if command=='cast_agent_follow':configure(queue,inspection,actor,payload['purpose'])
                elif command=='cast_agent_unfollow':unfollow(queue,actor)
                else:
                    if actor in existing:raise ValueError('Actor already authored; follow it instead')
                    from .canonical_seeds import initialize
                    initialize(queue,server,actor=actor,purpose=payload['purpose'])
            finally:queue.close()
    except (ValueError,OSError):
        raise SessionError('Living-cast operation was not confirmed. Check selected model, host credential availability, actor history and runtime status. No automatic retry.') from None
    with server.lock:actors=records(server.module_state)
    status=session.gm_status()
    followed={r['id'] for r in status.get('characters',[])}
    thread=session.gm_thread
    return dict(world=payload['world'],running=bool(thread and thread.is_alive()),
        provider=getattr(session,'gm_provider',None),model=getattr(session,'gm_model',None),
        failed=bool(session.gm_error),providers=[dict(id=k,credential_ready=bool(os.environ.get(v[1]))) for k,v in API_BACKENDS.items()],
        actors=[dict(id=k,name=v['name'],authored=k in actors,followed=k in followed,goal=actors.get(k,{}).get('goal')) for k,v in BINDINGS.items()],
        queued=sum(r['status']=='queued' for r in status.get('requests',[])),
        failed_requests=sum(r['status'] in ('failed','interrupted') for r in status.get('requests',[])))
