"""Inert, outcome-grounded settlement plans with a real expedition steward."""
from copy import deepcopy
import hashlib
import json
import uuid

from .frontier_outposts import compile_outpost
from .character_chapters import validate_plan, compile_plan


def compile_settlement(blob, plan, outcome_seq, wilds_map):
    if type(plan) is not dict or set(plan) != {'label', 'construction', 'resident'}:
        raise ValueError('settlement needs label, construction and resident')
    label = plan['label']
    if type(label) is not str or not label.strip() or len(label)>80 or any(ord(c)<32 or ord(c)==127 for c in label):
        raise ValueError('invalid settlement label')
    r = plan['resident']
    fields = {'id','name','role','goals','team','gfx','text','offer','completion_text','completion_goals'}
    if type(r) is not dict or set(r) != fields:
        raise ValueError('invalid settlement resident')
    if type(outcome_seq) is not int or outcome_seq < 1:
        raise ValueError('settlement requires a committed public outcome')
    result, report = compile_outpost(blob, plan['construction'])
    x,y,w,h = report['footprint']
    obj = dict(id=r['id'], group=wilds_map[0], num=wilds_map[1], x=x+w//2, y=y+h//2,
               gfx=r['gfx'], text=r['text'], region_revision=report['revision'])
    arrival = dict(id='arrival', when=None, goals=r['goals'], team=r['team'], status='active', object=obj,
                   reason='An authored steward establishes this outpost after public outcome '+str(outcome_seq), offer=r['offer'])
    # Existing chapter validation binds the later completion to this exact offer.
    offer = r['offer']
    if type(offer) is not dict or not {'id','revision'} <= set(offer):
        raise ValueError('resident needs a valid expedition offer')
    completed = dict(id='completed', when=dict(event='guild_goal_completed', character_id=r['id'],
        character_offer_id=offer['id'], character_offer_revision=offer['revision']),
        goals=r['completion_goals'], team=deepcopy(r['team']), status='active',
        object=dict(obj,text=r['completion_text']),
        reason='The authority recorded completion of this steward expedition')
    character = validate_plan(dict(id=r['id'], name=r['name'], role=r['role'], origin_evidence=[outcome_seq],
                                   chapters=[arrival, completed]))
    return result, report, character


def begin(server, conn, request):
    required = {'command','plan','outcome_seq','previous_revision','expected_world_id','expected_sequence'}
    if set(request) != required:
        raise ValueError('invalid settlement request')
    if server.job is not None or server.deployment is not None:
        raise ValueError('wait for pending mechanic work before founding a settlement')
    cave = server.shared_cave
    if not server.archive_generated_areas or cave is None or cave.identity != request['previous_revision']:
        raise ValueError('active archived area changed')
    if (request['expected_world_id'] != server.memory.world_id or type(request['expected_sequence']) is not int
            or request['expected_sequence'] != server.memory.context(server)['through']):
        raise ValueError('world changed; inspect before founding a settlement')
    seq = request['outcome_seq']
    if type(seq) is not int or not 1 <= seq <= request['expected_sequence']:
        raise ValueError('invalid outcome sequence')
    if server.db.execute('SELECT 1 FROM settlement_foundings WHERE outcome_seq=?',(seq,)).fetchone():
        raise ValueError('public outcome already founded a settlement')
    row = server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'", (seq,)).fetchone()
    if row is None or json.loads(row[0]).get('event') != 'guild_goal_completed':
        raise ValueError('settlement must cite a real public guild outcome')
    stored = server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
    if stored is None or hashlib.sha256(stored[0]).hexdigest() != cave.identity:
        raise ValueError('active area is not durably published')
    blob, report, character = compile_settlement(stored[0], request['plan'], seq, server.wilds_map)
    from .character_rebinding import prepare
    rebinding = prepare(server, cave.identity, report['revision'])
    previous = rebinding['candidate'] if rebinding else server.candidate
    inspection = server.inspect()
    inspection['module_hash'] = previous.sha256 if previous else None
    context = dict(data=inspection, recalled_history=dict(events=[dict(seq=seq, **json.loads(row[0]))]),
                   runtime=dict(previous_source=previous.source if previous else None))
    source = compile_plan(character, context)
    if len(source.encode())>262144:
        raise ValueError('settlement source exceeds mechanic size limit')
    path = server.root/'candidates'/('settlement-'+uuid.uuid4().hex+'.py')
    with path.open('x') as stream: stream.write(source)
    runtime_context = server._context(); state = deepcopy(server.module_state)
    cursor = runtime_context['interactions'][-1]['seq'] if runtime_context['interactions'] else server.interaction_cursor
    prepared = dict(request=deepcopy(request), blob=blob, report=report, character=character,
                    previous_hash=server.candidate.sha256 if server.candidate else None,
                    ids=rebinding['ids'] if rebinding else [], source_path=str(path), source_hash=hashlib.sha256(source.encode()).hexdigest())
    def stage():
        # Both calls invoke the existing kernel-sandboxed production runtime.
        candidate = server.runtime.stage(path)
        return candidate, server.runtime.run(candidate, runtime_context, state), prepared
    server.job = (server.executor.submit(stage), 'settlement', conn, cursor)


def finish(server, staged, cursor):
    candidate, result, prepared = staged
    request = prepared['request']
    if server.deployment is not None or (server.candidate.sha256 if server.candidate else None) != prepared['previous_hash']:
        raise ValueError('world mechanic changed during settlement staging')
    if candidate.sha256 != prepared['source_hash']:
        raise ValueError('settlement staged source changed')
    state_json, tiles = server._validated(result)
    resident = prepared['character']['id']
    obj = next((obj for obj in result.get('objects',[]) if obj['id']==resident), None)
    if obj != prepared['character']['chapters'][0]['object']:
        raise ValueError('staged settlement resident differs from the approved plan')
    continuation = dict(candidate=candidate, objects=result.get('objects',[]), previous_hash=prepared['previous_hash'],
                        ids=prepared['ids'], state=json.loads(state_json), tiles=tiles, cursor=cursor, clear_error=True,
                        founding=dict(outcome_seq=request['outcome_seq'],resident_id=resident,
                            offer=prepared['character']['chapters'][0]['offer']))
    revision = server._replace_cave(prepared['blob'], label=request['plan']['label'],
        previous_revision=request['previous_revision'], expected_world_id=request['expected_world_id'],
        expected_sequence=request['expected_sequence'], history_evidence=[request['outcome_seq']],
        character_continuation=continuation)
    return dict(ok=True, revision=revision, place_id=server.memory.place(revision),
                resident=resident, construction=prepared['report'], persistent=True,
                outcome_seq=request['outcome_seq'],source_path=prepared['source_path'],source_sha256=candidate.sha256)
