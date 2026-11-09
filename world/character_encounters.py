"""Spatially grounded encounters for already rendered world characters."""
import re


def validate_control(journey,identity):
    meeting=journey.get('meeting')
    if meeting is None:return
    if (type(meeting) is not dict or set(meeting)!={'target','expected_version','text'}
            or type(meeting['target']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}',meeting['target'])
            or meeting['target']==identity or type(meeting['expected_version']) is not int
            or not 1<=meeting['expected_version']<=2**31-1
            or type(meeting['text']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,28}",meeting['text'])):
        raise ValueError('meeting requires another exact-version character and bounded public message')


def validate_request(action,actors,objects):
    if 'journey' not in action:raise ValueError('meeting requires an actual journey')
    validate_control(dict(meeting=action['meet']),action['id'])
    meeting=action['meet'];target=actors.get(meeting['target'])
    obj=next((o for o in objects if o['id']==meeting['target']),None);end=action['object']
    if (not target or target['status']!='active' or target['version']!=meeting['expected_version'] or not obj
            or not end or not end.get('region_revision') or any(obj.get(k)!=end.get(k) for k in ('group','num','region_revision'))
            or abs(obj['x']-end['x'])+abs(obj['y']-end['y'])!=1):
        raise ValueError('journey endpoint must approach the inspected target in its exact generated place')
    if end.get('text')!=meeting['text']:
        raise ValueError('visitor endpoint dialogue must show the same public message')


def commit(server,identity,control,state,objects,arrival_seq):
    from .characters import records
    from .character_walks import walking
    meeting=control['journey']['meeting'];target=records(state).get(meeting['target'])
    obj=next((o for o in objects if o['id']==meeting['target']),None);visitor=control['object']
    reason=None
    if not target or target['status']!='active' or not obj:reason='target_unavailable'
    elif target['version']!=meeting['expected_version']:reason='target_changed'
    elif any(obj.get(k)!=visitor.get(k) for k in ('group','num','region_revision')):reason='different_place'
    elif abs(obj['x']-visitor['x'])+abs(obj['y']-visitor['y'])!=1:reason='target_moved'
    elif walking(state,meeting['target']):reason='target_travelling'
    elif any(p.get('character_pending',{}).get('id')==meeting['target'] for p in server.peers.values() if type(p.get('character_pending')) is dict):reason='target_in_battle'
    data=dict(character_id=identity,recipient=meeting['target'],journey=control['journey']['id'],
        revision=visitor['region_revision'],place_id=server.memory.place(visitor['region_revision']),
        arrival_receipt=arrival_seq,publication='public_world_character_encounter',
        basis='validated_authority_adjacency_and_versions',
        outcome='missed' if reason else 'public_message_delivered',
        limits='Authority positions, not proof of rendered meeting or player participation. No reply or relationship is inferred.')
    if reason:data['reason']=reason
    else:data.update(text=meeting['text'],recipient_version=target['version'],position=[visitor['x'],visitor['y']],recipient_position=[obj['x'],obj['y']])
    server.revision=server.memory.append('character_encounter',data)


def relevant(event,identity):
    return (event.get('event')=='character_encounter'
            and event.get('publication')=='public_world_character_encounter'
            and event.get('basis')=='validated_authority_adjacency_and_versions'
            and (event.get('character_id')==identity or
                 event.get('recipient')==identity and event.get('outcome')=='public_message_delivered'))


def observed(event,revisions):
    return (event.get('event')=='character_encounter'
            and event.get('publication')=='public_world_character_encounter'
            and event.get('basis')=='validated_authority_adjacency_and_versions'
            and event.get('revision') in revisions)
