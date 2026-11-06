"""Publish an owner-authorized, durable walkable terrain overlay."""
import argparse,json
from pathlib import Path
from .client import admin_request

def publish(admin_socket,identity,tiles):
    return admin_request('',{'command':'set_shared_terrain','identity':identity,'tiles':tiles},admin_path=admin_socket)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--admin-socket',required=True,type=Path);p.add_argument('--area',required=True);p.add_argument('--tiles-file',required=True,type=Path);a=p.parse_args(argv)
    with a.tiles_file.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('tile input too large')
    try:tiles=json.loads(data.decode('utf-8'))
    except (ValueError,UnicodeError):p.error('tile input must be JSON')
    result=publish(a.admin_socket,a.area,tiles);print(json.dumps(result,sort_keys=True));return 0 if result.get('ok') is True else 1
if __name__=='__main__':raise SystemExit(main())
