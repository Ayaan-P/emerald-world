"""Read-only local-owner journal derived from committed world history."""
import json
import re
import sqlite3
from .rules_ui import _owned_server
from .session import SessionError
from .world_memory import native_place


def _label(place):
    if place.startswith('native:'):
        return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', place[7:]).replace('_', ' ')
    return 'Generated place'


def describe(event, place=None):
    """Describe only the actual structural change, never a claimed story outcome."""
    kind = event['event']
    details = []
    if kind == 'area_activated':
        title = 'Area activated'
        details = [event.get('label') or 'Generated area',
                   'Continues the same recorded place.' if event.get('continued') else 'This content revision became active.']
    elif kind == 'area_named':
        title = 'Place renamed'
        details = [event['before'] + ' → ' + event['after']]
    elif kind == 'terrain_changed':
        title = str(len(event['tiles'])) + ' terrain cells changed'
        details = [f"({t['x']}, {t['y']}): {t['before']} → {t['after']}" for t in event['tiles'][:8]]
        if len(event['tiles']) > 8:
            details.append(str(len(event['tiles']) - 8) + ' more changed cells in this record.')
    elif kind == 'character_changed':
        character = event['after']
        title = character['name'] + ' continued their story'
        details = [character['role'], 'Status: ' + character['status'],
                   'Authored motivation: ' + character['reason']]
        details.extend('Goal: ' + goal for goal in character['goals'])
        details.append('Team plan: ' + ', '.join('species ' + str(mon['species']) +
                       ' at level ' + str(mon['level']) for mon in character['team']))
        details.append('This is an authored character change, not proof of a battle or catch.')
    elif kind == 'canonical_speaker_decided':
        title='A speaker answered '+event['character_id']
        details=[event['question'],event['label'],'Speaker choice with optional advice, not group consensus or story progression.']
    elif kind == 'canonical_council_agreed':
        title='A group answered '+event['character_id']
        details=[event['question'],event['label'],str(event['participants'])+' trainers unanimously agreed. Preference only, not story progression or completed activity.']
    elif kind == 'canonical_campaign_milestone':
        title=event['summary']
        details=['Shared by future campaign opt-in. Native client attestation, not another trainer progression or actor achievement.']
    elif kind == 'character_field_report':
        title=event['character_name']+': '+event['title']
        details=[str(len(event['samples']))+' visited route points measured on exact map '+event['revision'][:12],
                 str(len(event['junctions']))+' junctions; '+str(len(event['dead_ends']))+' dead ends.',
                 'Static access geometry, not wildlife sightings or player activity.']
    elif kind == 'character_encounter':
        title=event['character_id']+' '+('reached '+event['recipient'] if event['outcome']=='public_message_delivered' else 'missed an encounter')
        details=[event.get('text',event.get('reason','')), 'Actual authority positions. No reply, friendship or player participation is inferred.']
    elif kind == 'character_journey_arrived':
        title=event['character_name']+' reached a destination'
        details=[str(event['steps'])+' authority walking steps on exact map '+event['revision'][:12],
                 'Authority arrival; clients may still be rendering movement. No player or original story NPC travel is implied.']
    elif kind == 'canonical_intention_fulfilled':
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' completed a retained intention'
        details=[event['kind']+': '+event['target'],'Actual committed action receipt: '+str(event['action_receipt'])]
    elif kind in ('canonical_contribution_proposed','canonical_contribution_resolved'):
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' '+('offered project guidance' if kind.endswith('proposed') else 'decided on a contribution')
        details=[event.get('text',event.get('decision','')), 'Project: '+event['course'],
                 'Public author collaboration. No physical attendance or player participation is implied.']
    elif kind in ('canonical_project_invited','canonical_project_decided'):
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' '+('invited '+BINDINGS[event['recipient']]['name'] if kind.endswith('invited') else 'chose to '+event['decision']+' a project')
        details=['Project: '+event['intention'],'Independent project decision. No physical meeting or mutual affection is implied.']
    elif kind == 'canonical_initiative_published':
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' opened a shared project'
        details=[event['title'],'Executable public choices installed; no physical participation or completed work implied.']
    elif kind == 'canonical_action_obstructed':
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' encountered a changed project'
        details=['A retained project choice was unavailable. The actor can reconsider their plan.', 'No action completed and no cause or blame is inferred.']
    elif kind == 'canonical_world_action_committed':
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' changed a shared opportunity'
        details=[event['result'],'Shared narrative state, not physical travel or native progression.']
    elif kind == 'canonical_construction_completed':
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['character_id']]['name']+' completed '+event['label']
        details=[str(event['report']['added_walkable_tiles'])+' connected walkable tiles added.',
                 'Abstract authority project execution, not animated labor, NPC travel or player resource gathering.']
    elif kind == 'canonical_study_published':
        title=event['character_name']+' installed '+event['title']
        details=[str(len(event['sites']))+' optional survey sites on map revision '+event['revision'][:12],
                 'An exploration activity, not character travel or discoveries. Player visits stay private unless shared.']
    elif kind == 'canonical_project_published':
        title=event['character_name']+' published '+event['title']
        details=['Playable relay course installed: '+event['course'],
                 str(event['limit'])+' second limit. '+('Mounts required.' if event['mounted'] else 'On-foot practice.'),
                 'No player has been joined or credited. No physical construction or race completion is implied.']
    elif kind == 'canonical_letter_delivered':
        from .canonical_cast import BINDINGS
        title=BINDINGS[event['sender']]['name']+' wrote to '+BINDINGS[event['recipient']]['name']
        details=[event['text'],'Delivered public in-world correspondence. No physical meeting, travel or battle is implied.']
    elif kind == 'canonical_actor_changed':
        title=event['character_name']+' reconsidered a goal'
        details=['Authored goal: '+event['after']['goal'],
                 'Supplemental dialogue: '+event['after']['dialogue'],
                 'Based on public evidence records: '+', '.join(map(str,event['after']['evidence'])),
                 'An authored interpretation, not proof that this character performed an activity. Original gameplay is unchanged.']
    elif kind == 'guild_goal_completed':
        title = 'Guild '+event['goal_kind']+' completed'
        details = [event['guild_name']+' completed its '+event['goal_kind']+' goal.',
                   str(event['credited'])+' credited toward a goal of '+str(event['target'])+'.',
                   str(event['awarded_guild_xp'])+' guild XP awarded by the authority.',
                   'Based on authenticated client presence reports, not independently simulated travel.']
    elif kind == 'mechanic_changed':
        title = 'Shared world content changed'
        old = {obj['id']:obj for obj in event['before']['objects']}
        new = {obj['id']:obj for obj in event['after']['objects']}
        for identity in sorted(old.keys() | new.keys()):
            a, b = old.get(identity), new.get(identity)
            if place is not None and not any(obj and native_place(obj['group'],obj['num']) == place for obj in (a,b)):
                continue
            if a == b:
                continue
            if a is None:
                details.append(f"NPC {identity} appeared at ({b['x']}, {b['y']}).")
                details.append('Dialogue: ' + b['text'])
            elif b is None:
                details.append('NPC ' + identity + ' was removed from the shared overlay.')
            else:
                if a['text'] != b['text']:
                    details.append('NPC ' + identity + ' dialogue changed: ' + a['text'] + ' → ' + b['text'])
                if (a['group'],a['num'],a['x'],a['y']) != (b['group'],b['num'],b['x'],b['y']):
                    details.append(f"NPC {identity} moved from ({a['x']}, {a['y']}) to ({b['x']}, {b['y']}).")
                if a['gfx'] != b['gfx']:
                    details.append('NPC ' + identity + ' appearance changed.')
        old_tiles = {tuple(t[:4]):t for t in event['before']['tiles']}
        new_tiles = {tuple(t[:4]):t for t in event['after']['tiles']}
        count = sum(old_tiles.get(k) != new_tiles.get(k) for k in old_tiles.keys() | new_tiles.keys()
                    if place is None or native_place(*k[:2]) == place)
        if count:
            details.append(str(count) + ' shared map-overlay cells changed.')
        if not details:
            details = ['Mechanic source committed without a visible overlay change.']
    else:
        title, details = 'Recorded world change', ['See the authority record for this event.']
    return dict(seq=event['seq'], recorded_at=event['recorded_at'], title=title, details=details,
                evidence='authority_commit', places=event.get('changed_places',event.get('places',[event['place_id']] if event.get('place_id') else [])))


def read_journal(session, worlds, payload):
    if (type(payload) is not dict or not {'world'} <= set(payload)
            or not set(payload) <= {'world','place_id','through','before','world_id'}
            or type(payload['world']) is not str or payload['world'] not in {w['key'] for w in worlds}):
        raise SessionError('Choose a local world owned by this launcher.')
    server = _owned_server(session,payload['world'])
    if server is None:
        raise SessionError('Open this local host to read its journal. The game can stay closed.')
    try:
        with server.lock:
            memory = getattr(server,'memory',None)
            if memory is None:
                raise SessionError('This host does not provide a world journal yet.')
            if 'world_id' in payload and payload['world_id'] != memory.world_id:
                raise SessionError('This world changed. Refresh its journal.')
            head = server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
            through = payload.get('through',head)
            before = payload.get('before')
            place = payload.get('place_id')
            if (type(through) is not int or not 0 <= through <= head or
                    (before is not None and (type(before) is not int or not 1 <= before <= through)) or
                    (place is not None and (type(place) is not str or not 1 <= len(place) <= 128))):
                raise ValueError('invalid journal boundary')
            if ('through' in payload or before is not None) and payload.get('world_id') != memory.world_id:
                raise SessionError('Refresh the journal before reading older entries.')
            active = server.shared_cave.identity if server.shared_cave else None
            places = []
            rows = server.db.execute('SELECT DISTINCT place_id FROM world_memory_place_events ORDER BY place_id LIMIT 101').fetchall()
            for (identity,) in rows[:100]:
                label, active_here = _label(identity), False
                if identity.startswith('area:') and server.archive_generated_areas:
                    row = server.db.execute('''SELECT a.label,a.identity FROM generated_area_archive a
                        JOIN world_places p ON a.identity=p.revision WHERE p.place_id=?
                        ORDER BY (a.identity=?) DESC,a.created DESC,a.identity LIMIT 1''',(identity,active or '')).fetchone()
                    if row:
                        label, active_here = row[0], row[1] == active
                places.append(dict(id=identity,label=label,active=active_here))
            query = "SELECT seq,data FROM events WHERE kind='world_memory' AND seq<=?"
            args = [through]
            if before is not None:
                query += ' AND seq<?'
                args.append(before)
            if place is not None:
                query += ' AND seq IN (SELECT seq FROM world_memory_place_events WHERE place_id=?)'
                args.append(place)
            records = server.db.execute(query+' ORDER BY seq DESC LIMIT 21',args).fetchall()
            entries = [describe(dict(seq=seq,**json.loads(data)),place) for seq,data in records[:20]]
            current = dict(objects=[dict(id=o['id'],text=o['text'],x=o['x'],y=o['y']) for o in server.objects
                                    if place is None or native_place(o['group'],o['num']) == place],
                           active_area=next((p for p in places if p['active']),None))
            return dict(world_id=memory.world_id,through=through,entries=entries,places=places,
                        places_truncated=len(rows)>100,current=current,
                        before=entries[-1]['seq'] if entries else None,has_more=len(records)>20,
                        coverage_start_seq=int(server.db.execute("SELECT value FROM world_memory_metadata WHERE key='coverage_start_seq'").fetchone()[0]))
    except SessionError:
        raise
    except (ValueError,TypeError,KeyError,sqlite3.Error):
        raise SessionError('The journal could not be read. Refresh and try again.') from None
