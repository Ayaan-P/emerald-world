"""Player-selected authored actions, not implicit access to agent-only actions."""
import copy,secrets,time
from . import actor_objects
from .guilds import GuildError


def facing(server,conn):
    from .region_characters import scoped
    state=conn.get('state')
    if (server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not conn.get('world_props_capable')
        or not state or not state[6] or not 0<=time.monotonic()-conn.get('state_time',0)<=5 or conn.get('character_pending')):
        raise GuildError('Stand ready facing a shared object.')
    dx,dy={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(state[4],(0,0))
    obj=next((o for o in server.objects if o.get('kind')=='prop' and state[:2]==[o['group'],o['num']]
              and [state[2]+dx,state[3]+dy]==[o['x'],o['y']] and scoped(server,conn,o,o.get('region_revision'))),None)
    if not obj:raise GuildError('No compatible shared object in front of you.')
    return obj


def command(server,conn,words):
    obj=facing(server,conn);offer=actor_objects.offers(server,obj)
    allowed=server.module_state.get('world_object_player_choices',{}).get(obj['id'],[])
    actions=[a for a in allowed if a in offer.get('actions',{})]
    if not words or words==['choices']:
        token=secrets.token_hex(6)
        conn['object_choices']=dict(token=token,object=obj['id'],revision=offer.get('object_revision'),actions=actions,until=time.monotonic()+60)
        return [obj['text'],'Choose an authored action with /guild object choose TOKEN ACTION. Shared effects are visible to other players.']+[f'{token} {a}' for a in actions] if actions else ['This object offers no player choices. Ordinary A use is unchanged.']
    if len(words)!=3 or words[0]!='choose':raise GuildError('Use /guild object choices, then /guild object choose TOKEN ACTION.')
    pending=conn.pop('object_choices',None)
    if (not pending or pending['token']!=words[1] or pending['until']<time.monotonic() or pending['object']!=obj['id']
        or pending['revision']!=offer.get('object_revision') or words[2] not in pending['actions'] or words[2] not in actions):
        raise GuildError('Object choices changed or expired. Inspect choices again.')
    if server.job is not None or server.deployment is not None or getattr(server,'object_use_pending',None):raise GuildError('Object busy. Inspect choices again shortly.')
    request=dict(actor='',version=0,object=obj['id'],action=words[2],target=copy.deepcopy(obj),actions=offer['actions'],player_choice=True,nonce=pending['token'])
    try:work=actor_objects.stage(server,request,position=tuple(conn['state'][2:4]))
    except ValueError as exc:raise GuildError(str(exc)) from None
    server.object_use_pending=dict(conn=conn,pending=work.data,action=words[2]);work.dispatch()
    return ['Selected action submitted. The shared world changes only if admitted.']
