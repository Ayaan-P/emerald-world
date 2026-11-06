"""Publish an owner-authorized, durable walkable terrain overlay."""
import argparse,base64,json
from pathlib import Path
from .client import admin_request

def publish(admin_socket,identity,tiles):
    return admin_request('',{'command':'set_shared_terrain','identity':identity,'tiles':tiles},admin_path=admin_socket)

def publish_geometry(admin_socket,identity,tiles,replace=False):
    if type(tiles) is not list or len(tiles)>512 or type(replace) is not bool:raise ValueError('invalid geometry patch')
    if len(tiles)<=64:return admin_request('',{'command':'set_shared_geometry','identity':identity,'tiles':tiles,'replace':replace},admin_path=admin_socket)
    kinds={'grass':0,'tall_grass':1,'water':2,'original':3};data=bytearray(len(tiles).to_bytes(2,'little'))
    for tile in tiles:
        if type(tile) is not dict or set(tile)!={'x','y','terrain'} or type(tile['x']) is not int or type(tile['y']) is not int or not 0<=tile['x']<127 or not 0<=tile['y']<127 or type(tile['terrain']) is not str or tile['terrain'] not in kinds:raise ValueError('invalid geometry patch')
        data.extend((tile['x'],tile['y'],kinds[tile['terrain']]))
    return admin_request('',{'command':'set_shared_geometry_compact','identity':identity,'data':base64.b64encode(data).decode('ascii'),'replace':replace},admin_path=admin_socket)

def inspect(admin_socket,identity):
    return admin_request('',{'command':'inspect_shared_terrain','identity':identity},admin_path=admin_socket)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admin-socket',required=True,type=Path);p.add_argument('--area',required=True);p.add_argument('--tiles-file',type=Path);p.add_argument('--inspect',action='store_true');p.add_argument('--geometry',action='store_true');p.add_argument('--replace',action='store_true');a=p.parse_args(argv)
    if (a.tiles_file is None)==(not a.inspect):p.error('choose exactly one of --tiles-file or --inspect')
    if a.inspect and a.geometry:p.error('--geometry cannot be combined with --inspect')
    if a.replace and not a.geometry:p.error('--replace requires --geometry')
    if a.inspect:
        result=inspect(a.admin_socket,a.area);print(json.dumps(result,sort_keys=True));return 0 if result.get('ok') is True else 1
    with a.tiles_file.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('tile input too large')
    try:tiles=json.loads(data.decode('utf-8'))
    except (ValueError,UnicodeError):p.error('tile input must be JSON')
    result=publish_geometry(a.admin_socket,a.area,tiles,a.replace) if a.geometry else publish(a.admin_socket,a.area,tiles);print(json.dumps(result,sort_keys=True));return 0 if result.get('ok') is True else 1
if __name__=='__main__':raise SystemExit(main())
