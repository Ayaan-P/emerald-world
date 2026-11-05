"""Explicit local-host authoring, using mocked model and authority only."""
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock,patch
from world.session import DesktopSession,DesktopApp,SessionError
from world import cave_blueprint,large_cave,wilds
from test_large_generated_cave import DOC
from test_shared_generated_cave import MemoryAuthority
from world.shared_cave import SharedCave

class FakeServer:
    def __init__(self):
        self._closed=False;self.cave_map=(99,0);self.wilds_map=(99,1);self.lock=threading.RLock();self.peers={}
        self.persist_generated_cave=False;self._replace_cave=Mock(return_value='id')

class HostCaveAuthoring(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.session=DesktopSession(Path(self.temp.name).resolve());self.session.state=Path(self.temp.name).resolve()/'world';self.server=FakeServer();self.session.server=self.server
        self.proposal=cave_blueprint.proposal_from_blueprint(DOC,side=63)
        self.blob=large_cave.encode_wildlife(self.proposal,'ice',20,[{'species':'MAGIKARP','level':5}]*12)

    def test_local_host_explicitly_authors_and_publishes(self):
        with patch('world.author_cave.author',return_value=(self.proposal,self.blob)) as author:
            self.assertEqual(self.session.author_shared_cave('an icy cave'),'id')
            author.assert_called_once_with('an icy cave',large=True,custom_wildlife=True)
            self.server._replace_cave.assert_called_once_with(self.blob,label='an icy cave')
            self.assertIn('host session',self.session.status)

    def test_actual_in_memory_owner_authority_installs_generated_map(self):
        root=Path(self.temp.name);server=MemoryAuthority(root/'socket',root/'world')
        self.session.server=server;self.session.state=root/'world'
        try:
            with patch('world.author_cave.author',return_value=(self.proposal,self.blob)):
                self.assertEqual(self.session.author_shared_cave('icy cave'),SharedCave(self.blob).identity)
            self.assertEqual(server.shared_cave.identity,SharedCave(self.blob).identity)
        finally:server.close()

    def test_host_authors_outdoor_area_into_real_authority(self):
        root=Path(self.temp.name);server=MemoryAuthority(root/'socket',root/'world',persist_generated_cave=True)
        self.session.server=server;self.session.state=root/'world';blob=wilds.encode(self.proposal)
        try:
            with patch('world.author_cave.author',return_value=(self.proposal,blob)) as author:
                self.assertEqual(self.session.author_shared_cave('islands',wilds=True),SharedCave(blob).identity)
                author.assert_called_once_with('islands',large=True,wilds=True)
            self.assertEqual(server.shared_cave.version,6);self.assertIn('outdoor area',self.session.status)
        finally:server.close()

    def test_missing_host_and_occupied_cave_do_not_call_model(self):
        with patch('world.author_cave.author') as author:
            self.session.server=None
            with self.assertRaises(SessionError):self.session.author_shared_cave('cave')
            self.session.server=self.server;self.server.peers={'trainer':{'state':[99,0,3,4]}}
            with self.assertRaises(SessionError):self.session.author_shared_cave('cave')
            self.server.peers={'trainer':{'state':[99,1,3,4]}}
            with self.assertRaises(SessionError):self.session.author_shared_cave('cave')
            with self.assertRaises(SessionError):self.session.author_shared_cave('')
            author.assert_not_called();self.server._replace_cave.assert_not_called()

    def test_world_changed_or_occupied_after_model_never_publishes(self):
        def change(*args,**kwargs):self.session.server=None;return self.proposal,self.blob
        with patch('world.author_cave.author',side_effect=change):
            with self.assertRaises(SessionError):self.session.author_shared_cave('cave')
        self.server._replace_cave.assert_not_called()
        self.session.server=self.server;self.server._replace_cave.side_effect=ValueError('occupied')
        with patch('world.author_cave.author',return_value=(self.proposal,self.blob)):
            with self.assertRaises(SessionError) as error:self.session.author_shared_cave('cave')
        self.assertNotIn('occupied',str(error.exception).lower())

    def test_queued_activation_rejects_changed_host(self):
        old=self.session.server;state=self.session.state;self.session.server=FakeServer()
        with self.assertRaises(SessionError):
            self.session.activate_generated_area('a'*64,expected_server=old,expected_state=state)

    def test_ui_saved_area_confirmation_and_submission(self):
        app=object.__new__(DesktopApp);app.pending=None;app.closing=False;app.session=self.session;app.window=object()
        app.message=Mock();app.executor=Mock();app._set_busy=Mock();identity='a'*64
        app.generated_area_ids={'islands ['+identity+']':identity};app.generated_area_owner=(self.session.server,self.session.state);app.values=Mock(return_value={'generated_area':'islands ['+identity+']'})
        fake_tk=types.ModuleType('tkinter');fake_tk.messagebox=types.SimpleNamespace(askyesno=Mock(return_value=False))
        with patch.dict('sys.modules',{'tkinter':fake_tk}):
            app.generated_area_owner=(object(),self.session.state)
            app.submit(app.activate_generated_area);app.executor.submit.assert_not_called();fake_tk.messagebox.askyesno.assert_not_called()
            app.generated_area_owner=(self.session.server,self.session.state)
            app.submit(app.activate_generated_area);app.executor.submit.assert_not_called()
            fake_tk.messagebox.askyesno.return_value=True;app.submit(app.activate_generated_area)
            app.executor.submit.assert_called_once_with(self.session.activate_generated_area,identity,expected_server=self.session.server,expected_state=self.session.state)
            self.assertEqual(app.pending_kind,'activate_generated_area')
            app.pending=None;app.executor.submit.reset_mock();app.submit(app.refresh_generated_areas)
            app.executor.submit.assert_called_once_with(self.session.list_generated_areas)

    def test_ui_confirmation_and_background_submission(self):
        app=object.__new__(DesktopApp);app.pending=None;app.closing=False;app.session=self.session;app.window=object()
        app.message=Mock();app.executor=Mock();app._set_busy=Mock();app.values=Mock(return_value={'cave_theme':'icy cave'})
        # The UI-only operation is a marker; submit owns the actual work.
        fake_tk=types.ModuleType('tkinter');fake_tk.messagebox=types.SimpleNamespace(askyesno=Mock(return_value=False))
        with patch.dict('sys.modules',{'tkinter':fake_tk}):
            app.submit(app.generate_cave)
            fake_tk.messagebox.askyesno.assert_called_once();app.executor.submit.assert_not_called()
            fake_tk.messagebox.askyesno.return_value=True
            app.submit(app.generate_cave)
            app.executor.submit.assert_called_once_with(self.session.author_shared_cave,'icy cave')
            self.assertEqual(app.pending_kind,'author_cave');app._set_busy.assert_called_once_with(True)
            app.pending=None;app.executor.submit.reset_mock();app._set_busy.reset_mock()
            app.submit(app.generate_wilds)
            app.executor.submit.assert_called_once_with(self.session.author_shared_cave,'icy cave',wilds=True)
