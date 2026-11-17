"""NPC fieldwork: measured access geometry along a completed authority journey.

This does not simulate sightings, resources, battles or canonical NPC movement.
"""
import hashlib
import re


def validate(route):
    if 'survey' not in route:return
    if type(route['survey']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,48}",route['survey']):
        raise ValueError('field survey needs a bounded literal public title')


def commit(server,identity,control,arrival_seq):
    from .shared_cave import SharedCave
    route=control['journey'];revision=control['object']['region_revision']
    row=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
    if row is None or hashlib.sha256(row[0]).hexdigest()!=revision:
        raise ValueError('field survey lost its exact archived geometry')
    cave=SharedCave(row[0])
    # The caller only invokes this after every route segment has committed.
    # Measure the immutable map, not claimed observations supplied by an author.
    samples=[]
    for x,y in route['path']:
        if not cave.walkable(x,y):raise ValueError('field survey route is not walkable')
        exits=sum(1<<i for i,(dx,dy) in enumerate(((0,-1),(1,0),(0,1),(-1,0))) if cave.walkable(x+dx,y+dy))
        samples.append([x,y,exits])
    place=server.memory.place(revision)
    server.revision=server.memory.append('character_field_report',dict(
        character_id=identity,character_name=control['character']['name'],title=route['survey'],
        journey=route['id'],arrival_receipt=arrival_seq,revision=revision,place_id=place,places=[place] if place else [],
        samples=samples,exit_bits=['north','east','south','west'],
        junctions=[[x,y] for x,y,mask in samples if mask.bit_count()>=3],
        dead_ends=[[x,y] for x,y,mask in samples if mask.bit_count()==1],
        publication='public_world_character_fieldwork',basis='completed_authority_route_and_archived_geometry',
        limits='Static walkable access only. No wildlife sightings, resources, player visits, native rendering or original story NPC travel is inferred.'))


def observed(event,revisions):
    return (event.get('event')=='character_field_report'
            and event.get('publication')=='public_world_character_fieldwork'
            and event.get('basis')=='completed_authority_route_and_archived_geometry'
            and event.get('revision') in revisions)
