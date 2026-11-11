"""Typed UI negotiation over the existing move-effect authority; no alternate effects."""
import re
from .guilds import GuildError
from .overworld_moves import command


def handle(server,conn,raw):
    seq=0;channel=conn
    try:
        conn=channel['presence']
        if server.link_channels.get(channel['id']) is not channel or server.peers.get(channel['id']) is not conn:raise ValueError()
        f=raw.decode('ascii').split()
        if len(f)<3 or f[0]!='FM' or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
        if f==['FM','WATCH','1']:
            channel['move_feedback']=True
            return 'FM WATCH 1\n'
        seq=int(f[2])
        if seq>0xffffffff or server.link_protocol.field_action_busy(conn['id']):raise ValueError()
        if f[1] in ('SGET','CLUE'):
            from .move_sensing import handle as sensing_handle
            return sensing_handle(server,channel,conn,f,seq)
        if f[1]=='WGET' and len(f)==4 and f[3].isdigit() and 0<int(f[3])<=65535:
            from .move_weather import offer
            return offer(server,conn,seq,int(f[3]))
        if f[1]=='PGET' and len(f)==4 and f[3].isdigit() and 0<int(f[3])<=65535:
            from .encounter_profiles import offer
            return offer(server,conn,seq,int(f[3]))
        if f[1]=='LOOK' and len(f)==3:
            # Public object requirements only; never request or upload a party roster.
            from . import actor_objects,object_choices
            from .overworld_moves import requirements
            obj=object_choices.facing(server,conn);current=actor_objects.offers(server,obj)
            allowed=server.module_state.get('world_object_player_choices',{}).get(obj['id'],[])
            moves={m for action,values in requirements(server,obj).items()
                   if action in allowed and action in current.get('actions',{}) for m in values}
            if any(not 0<m<1024 for m in moves):raise ValueError()
            mask=bytearray(128)
            for move in moves:mask[move//8]|=1<<(move%8)
            channel.pop('field_move_ui',None);conn.pop('object_moves',None)
            return f"FM LOOKED {seq} {obj['text'].encode('ascii').hex()} {mask.hex()}\n"
        if f[1]=='GET' and len(f)==4 and f[3].isdigit() and 0<int(f[3])<=65535:
            if getattr(server,'object_use_pending',None):raise ValueError()
            command(server,conn,['moves']);offer=conn['object_moves'];move=int(f[3])
            actions=[a for a,moves in offer['choices'].items() if move in moves]
            if not 1<=len(actions)<=8:raise ValueError()
            channel['field_move_ui']=dict(seq=seq,move=move,token=offer['token'],actions=actions)
            return 'FM OFFER '+str(seq)+' '+offer['token']+' '+str(len(actions))+' '+' '.join(actions)+'\n'
        if f[1]=='VIEW' and len(f)==5:
            import time
            from . import actor_objects,object_choices
            pending=channel.get('field_move_ui');saved=conn.get('object_moves')
            obj=object_choices.facing(server,conn);current=actor_objects.offers(server,obj)
            if (not pending or not saved or pending['seq']!=seq or pending['token']!=f[3]
                or f[4] not in pending['actions'] or saved['token']!=f[3]
                or saved['until']<time.monotonic() or saved['object']!=obj['id']
                or saved['revision']!=current.get('object_revision')):raise ValueError()
            label=current['actions'][f[4]]
            if len(label)>28:label=label[:25]+'...'
            response=current.get('previews',{}).get(f[4],'Response not described')
            values=[obj['text'],label,response]
            if any(type(v) is not str or not 1<=len(v)<=28 or any(not 32<=ord(c)<127 for c in v) for v in values):raise ValueError()
            return 'FM DETAIL '+str(seq)+' '+f[3]+' '+f[4]+' '+' '.join(v.encode('ascii').hex() for v in values)+'\n'
        if f[1]=='USE' and len(f)==5:
            pending=channel.pop('field_move_ui',None)
            if not pending or pending['seq']!=seq or pending['token']!=f[3] or f[4] not in pending['actions']:raise ValueError()
            command(server,conn,['move',f[3],f[4],str(pending['move'])])
            server.object_use_pending['field_move_ui_seq']=seq
            server.object_use_pending['field_move_ui_channel']=channel
            return f'FM WAIT {seq}\n'
        raise ValueError()
    except (ValueError,KeyError,UnicodeError,GuildError):
        channel.pop('field_move_ui',None)
        return f'FM FAIL {seq}\n'
