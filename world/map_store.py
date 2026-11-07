"""Write validated map bytes, optionally replacing a regular file atomically."""
import os,stat,tempfile
from pathlib import Path

def validate_replacement(path):
    info=Path(path).lstat()
    if not stat.S_ISREG(info.st_mode):raise ValueError('replacement target must be a regular file')

def write_map(path,data,*,replace=False):
    if type(data) is not bytes or not data:raise ValueError('map data must be nonempty bytes')
    path=Path(path)
    if not replace:
        with path.open('xb') as out:out.write(data)
        return
    validate_replacement(path)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
    finally:
        try:os.unlink(name)
        except FileNotFoundError:pass
