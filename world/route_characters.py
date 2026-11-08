"""Bind authored character chapters to actual route landmarks, without publishing."""
from copy import deepcopy
from .shared_cave import SharedCave
from .build_catalog import catalog_maps
from .character_chapters import validate_plan


def bind_landmarks(character_plan, blob, route_report, chapter_landmarks):
    """Return a normal character_plan with exact generated geometry scope.

    Inputs remain authored proposals. This does not infer achievements, call a
    model, activate a destination, or bypass mechanic staging/authority checks.
    """
    cave=SharedCave(blob)
    if cave.version!=16 or type(route_report) is not dict or route_report.get('revision')!=cave.identity:
        raise ValueError('route report must match the exact XL template')
    if type(chapter_landmarks) is not dict or any(type(v) is not str for v in chapter_landmarks.values()):
        raise ValueError('chapter landmark bindings must be an object')
    sites={site['id']:site for site in route_report.get('landmarks',[]) if type(site) is dict and type(site.get('id')) is str}
    maps=[key for key,value in catalog_maps().items() if value['name']=='GeneratedWorld_Wilds']
    if len(maps)!=1:raise ValueError('generated wilds map unavailable')
    result=deepcopy(character_plan)
    active={chapter['id'] for chapter in result['chapters'] if chapter['status']=='active'}
    if set(chapter_landmarks)!=active:
        raise ValueError('bind every active chapter and no absent chapter')
    for chapter in result['chapters']:
        if chapter['status']!='active':continue
        site=sites.get(chapter_landmarks[chapter['id']])
        if site is None or site['id'] in ('entry','exit') or not cave.walkable(site.get('x'),site.get('y')):
            raise ValueError('character landmark must be a walkable named clearing')
        chapter['object'].update(group=maps[0][0],num=maps[0][1],x=site['x'],y=site['y'],region_revision=cave.identity)
    return validate_plan(result)
