"""Reviewed model-free adventures over the existing durable world authorities.

Helpers require an already owner-authorized WorldServer. Transport authentication
belongs to the caller. No player identity, arbitrary plan or source is accepted.
"""
from copy import deepcopy
import hashlib
import json
import inspect
import secrets
import sqlite3
import time
import uuid
from typing import Any

from .character_actions import action_step as _lantern_action_step
from .content_ui import ContentWorkshop
from .session import SessionError

ADVENTURE = 'lantern-trail'
LABEL = 'Lantern Trail Outpost'
PREREQUISITES = [
    'Use the supported Expansion client connected to the world where its owner installed the adventure.',
    'Have at least one conscious Pokemon that is not an Egg. An ordinary starter is enough. No badges, guild, public chronicle or special battle equipment are required.',
    'Stand outdoors on foot, with field control, not riding a Bike or Surfing. Finish any rally or other current activity before entering.',
    'After entering, use the existing native survey controls. Sharing is optional and always needs its own explicit confirmation.',
]
GUIDE = [
    'Choose Lantern Trail Outpost in launcher Explore. In the native WORLD menu choose Explore generated area. The game enters the selected shared outdoor area. Bring a conscious starter.',
    'Mira waits beside the entry clearing. Talk to her, then open WORLD, My objectives and choose Start survey. This explicitly starts your private survey. While facing Mira, ask for guide help there and use Guide directions as you walk.',
    'Follow the clear trails to lantern_outpost, wind_lookout, reed_pool and field_archive. Ivo watches the lookout and Ren keeps the archive. WORLD, My objectives shows your own saved discoveries.',
    'Ivo offers an optional level 4 practice battle. Declining never blocks the survey. There are no promised items or battle-result story triggers.',
    'You can finish every discovery privately with chronicle OFF. Your survey survives returning later. No resident claims you shared anything unless someone explicitly publishes a discovery.',
    'Optional shared choice: at wind_lookout or reed_pool, use /explore share LANDMARK to review the public record. Only adding confirm publishes it. The first of those two public discoveries chooses Mira\'s lookout watch or quiet-pool project for this world.',
    'After that choice, voluntarily share field_archive to finish the public route notes. Mira\'s dialogue and goals change durably. Other players can make the public choice first. Private discoveries are never copied into it.',
    'Return by the entry at the northwest end, or follow the connected trail to the far return exit. The named archive keeps this exact revision available when another area is active.',
]


def adventure_plan(wilds_map, place_id) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Inert authored recipe. Species are ordinary low-level Emerald species."""
    from .route_landscape import compile_plan
    route = dict(seed=12012, loops=1, reservations=[], landmarks=[
        dict(id='lantern_outpost', x=5, y=5, radius=3),
        dict(id='wind_lookout', x=16, y=7, radius=3),
        dict(id='reed_pool', x=11, y=19, radius=3),
        dict(id='field_archive', x=27, y=19, radius=3)])
    blob, report = compile_plan(route)
    revision = report['revision']

    def obj(identity, x, y, text, gfx=8):
        return dict(id=identity, group=wilds_map[0], num=wilds_map[1], x=x, y=y,
                    gfx=gfx, text=text, region_revision=revision)

    def chapter(identity, when, goals, team, object, **extra):
        return dict(id=identity, when=when, goals=goals, team=team, status='active',
                    object=object, reason='Authored Lantern Trail story, not a claimed player achievement', **extra)

    def shared(landmark):
        return dict(event='landmark_discovery_shared', place_id=place_id,
                    revision=revision, landmark=landmark)

    mira = obj('Mira', 4, 3, 'WORLD has My objectives.\nStart your private survey.')
    team = [dict(species=276, level=4)]
    characters = [dict(id='Mira', name='Mira', role='Lantern Trail keeper and private survey guide', origin_evidence=[], chapters=[
        chapter('welcome', None, ['Help visitors find four clearings without requiring public sharing',
                'Let the first voluntarily shared lookout or pool discovery choose our project'], team, mira,
                services=['guide'], next=['watch', 'quiet', 'archive_first']),
        chapter('watch', shared('wind_lookout'), ['Keep a lookout watch using voluntarily shared field notes',
                'Await an explicit archive discovery to finish the public route notes'], team,
                dict(mira, text='A lookout watch it is!\nRen keeps our route notes.'), services=['guide'], next=['watch_notes']),
        chapter('quiet', shared('reed_pool'), ['Keep the pool quiet using voluntarily shared field notes',
                'Await an explicit archive discovery to finish the public route notes'], team,
                dict(mira, text='The pool stays quiet here.\nRen keeps our route notes.'), services=['guide'], next=['quiet_notes']),
        chapter('watch_notes', shared('field_archive'), ['Keep the lookout route notes available to future visitors'], team,
                dict(mira, text='Our watch notes are saved.\nYour own trail stays yours.'), services=['guide'], next=[]),
        chapter('quiet_notes', shared('field_archive'), ['Keep the quiet-pool route notes available to future visitors'], team,
                dict(mira, text='Quiet pool notes are saved.\nYour own trail stays yours.'), services=['guide'], next=[]),
        chapter('archive_first', shared('field_archive'), ['Keep the voluntarily shared archive discovery ready',
                'Let a later shared lookout or pool discovery choose which route notes to keep'], team,
                dict(mira, text='The archive notes are ready.\nLookout or quiet pool next?'), services=['guide'], next=['watch_ready', 'quiet_ready']),
        chapter('watch_ready', shared('wind_lookout'), ['Keep the lookout route notes available to future visitors'], team,
                dict(mira, text='Our watch notes are saved.\nYour own trail stays yours.'), services=['guide'], next=[]),
        chapter('quiet_ready', shared('reed_pool'), ['Keep the quiet-pool route notes available to future visitors'], team,
                dict(mira, text='Quiet pool notes are saved.\nYour own trail stays yours.'), services=['guide'], next=[])]),
        dict(id='Ivo', name='Ivo', role='Lookout apprentice with an optional beginner practice battle', origin_evidence=[], chapters=[
            chapter('practice', None, ['Offer a level 4 practice battle with no required win',
                    'Watch the lookout without blocking its discovery'], [dict(species=278, level=4)],
                    obj('Ivo', 17, 7, 'Practice battle? Your call.\nNo win needed for the trail.', 7), next=[])]),
        dict(id='Ren', name='Ren', role='Archive keeper and private survey guide', origin_evidence=[], chapters=[
            chapter('archive', None, ['Keep the four-clearing survey available even when nobody shares',
                    'Explain that only confirmed sharing changes the public project'], [dict(species=263, level=3)],
                    obj('Ren', 28, 19, 'Four clearings, your notes.\nSharing is always your call.'), services=['guide'], next=[])])]
    from .character_chapters import validate_plan
    for character in characters:
        validate_plan(character)
    walk = dict(character='Ivo', landmarks=['wind_lookout', 'reed_pool'],
                path=[[17,7], [17,8], [18,8]], team=[dict(species=278, level=5)],
                text='Our new watch starts here.\nA rematch is up to you.')
    return blob, report, dict(route=route, characters=characters, walk=walk)


def _lantern_motion(result, context, place_id, revision, walk_plan):
    """Authored Ivo action uses only this route's actual explicit public share.

    Embedded into the ordinary sandbox with the existing action_step reducer.
    It does not read visits, invent history, or interpret battle results.
    """
    state = result['state']
    control = state.get('world_character_controls', {}).get('Ivo')
    events = context.get('character_history', {}).get('events', [])
    event = next((event for event in events if event.get('event') == 'landmark_discovery_shared'
                  and event.get('place_id') == place_id and event.get('revision') == revision
                  and event.get('landmark') in walk_plan['landmarks']), None)
    actions = []
    if control is None and event is not None:
        obj = next(o for o in result['objects'] if o['id'] == 'Ivo')
        actor = state['world_characters']['Ivo']
        actions = [dict(id='Ivo', expected_version=actor['version'], evidence=[event['seq']],
                        reason='Ivo moves to the lookout edge after an explicitly shared trail discovery',
                        changes=dict(goals=['Watch the shared project from the lookout edge',
                                            'Offer an optional level 5 rematch, never required for survey progress'],
                                     team=walk_plan['team']),
                        object=dict(obj, x=walk_plan['path'][-1][0], y=walk_plan['path'][-1][1], text=walk_plan['text']),
                        walk=walk_plan['path'])]
    if actions or control is not None:
        import hashlib
        definition = hashlib.sha256(('lantern-trail-ivo-walk-01:' + revision).encode()).hexdigest()
        return _lantern_action_step(actions, definition, result, context)
    return result


class AdventureWorkshop:
    def __init__(self):
        self.draft: dict[str, Any] | None = None

    def read(self, server):
        current = ContentWorkshop()._read(server, '')
        receipt = server.module_state.get('world_product_adventures', {}).get(ADVENTURE)
        current['prerequisites'] = list(PREREQUISITES)
        current['adventures'] = [dict(id=ADVENTURE, label=LABEL,
            summary='A resident-led private survey, optional beginner battle and an opt-in public project.',
            guide=list(GUIDE), installed=bool(receipt), revision=receipt['revision'] if receipt else None)]
        return current

    def _guard(self, server):
        current = self.read(server)
        # Public sequence alone does not detect a mechanic state tick or private
        # occupancy change. Bind every authoritative behavior/geometry checkpoint.
        return dict(world_id=current['world_id'], sequence=current['sequence'], identity=current['identity'],
                    module=server.candidate.sha256 if server.candidate else None,
                    state=deepcopy(server.module_state), objects=deepcopy(server.objects), tiles=deepcopy(server.tiles),
                    cursor=server.interaction_cursor,
                    archive=server.db.execute('SELECT identity,label FROM generated_area_archive ORDER BY identity').fetchall())

    def preview(self, server, adventure=ADVENTURE):
        with server.lock:
            self.draft = None
            if adventure != ADVENTURE:
                raise SessionError('Choose a supported named adventure.')
            current = self.read(server)
            receipt = server.module_state.get('world_product_adventures', {}).get(ADVENTURE)
            place_id = receipt['place_id'] if receipt else 'area:' + str(uuid.uuid4())
            blob, report, plan = adventure_plan(server.wilds_map, place_id)
            if not receipt and any(p['id'] in current['residents'] for p in plan['characters']):
                raise SessionError('Keep existing characters. An adventure resident identity is already in use.')
            if receipt:
                archived = server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?', (report['revision'],)).fetchone()
                if receipt != dict(revision=report['revision'], place_id=place_id, edition=1):
                    raise SessionError('Installed adventure receipt changed. Do not overwrite it.')
                survey = server.db.execute('SELECT sites FROM survey_routes WHERE revision=?', (report['revision'],)).fetchone()
                place = server.db.execute('SELECT place_id FROM world_places WHERE revision=?', (report['revision'],)).fetchone()
                expected_sites = [site for site in report['landmarks'] if site['id'] not in ('entry', 'exit')]
                programs = server.module_state.get('world_character_chapters', {})
                if (survey is None or json.loads(survey[0]) != expected_sites or place != (place_id,) or
                        any(character['id'] not in current['residents'] or
                            programs.get(character['id'], {}).get('definition') != hashlib.sha256(json.dumps(character, sort_keys=True).encode()).hexdigest()
                            for character in plan['characters'])):
                    raise SessionError('Installed adventure is incomplete or changed. Review its archive without overwriting it.')
                if receipt['revision'] != report['revision'] or archived is None or archived[0] != blob:
                    raise SessionError('Installed adventure archive changed. Do not overwrite it.')
            elif server.db.execute('SELECT 1 FROM generated_area_archive WHERE identity=?', (report['revision'],)).fetchone():
                raise SessionError('This route revision already belongs to other content. Do not adopt or overwrite it.')
            token = secrets.token_hex(24)
            self.draft = dict(server=server, token=token, expires=time.monotonic()+900, guard=self._guard(server),
                              blob=blob, report=report, plan=plan, place_id=place_id, installed=bool(receipt))
            from .shared_cave import SharedCave
            return dict(current, token=token, adventure=ADVENTURE, label=LABEL, plan=deepcopy(plan), report=deepcopy(report),
                        guide=list(GUIDE), proposed_rows=[r.decode('ascii') for r in SharedCave(blob)._rows],
                        validation='Preview only. Apply requires owner confirmation and no connected games. Existing areas stay archived unchanged. No private history is published.')

    def apply(self, server, token, confirmed=False):
        with server.lock:
            draft = self.draft
            if confirmed is not True:
                raise SessionError('Review and confirm the exact adventure before applying.')
            if (draft is None or draft['server'] is not server or token != draft['token'] or
                    time.monotonic() > draft['expires'] or draft['guard'] != self._guard(server)):
                self.draft = None
                raise SessionError('World or review changed. Preview the adventure again.')
            if any(not p.get('closing') for p in server.peers.values()):
                raise SessionError('The world is occupied. Save and close connected games before applying.')
            if server.job is not None or server.deployment is not None:
                raise SessionError('Wait for pending mechanic work before applying.')
            self.draft = None
            if draft['installed']:
                return dict(self.read(server), saved=True, already_installed=True, adventure=ADVENTURE,
                            registered_revision=draft['report']['revision'], guide=list(GUIDE))
            context = dict(data=server.inspect(), runtime=dict(previous_source=server.candidate.source if server.candidate else None))
            # Wrap each validated resident with the existing chapter compiler.
            from .character_chapters import compile_plan
            source = context['runtime']['previous_source'] or ''
            for character in draft['plan']['characters']:
                source = compile_plan(character, context)
                context['data']['module_hash'] = hashlib.sha256(source.encode()).hexdigest()
                context['runtime']['previous_source'] = source
            source += '\n' + inspect.getsource(_lantern_action_step).replace('def action_step(', 'def _lantern_action_step(', 1)
            source += '\n' + inspect.getsource(_lantern_motion)
            receipt = dict(revision=draft['report']['revision'], place_id=draft['place_id'], edition=1)
            source += '\ndef update(context, state, _adventure_previous=update):\n    result = _adventure_previous(context, state)\n    result = _lantern_motion(result, context, %r, %r, %r)\n    result["state"].setdefault("world_product_adventures", {})[%r] = %r\n    return result\n' % (receipt['place_id'], receipt['revision'], draft['plan']['walk'], ADVENTURE, receipt)
            runtime_context = server._context()
            old_state = deepcopy(server.module_state)
        path = server.root / 'candidates' / ('lantern-trail-' + uuid.uuid4().hex + '.py')
        try:
            with path.open('x') as stream:
                stream.write(source)
            candidate = server.runtime.stage(path)
            result = server.runtime.run(candidate, runtime_context, old_state)
            with server.lock:
                if (draft['guard'] != self._guard(server) or server.peers or
                        server.job is not None or server.deployment is not None):
                    raise SessionError('World changed during sandbox staging. Preview again.')
                state_json, tiles = server._validated(result)
                continuation = dict(candidate=candidate, objects=result.get('objects', []), state=json.loads(state_json),
                                    tiles=tiles, cursor=server.interaction_cursor,
                                    previous_hash=draft['guard']['module'], ids=[], clear_error=True)
                sites = [s for s in draft['report']['landmarks'] if s['id'] not in ('entry', 'exit')]
                # Queue auxiliary rows BEFORE _replace_cave's existing atomic
                # authority commit. Its inner transaction commits all four pieces:
                # archive, resident module, place identity and registered survey.
                # Do not call register() afterward (that could leave a partial import).
                with server.db:
                    server.db.execute('INSERT INTO world_places VALUES (?,?)', (receipt['revision'], receipt['place_id']))
                    server.db.execute('INSERT INTO survey_routes VALUES (?,?)', (receipt['revision'], json.dumps(sites, sort_keys=True)))
                    server._replace_cave(draft['blob'], label=LABEL, expected_world_id=draft['guard']['world_id'],
                                         expected_sequence=draft['guard']['sequence'], history_evidence=[],
                                         character_continuation=continuation)
                # Exact read-back, not merely a successful invocation.
                archived = server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?', (receipt['revision'],)).fetchone()
                survey = server.db.execute('SELECT sites FROM survey_routes WHERE revision=?', (receipt['revision'],)).fetchone()
                if (archived is None or archived[0] != draft['blob'] or survey is None or json.loads(survey[0]) != sites or
                        server.module_state.get('world_product_adventures', {}).get(ADVENTURE) != receipt):
                    raise SessionError('Adventure save could not be confirmed. Reload before retrying.')
                return dict(self.read(server), saved=True, already_installed=False, adventure=ADVENTURE,
                            registered_revision=receipt['revision'], guide=list(GUIDE))
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
            raise SessionError('Adventure was not confirmed: ' + str(exc) + '. Reload before retrying.') from None
        finally:
            path.unlink(missing_ok=True)

    def action(self, session, worlds, action, payload):
        fields = {'adventure_read': {'world'}, 'adventure_preview': {'world', 'adventure'},
                  'adventure_apply': {'world', 'token', 'confirmed'}}
        if type(payload) is not dict or action not in fields or set(payload) != fields[action]:
            raise SessionError('Choose a world and supported adventure fields.')
        server = session.server
        if (payload['world'] not in {w['key'] for w in worlds} or session.state is None or
                session.state.name != payload['world'] or server is None or server._closed):
            raise SessionError('Open the selected owner-local world before managing adventures.')
        if action == 'adventure_read':
            with server.lock:
                result = self.read(server)
        elif action == 'adventure_preview':
            result = self.preview(server, payload['adventure'])
        else:
            result = self.apply(server, payload['token'], payload['confirmed'])
        return dict(result, world=payload['world'])


def _workshop(server):
    with server.lock:
        if not hasattr(server, '_product_adventure_workshop'):
            server._product_adventure_workshop = AdventureWorkshop()
        return server._product_adventure_workshop


def read_adventures(server):
    with server.lock: return _workshop(server).read(server)


def preview_adventure(server, adventure=ADVENTURE):
    return _workshop(server).preview(server, adventure)


def apply_adventure(server, token, confirmed=False):
    return _workshop(server).apply(server, token, confirmed)
