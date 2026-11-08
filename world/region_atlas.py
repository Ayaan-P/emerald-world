"""Publish a generated atlas into the existing independent destination menu.

An atlas is a bounded set of immutable plain-cave destinations, not seamless
geography. Publication never activates the shared slot or moves a player.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from .cave_blueprint import proposal_from_blueprint
from .shared_cave import SharedCave
from scripts.export_generated_cave import encode

MAX_INPUT=65536


def compile_atlas(plan):
    if type(plan) is not dict or set(plan)!={'title','regions'}:
        raise ValueError('atlas requires title and regions')
    def label(value):
        if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,'!?-]{0,19}",value):
            raise ValueError('atlas and region labels need 1..20 plain ASCII characters')
    label(plan['title'])
    regions=plan['regions']
    if type(regions) is not list or not 2<=len(regions)<=8:
        raise ValueError('atlas needs 2..8 destinations')
    serialized=json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(serialized.encode())>MAX_INPUT:raise ValueError('atlas plan too large')
    compiled=[];names=set();revisions=set()
    for entry in regions:
        if type(entry) is not dict or set(entry)!={'label','blueprint'}:raise ValueError('invalid atlas destination')
        label(entry['label'])
        blob=encode(proposal_from_blueprint(entry['blueprint']))
        cave=SharedCave(blob)
        if cave.version!=1:raise ValueError('atlas requires REGION1 plain-cave geometry')
        if entry['label'].lower() in names or cave.identity in revisions:
            raise ValueError('atlas destinations need distinct labels and geometry')
        names.add(entry['label'].lower());revisions.add(cave.identity)
        compiled.append(dict(label=entry['label'],revision=cave.identity,blob=blob,
                             walkable_tiles=sum(cave.walkable(x,y) for x in range(31) for y in range(31))))
    return serialized,compiled


def publish(server,request):
    if (type(request) is not dict or set(request)!={'command','plan','expected_world_id','expected_sequence'}
            or request['command'] not in ('preview_atlas','publish_atlas')):
        raise ValueError('invalid atlas request')
    serialized,compiled=compile_atlas(request['plan'])
    identity=hashlib.sha256(serialized.encode()).hexdigest()
    with server.lock:
        if not server.archive_generated_areas or request['expected_world_id']!=server.memory.world_id:
            raise ValueError('persistent matching world required')
        existing=server.db.execute('SELECT plan,result FROM world_region_atlases WHERE identity=?',(identity,)).fetchone()
        if existing:
            if existing[0]!=serialized:raise ValueError('atlas identity conflict')
            result=json.loads(existing[1])
            if len(result['regions'])!=len(compiled):raise ValueError('published atlas manifest differs')
            for item,region in zip(compiled,result['regions']):
                row=server.db.execute('''SELECT a.template,r.revision FROM generated_area_archive a
                    JOIN world_region_revisions r ON r.revision=a.identity WHERE r.place_id=?''',(region['place_id'],)).fetchone()
                if row!=(item['blob'],item['revision']):raise ValueError('published atlas no longer matches its archived destinations')
            return dict(result,applied=False,already_published=True)
        if (type(request['expected_sequence']) is not int or request['expected_sequence']!=
                server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]):
            raise ValueError('world changed; preview this atlas again')
        report=[]
        for item in compiled:
            collision=server.db.execute('SELECT identity FROM generated_area_archive WHERE label=? COLLATE NOCASE AND identity!=?',(item['label'],item['revision'])).fetchone()
            if collision:raise ValueError('destination label already belongs to another map')
            row=server.db.execute('SELECT template,label FROM generated_area_archive WHERE identity=?',(item['revision'],)).fetchone()
            if row and row!=(item['blob'],item['label']):raise ValueError('existing destination differs; atlas will not rename or replace it')
            place=server.db.execute('SELECT place_id FROM world_places WHERE revision=?',(item['revision'],)).fetchone()
            pin=server.db.execute('SELECT revision FROM world_region_revisions WHERE place_id=?',(place[0],)).fetchone() if place else None
            if pin and pin[0]!=item['revision']:raise ValueError('destination place already pins another revision')
            report.append({k:item[k] for k in ('label','revision','walkable_tiles')})
        result=dict(ok=True,atlas_id=identity,title=request['plan']['title'],regions=report,
                    format='REGION1 plain caves',travel='Select a destination outside generated areas, then enter normally.')
        if request['command']=='preview_atlas':return dict(result,applied=False)
        try:
            with server.db:
                for item,region in zip(compiled,report):
                    server.db.execute('INSERT OR IGNORE INTO generated_area_archive VALUES (?,?,?,?,?)',
                                      (item['revision'],item['label'],'cave',item['blob'],int(time.time())))
                    place=server.memory.place(item['revision']);region['place_id']=place
                    inserted=server.db.execute('INSERT OR IGNORE INTO world_region_revisions VALUES (?,?)',(place,item['revision'])).rowcount
                    if inserted:
                        server.memory.append('region_opened',dict(place_id=place,revision=item['revision'],label=item['label'],
                                                                 atlas_id=identity,atlas_title=request['plan']['title']))
                server.db.execute('INSERT INTO world_region_atlases VALUES (?,?,?)',(identity,serialized,json.dumps(result,sort_keys=True)))
        except sqlite3.Error as exc:
            raise ValueError('atlas publication failed; no destinations were added') from exc
        server.revision=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
        return dict(result,applied=True)


def main(argv=None):
    from .client import admin_request
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path);parser.add_argument('--admin-socket',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(argv)
    try:
        with args.plan.open('rb') as stream:raw=stream.read(MAX_INPUT+1)
        if len(raw)>MAX_INPUT:raise ValueError('atlas plan too large')
        plan=json.loads(raw);compile_atlas(plan)
        def call(request):
            result=admin_request('',request,admin_path=args.admin_socket)
            if not result.get('ok'):raise ValueError(result.get('error','atlas request refused'))
            return result
        memory=call(dict(command='inspect'))['world_memory']
        result=call(dict(command='publish_atlas' if args.apply else 'preview_atlas',plan=plan,
                         expected_world_id=memory['world_id'],expected_sequence=memory['through']))
        print(json.dumps(result,indent=2))
    except (ValueError,TypeError,KeyError,OSError) as exc:parser.exit(1,str(exc)+'\n')
    return 0

if __name__=='__main__':main()
