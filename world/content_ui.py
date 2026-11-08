"""Explicit, reviewed local-owner access to existing content compilers.

No provider requests, private history reads or arbitrary mechanic source input.
Drafts live only in this launcher and are bound to an exact authority snapshot.
"""
from copy import deepcopy
import json
import secrets
import sqlite3
from typing import Any
import time
import uuid


def field_test_plan(wilds_map, place_id):
    """Curated test content, not generated history or a campaign achievement."""
    from .route_landscape import compile_plan
    route = dict(seed=11, loops=0, reservations=[], landmarks=[
        dict(id='field_station', x=8, y=8, radius=4),
        dict(id='lookout', x=22, y=8, radius=4)])
    blob, report = compile_plan(route)
    obj = dict(id='rc11_scholar', group=wilds_map[0], num=wilds_map[1], x=8, y=8, gfx=8,
               text='Visit the nearby lookout.\nShare only if you want to.', region_revision=report['revision'])
    first = dict(id='waiting', when=None, goals=['Wait for voluntarily shared lookout notes'],
                 team=[dict(species=277,level=12)], status='active', object=obj,
                 reason='Curated RC11 field-test character, not a campaign achievement')
    second = dict(id='researching', when=dict(event='landmark_discovery_shared',place_id=place_id,
                  revision=report['revision'],landmark='lookout'),
                  goals=['Study the shared lookout notes'], team=[dict(species=278,level=18)],
                  status='active', object=dict(obj,x=22,y=8,text='Your shared notes helped.\nMy research team is ready!'),
                  reason='An explicit public discovery activates this authored chapter')
    character = dict(id='rc11_scholar',name='Field Scholar',role='RC11 opt-in field-test researcher',
                     origin_evidence=[],chapters=[first,second])
    return blob, report, dict(route=route, character=character)

from .session import SessionError


class ContentWorkshop:
    def __init__(self):
        self.draft: dict[str, Any] | None = None

    def _read(self, server, world) -> dict[str, Any]:
        cave = server.shared_cave
        if server._closed or not server.archive_generated_areas or not server.persist_generated_cave:
            raise SessionError('Open a durable local world before authoring content.')
        memory = server.memory.context(server)
        # Only public, already committed outcomes. Never inspect survey visits,
        # trainer saves, chat, teams or private guild progress.
        outcomes = [dict(seq=seq, **json.loads(data)) for seq, data in server.db.execute(
            "SELECT seq,data FROM events WHERE kind='world_memory' AND json_extract(data,'$.event')='guild_goal_completed' ORDER BY seq DESC LIMIT 100")]
        return dict(world=world, world_id=memory['world_id'], sequence=memory['through'],
                    identity=cave.identity if cave else None, version=cave.version if cave else None,
                    rows=[row.decode('ascii') for row in cave._rows] if cave else [],
                    outcomes=outcomes, residents=sorted(server.module_state.get('world_characters', {})),
                    players=sum(not peer.get('closing') for peer in server.peers.values()))

    @staticmethod
    def _guard(current):
        return {key: current[key] for key in ('world', 'world_id', 'sequence', 'identity')}

    def action(self, session, worlds, action, payload):
        fields = {'world'}
        if action == 'content_preview': fields |= {'kind', 'label', 'plan', 'outcome_seq'}
        elif action == 'content_apply': fields |= {'token', 'confirmed'}
        elif action != 'content_read': raise SessionError('Unknown content action.')
        if type(payload) is not dict or set(payload) != fields:
            raise SessionError('Choose a local world and supported content fields.')
        server = session.server
        if (payload['world'] not in {item['key'] for item in worlds} or session.state is None
                or session.state.name != payload['world'] or server is None or server._closed):
            raise SessionError('Open the selected local world before authoring content. Hosted content management is not supported here.')
        try:
            with server.lock:
                current = self._read(server, payload['world'])
                if action == 'content_read': return current
                if action == 'content_preview':
                    self.draft = None
                    if len(json.dumps(payload['plan']).encode()) > 16384:
                        raise ValueError('content plan exceeds 16384 bytes')
                    plan = deepcopy(payload['plan']); kind = payload['kind']; label = payload['label']
                    request: dict[str, Any]
                    if kind == 'field_test':
                        if current['identity'] is not None or server.candidate is not None or server.objects:
                            raise SessionError('Use a separate empty local world for the RC11 field test. Existing geography and inhabitants cannot be replaced.')
                        if plan != {}:
                            raise ValueError('the curated field test uses its reviewed built-in plan')
                        place_id = 'area:' + str(uuid.uuid4())
                        blob, report, plan = field_test_plan(server.wilds_map, place_id)
                        request = dict(command='field_test', plan=plan, place_id=place_id)
                        mode = 'create'
                    elif kind == 'survey':
                        from .route_landscape import compile_plan
                        blob, report = compile_plan(plan)
                        row = server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?', (report['revision'],)).fetchone()
                        if current['identity'] is not None and (row is None or row[0] != blob):
                            raise SessionError('Do not replace existing geography. Register the exact archived route plan, or create a separate empty local world for a new route.')
                        request = dict(command='register_survey', plan=plan)
                        mode = 'register' if row is not None and row[0] == blob else 'create'
                    elif kind in ('outpost', 'settlement'):
                        stored = server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
                        if current['version'] != 16 or stored is None:
                            raise SessionError('Activate a saved plain 127 × 127 XL area in Explore first.')
                        mode = 'construct'
                        if kind == 'outpost':
                            from .frontier_outposts import compile_outpost
                            blob, report = compile_outpost(stored[0], plan)
                            request = dict(command='construct_outpost', plan=plan, label=label)
                        else:
                            from .settlement_plans import compile_settlement
                            seq = payload['outcome_seq']
                            if type(seq) is not int or seq not in {e['seq'] for e in current['outcomes']}:
                                raise SessionError('Choose a recorded public guild completion. Private progress is never published for you.')
                            blob, report, character = compile_settlement(stored[0], plan, seq, server.wilds_map)
                            if character['id'] in current['residents']:
                                raise SessionError('Keep existing residents. Choose a new character identity.')
                            label = plan['label']
                            request = dict(command='found_settlement', plan=plan, outcome_seq=seq)
                        request.update(previous_revision=current['identity'], expected_world_id=current['world_id'], expected_sequence=current['sequence'])
                    else:
                        raise ValueError('choose outpost, settlement or survey')
                    if type(label) is not str or not label.strip() or len(label) > 80 or any(ord(c) < 32 or ord(c) == 127 for c in label):
                        raise ValueError('choose a destination name of 1..80 printable characters')
                    from .shared_cave import SharedCave
                    proposed = SharedCave(blob)
                    token = secrets.token_hex(24)
                    self.draft = dict(token=token, server=server, guard=self._guard(current), request=request,
                                      blob=blob, report=report, mode=mode, label=label, expires=time.monotonic()+900)
                    return dict(current, token=token, kind=kind, mode=mode, plan=plan, report=report,
                                proposed_rows=[row.decode('ascii') for row in proposed._rows],
                                validation='Preview only. Apply rechecks occupancy and authority validation. Settlement publication also requires the existing mechanic sandbox.')
                draft = self.draft
                if payload['confirmed'] is not True:
                    raise SessionError('Review and confirm the exact content before applying.')
                if (draft is None or payload['token'] != draft['token'] or draft['server'] is not server
                        or time.monotonic() > draft['expires'] or draft['guard'] != self._guard(current)):
                    self.draft = None
                    raise SessionError('The world or review changed. Reload and preview again.')
                if current['players']:
                    raise SessionError('Save and close all connected games before applying content. No player is disconnected automatically.')
                # Consume before attempting a write. An uncertain result is never
                # automatically replayed, even if the HTTP response is lost.
                self.draft = None
                request = draft['request']
                if request['command'] == 'construct_outpost':
                    from .frontier_outposts import construct
                    construct(server, request)
                elif request['command'] == 'register_survey':
                    if draft['mode'] == 'create':
                        # No active area can be replaced by this route entry point.
                        server._replace_cave(draft['blob'], label=draft['label'], expected_world_id=current['world_id'],
                                             expected_sequence=current['sequence'], history_evidence=[])
                    server.landmark_survey.register(request['plan'])
                else:
                    # Staging is asynchronous. The server loop needs its lock,
                    # so use the existing private admin transport outside it.
                    pass
            if request['command'] == 'field_test':
                from .character_chapters import compile_plan
                with server.lock:
                    if server.job is not None or server.deployment is not None:
                        raise SessionError('Wait for pending mechanic work before creating a field test.')
                    context = server.inspect()
                    source = compile_plan(request['plan']['character'], context)
                    runtime_context = server._context()
                path = server.root / 'candidates' / ('field-test-' + uuid.uuid4().hex + '.py')
                with path.open('x') as stream: stream.write(source)
                candidate = server.runtime.stage(path)
                staged = server.runtime.run(candidate, runtime_context, {})
                with server.lock:
                    if (draft['guard'] != self._guard(self._read(server, payload['world']))
                            or server.job is not None or server.deployment is not None or server.peers):
                        raise SessionError('World changed during field-test staging. Reload and preview again.')
                    state_json, tiles = server._validated(staged)
                    continuation = dict(candidate=candidate, objects=staged.get('objects',[]), state=json.loads(state_json),
                                        tiles=tiles, cursor=server.interaction_cursor, previous_hash=None, ids=[], clear_error=True)
                    # Place identity, geometry and character persist in the same
                    # authority transaction. No fabricated public outcome is needed.
                    with server.db:
                        server.db.execute('INSERT INTO world_places VALUES (?,?)',(draft['report']['revision'],request['place_id']))
                        server._replace_cave(draft['blob'],label=draft['label'], expected_world_id=current['world_id'],
                                             expected_sequence=current['sequence'],history_evidence=[],character_continuation=continuation)
                    server.landmark_survey.register(request['plan']['route'])
            if request['command'] == 'found_settlement':
                from .client import admin_request
                result = admin_request('', request, admin_path=server.admin_path, timeout=120)
                if type(result) is not dict or result.get('ok') is not True:
                    raise SessionError('Settlement was not confirmed: ' + (str(result.get('error', 'unknown result')) if type(result) is dict else 'unknown result'))
            with server.lock:
                result = self._read(server, payload['world'])
                if request['command'] in ('register_survey', 'field_test'):
                    registered = server.db.execute('SELECT 1 FROM survey_routes WHERE revision=?', (draft['report']['revision'],)).fetchone()
                    if registered is None: raise SessionError('Survey registration was not confirmed. Reload before retrying.')
                elif result['identity'] != draft['report']['revision']:
                    raise SessionError('The expected content revision was not confirmed. Reload before retrying.')
                if request['command'] == 'found_settlement' and request['plan']['resident']['id'] not in result['residents']:
                    raise SessionError('The resident save was not confirmed. Reload before retrying.')
                return dict(result, saved=True, registered_revision=draft['report']['revision'])
        except SessionError:
            raise
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
            raise SessionError('Content could not finish: ' + str(exc) + '. Reload before applying again.') from None
