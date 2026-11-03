"""A host must reject incomplete source deployments before accepting players."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from world.server import WorldServer


class HostStartup(unittest.TestCase):
    def test_missing_map_catalog_fails_before_database_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'world'
            with patch('world.build_catalog.catalog_maps', side_effect=FileNotFoundError('missing catalog')):
                with self.assertRaises(FileNotFoundError):
                    WorldServer(state/'transport/world.sock', state)
            self.assertFalse((state/'world.sqlite3').exists())

    def test_valid_catalog_allows_host_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'world'
            server = WorldServer(state/'transport/world.sock', state)
            try:
                server.start()
                self.assertTrue(Path(server.socket_path).is_socket())
            finally:
                server.close()
