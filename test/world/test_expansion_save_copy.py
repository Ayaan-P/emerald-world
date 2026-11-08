"""Opaque Expansion save backup/import round trips. No game, sockets or accounts."""
import base64
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import zlib

from world.launcher import profile_paths
from world.offline import offline_profile
from world.save_backup import backup_save
from world.save_limits import EXPANSION_SAVE_MAX, encoded_save_limit, save_size_limit
from world.session import SessionError
from world.web_launcher import LauncherBridge, MAX_BODY


def native_save(extended=False, payload_size=1024):
    flash = bytes(range(256)) * 512
    version = 2 if extended else 1
    data = (b'PENSAV2\0' if extended else b'PENSAVE\0') + struct.pack('<5I', version, 64, 1, len(flash), zlib.crc32(flash)) + flash
    if extended:
        extension = b'EWSX0001'
        for counter in (2, 3):
            payload = bytes([counter]) * payload_size
            extension += struct.pack('<3I', counter, 1, len(payload)) + payload
        data += struct.pack('<2I', len(extension), zlib.crc32(extension)) + extension
    return data


class ExpansionSaveCopy(unittest.TestCase):
    def test_backup_and_offline_restore_preserve_both_snapshots(self):
        for data in (native_save(), native_save(True), native_save(True,8192)):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); world=root/'world'; world.mkdir(mode=0o700)
                with offline_profile(world,'May',engine='expansion-native') as p:
                    p['save'].write_bytes(data); original=p['save']
                backup=root/'backup.sav'
                backup_save(world,'May',backup,offline=True,engine='expansion-native')
                self.assertEqual(backup.read_bytes(),data); self.assertEqual(original.read_bytes(),data)
                self.assertEqual(backup.stat().st_mode & 0o777,0o600)
                with offline_profile(root/'restored','Brendan',seed_save=backup,engine='expansion-native') as p:
                    self.assertEqual(p['save'].read_bytes(),data)
                self.assertEqual(backup.read_bytes(),data)

    def test_launcher_import_and_request_envelope_preserve_all_bytes(self):
        for data in (native_save(),native_save(True),native_save(True,8192)):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as directory:
                session=Mock();session.root=Path(directory)
                bridge=LauncherBridge(session,'/nonexistent','expansion-native')
                seen={}
                def stage(*args,**kwargs):
                    p=kwargs['seed_save'];seen.update(data=p.read_bytes(),path=p,mode=p.stat().st_mode & 0o777)
                payload={'trainer':'May','seed':base64.b64encode(data).decode()}
                self.assertLessEqual(len(json.dumps({'action':'solo_new','payload':payload}).encode()),MAX_BODY)
                with patch.object(bridge,'_start_offline',side_effect=stage), patch.object(bridge,'snapshot',return_value={}):bridge.action('solo_new',payload)
                self.assertEqual(seen['data'],data);self.assertEqual(seen['mode'],0o600);self.assertFalse(seen['path'].exists())

    def test_bounds_are_engine_specific_and_overflow_is_refused(self):
        self.assertEqual(len(native_save(True,8192)),EXPANSION_SAVE_MAX)
        self.assertEqual(len(base64.b64encode(native_save(True,8192))),encoded_save_limit('expansion-native'))
        for engine in ('vanilla','expansion-native'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);session=Mock();session.root=root;bridge=LauncherBridge(session,'/nonexistent',engine)
                too_big=b'x'*(save_size_limit(engine)+1)
                with patch.object(bridge,'_start_offline') as start,self.assertRaises(SessionError):
                    bridge.action('solo_new',{'trainer':'May','seed':base64.b64encode(too_big).decode()})
                start.assert_not_called()
                with offline_profile(root/'world','May',engine=engine) as p:p['save'].write_bytes(too_big)
                with self.assertRaises(ValueError):backup_save(root/'world','May',root/'bad.sav',offline=True,engine=engine)
                self.assertFalse((root/'bad.sav').exists())
        with self.assertRaises(ValueError):save_size_limit('unknown-engine')
