"""Compile a small authored cast into one normal atomic mechanic publication."""
from copy import deepcopy
import hashlib
from .character_chapters import compile_plan, validate_plan
from .mechanics import validate_objects


def compile_ensemble(plans, context):
    if type(plans) is not list or not 2<=len(plans)<=4:
        raise ValueError('an ensemble needs two to four character plans')
    plans=[validate_plan(plan) for plan in plans]
    identities=[plan['id'] for plan in plans]
    if len(set(identities))!=len(identities):raise ValueError('ensemble identities must be distinct')
    work=deepcopy(context);data=work.get('data',work)
    state=data.get('state',{})
    if type(state) is not dict:raise ValueError('ensemble requires object-shaped world state')
    existing=state.get('world_characters',{})
    if len(existing)+len(plans)>8:raise ValueError('ensemble exceeds persistent character capacity')
    objects=data.get('objects',[])
    if set(identities)&({o['id'] for o in objects}|set(existing)):
        raise ValueError('ensemble cannot replace an existing character or object')
    # Reserve capacity for away residents too, so the initial empty scene cannot
    # promise a gathering that exceeds the authority's native object budget.
    if len({o['id'] for o in objects}|set(existing)|set(identities))>8:
        raise ValueError('ensemble exceeds shared object capacity')
    initial=[plan['chapters'][0]['object'] for plan in plans if plan['chapters'][0]['status']=='active']
    validate_objects(objects+initial)
    for plan in plans:
        source=compile_plan(plan,work)
        data['module_hash']=hashlib.sha256(source.encode()).hexdigest()
        work.setdefault('runtime',{})['previous_source']=source
    return source


def contract():
    return dict(response='{"character_ensemble": [plans], "tests": "Python tests"}',
                purpose='a caravan, research party or other small cast whose public-history chapters make a shared scene',
                limits='two to four new distinct chapter plans; existing and proposed residents together at most eight; reserve slots even for away characters',
                behavior='each resident uses the existing chapter contract, including public milestones and optional guide service; matching triggers can coordinate arrivals, relocation and departure',
                publication='one compiled source and one sandbox deployment; joint geometry, actor collisions and history are validated atomically, so failure cannot publish half a gathering',
                preservation='wraps the exact inspected source; never replaces existing actor identities; no rewards or native engine changes',
                tests='assert full top-level visible cast, empty-world behavior, coordinated transitions, unrelated actor preservation and restart state')
