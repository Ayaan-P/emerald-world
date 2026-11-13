"""Revise real native encounter tables without moving geometry or faking ecology."""
import hashlib,json
from .shared_cave import SharedCave
from .offline_cave import PROFILES
from .species_cohort import catalogue

SUPPORTED=(1,2,3,4,5,10,11)

def active(server):
    cave=server.shared_cave
    if not server.persist_generated_cave or not server.archive_generated_areas or not cave or cave.version not in SUPPORTED:
        raise ValueError('Use a durable active shared 31/63 cave, not outdoor or opened immutable region publication')
    saved=server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
    archive=server.db.execute('SELECT label,template FROM generated_area_archive WHERE identity=?',(cave.identity,)).fetchone()
    if not saved or not archive or saved[0]!=archive[1] or hashlib.sha256(saved[0]).hexdigest()!=cave.identity:
        raise ValueError('Durable habitat revision unavailable')
    if server.db.execute('SELECT 1 FROM world_region_revisions WHERE revision=?',(cave.identity,)).fetchone():
        raise ValueError('Opened regions are immutable; do not revise their population through the shared slot')
    return cave,archive[0]


def inspect(server,actor,row,args):
    if args:raise ValueError('Habitat inspection takes no arguments')
    cave,label=active(server)
    slots=[]
    if cave.wildlife:
        names={value:key for key,value in catalogue(cave.cohort).items()}
        for i in range(12):
            off=1+3*i;number=int.from_bytes(cave.wildlife[off:off+2],'little')
            slots.append(dict(species=names[number],level=cave.wildlife[off+2]))
    return dict(outcome='native_habitat_inspected',revision=cave.identity,place_id=server.memory.place(cave.identity),label=label,side=cave.side,
        profile=next((k for k,v in PROFILES.items() if v==cave.profile),None),cohort=cave.cohort,
        rate=cave.wildlife[0] if cave.wildlife else None,slots=slots,
        basis='public_authority_encounter_configuration',limits='Configured native land encounter slots, not sightings, living population counts, caught Pokemon or proven migration. Existing encounter probabilities/terrain checks remain native.')


def revise(server,actor,row,args):
    from .actor_runtime import Committed,_receipt
    from .character_rebinding import prepare
    if set(args)!={'observation','profile','rate','slots'} or type(args['observation']) is not int or type(args['slots']) is not str or len(args['slots'])>650:
        raise ValueError('Supply own habitat inspection, profile, native rate and bounded twelve-slot JSON')
    proof=server.db.execute("SELECT data FROM events WHERE seq=? AND kind='world_memory'",(args['observation'],)).fetchone()
    if not proof:raise ValueError('Actual habitat inspection required')
    event=json.loads(proof[0]);observation=event.get('result',{})
    if (event.get('event')!='actor_tool_result' or event.get('source')!='authority_capability_runtime' or event.get('character_id')!=actor
            or event.get('tool')!='world.inspect_habitat' or event.get('status')!='succeeded' or type(observation) is not dict):
        raise ValueError('Use this actor successful authority habitat inspection')
    cave,label=active(server)
    if observation.get('revision')!=cave.identity:raise ValueError('Habitat changed; inspect the current revision')
    if observation['profile'] is not None and args['profile']!=observation['profile']:
        raise ValueError('Preserve the existing native cave profile while revising wildlife')
    try:slots=json.loads(args['slots'])
    except ValueError:raise ValueError('Invalid population JSON') from None
    if type(slots) is not list or len(slots)!=12 or any(type(s) is not list or len(s)!=2 for s in slots):
        raise ValueError('Use exactly twelve [enabled Expansion species name,level] slots')
    slots=[dict(species=s[0],level=s[1]) for s in slots]
    if cave.side==31:
        from .offline_cave import encode_wildlife
    else:
        from .large_cave import encode_wildlife
    proposal=dict(rows=[r.decode('ascii') for r in cave._rows],spawn=[1,1],exit=[cave.side-2,cave.side-2])
    blob=encode_wildlife(proposal,args['profile'],args['rate'],slots,cohort='expansion-native');candidate=SharedCave(blob)
    if candidate._rows!=cave._rows:raise ValueError('Population revision must preserve exact geometry')
    if candidate.identity==cave.identity:return dict(outcome='habitat_population_unchanged',revision=cave.identity,place_id=observation['place_id'])
    continuation=prepare(server,cave.identity,candidate.identity)
    execution=getattr(server,'actor_tool_execution',None)
    if not execution or execution[0]!=actor:raise ValueError('Durable capability executor required')
    _,record,plan,step=execution;committed=[]
    result=dict(outcome='native_habitat_population_revised',previous_revision=cave.identity,revision=candidate.identity,
        profile=args['profile'],rate=args['rate'],slots=slots,side=cave.side,required_client_capability='CAVE10',observation=args['observation'])
    def persist(identity,place):
        if identity!=candidate.identity:raise ValueError('Unexpected habitat revision')
        result['place_id']=place
        server.memory.append('habitat_population_revised',dict(character_id=actor,place_id=place,previous_revision=cave.identity,revision=identity,
            before=dict(cohort=observation['cohort'],rate=observation['rate'],slots=observation['slots']),
            after=dict(cohort='expansion-native',profile=args['profile'],rate=args['rate'],slots=slots),
            history_evidence=list(row['evidence']),basis='committed_native_encounter_table',limits='Authored encounter configuration, not simulated ecology, migration, catches or victories.'))
        committed.append(_receipt(server,actor,record,plan,step,'succeeded',result))
    server._replace_cave(blob,label=label,previous_revision=cave.identity,expected_world_id=server.memory.world_id,
        expected_sequence=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0],history_evidence=list(row['evidence']),
        character_continuation=continuation,actor_tool_commit=persist)
    return Committed(committed[0],result)
