"""Host-only admission policy. The game socket never exposes these actions."""


class HostControls:
    def __init__(self, database):
        self.db = database
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS host_admission (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                mode TEXT NOT NULL CHECK(mode IN ('open','locked','stopped')));
            INSERT OR IGNORE INTO host_admission VALUES(1,'open');
            CREATE TABLE IF NOT EXISTS host_removed (id TEXT PRIMARY KEY);
        ''')

    def status(self):
        return dict(ok=True, admission=self.db.execute(
            'SELECT mode FROM host_admission WHERE singleton=1').fetchone()[0],
            removed=[row[0] for row in self.db.execute('SELECT id FROM host_removed ORDER BY id')])

    def rejection(self, trainer):
        state = self.status()
        if trainer in state['removed']:
            return 'REMOVED'
        return dict(locked='LOCKED', stopped='HOST_STOPPED').get(state['admission'])

    def request(self, request, server):
        from .server import ID
        action = request.get('action')
        targeted = action in ('remove', 'allow')
        expected = {'command', 'action', 'trainer'} if targeted else {'command', 'action'}
        if (set(request) != expected or type(action) is not str
                or action not in ('status', 'lock', 'unlock', 'stop', 'split', 'remove', 'allow')):
            raise ValueError('invalid host control fields')
        targets = [request['trainer']] if action == 'remove' else list(server.peers)
        if action in ('remove', 'split') and server.link_protocol.reserved(targets):
            raise ValueError('Players are in a native activity. Finish or cancel it first.')
        if targeted:
            trainer = request['trainer']
            if type(trainer) is not str or not ID.fullmatch(trainer):
                raise ValueError('invalid trainer')
            if not self.db.execute('SELECT 1 FROM identities WHERE id=?', (trainer,)).fetchone():
                raise ValueError('unknown trainer')
            with self.db:
                if action == 'remove':
                    self.db.execute('INSERT OR IGNORE INTO host_removed VALUES(?)', (trainer,))
                else:
                    self.db.execute('DELETE FROM host_removed WHERE id=?', (trainer,))
            if action == 'remove':
                for conn in list(server.connections.values()):
                    if conn['id'] == trainer and not conn['closing']:
                        server._error(conn, 'REMOVED')
        elif action != 'status':
            with self.db:
                self.db.execute('UPDATE host_admission SET mode=? WHERE singleton=1',
                                ({'lock': 'locked', 'unlock': 'open', 'stop': 'stopped', 'split': 'stopped'}[action],))
            if action == 'split':
                for conn in list(server.connections.values()):
                    if conn['id'] is not None and not conn['closing']:
                        server._error(conn, 'HOST_SPLIT')
        return self.status()


class HostControlsPanel:
    """Host administration in the existing world window, not a second launcher."""
    def __init__(self, app):
        import tkinter as tk
        from tkinter import ttk
        self.app = app
        self.future = None
        self.after_id = None
        self.server = None
        self.page = ttk.Frame(app.notebook, padding=12)
        app.notebook.add(self.page, text='Host controls')
        self.page.columnconfigure(0, weight=1)
        self.message = tk.StringVar(value='Host a world in Play, then refresh its host controls.')
        ttk.Label(self.page, text=('Lock world and Stop hosting stop new connections without ending current games. '
            'Open world admits trainers again. Removed trainers stay blocked until you allow them. '
            'These choices survive a host restart.'), wraplength=700, justify='left').grid(row=0, sticky='w', pady=8)
        self.buttons = {}
        bar = ttk.Frame(self.page)
        bar.grid(row=1, sticky='w', pady=8)
        for action, label in (('status', 'Refresh players'), ('lock', 'Lock world'),
                              ('unlock', 'Open world'), ('stop', 'Stop hosting')):
            self._button(bar, action, label)
        self.trainer = tk.StringVar()
        ttk.Label(self.page, text='Trainer to remove or allow').grid(row=2, sticky='w')
        self.trainers = ttk.Combobox(self.page, textvariable=self.trainer, width=32, state='readonly')
        self.trainers.grid(row=3, sticky='w', pady=6)
        bar = ttk.Frame(self.page)
        bar.grid(row=4, sticky='w', pady=6)
        self._button(bar, 'remove', 'Remove player')
        self._button(bar, 'allow', 'Allow player again')
        ttk.Label(self.page, text=('Stop playing together disconnects everyone from this world. Each native game keeps running '
            'alone with its own team, bag and progress. It does not save, reload, close a game or copy a trainer. '
            'Save in your game menu as usual. Finish or cancel native battles and trades before removing or splitting players.'),
            wraplength=700, justify='left').grid(row=5, sticky='w', pady=8)
        bar = ttk.Frame(self.page)
        bar.grid(row=6, sticky='w', pady=8)
        self._button(bar, 'split', 'Stop playing together')
        ttk.Label(self.page, textvariable=self.message, wraplength=700, justify='left').grid(row=7, sticky='w', pady=8)
        self.page.bind('<Destroy>', self._destroyed, add='+')

    def _button(self, bar, action, label):
        from tkinter import ttk
        button = ttk.Button(bar, text=label, command=lambda: self.perform(action))
        button.pack(side='left', padx=3)
        self.buttons[action] = button

    def perform(self, action):
        from tkinter import messagebox
        if self.future is not None or self.app.closing:
            return
        if self.app.pending is not None:
            self.message.set('Wait for the current world operation to finish, then refresh host controls.')
            return
        server = self.app.session.server
        if server is None:
            self.message.set('Host a world in Play to use host controls. Joining does not grant host authority.')
            return
        trainer = self.trainer.get()
        if action in ('remove', 'allow') and not trainer:
            self.message.set('Refresh players and select a trainer first.')
            return
        if action in ('remove', 'split') and not messagebox.askyesno('Host controls',
                ('Disconnect ' + trainer + ' and block rejoining until allowed again?' if action == 'remove' else
                 'Disconnect everyone so each game continues alone? Save from each game menu as usual.'),
                parent=self.app.window):
            return
        # A Tk modal pumps the normal event loop. Recheck authority/lifecycle
        # ownership after confirmation, before queuing any persistent mutation.
        if (self.app.closing or self.app.pending is not None
                or self.app.session.server is not server or server.stopping.is_set()):
            self.message.set('The hosted world changed. Wait for its operation to finish, then refresh host controls.')
            return
        self.server = server
        self.future = self.app.executor.submit(self._request, server, action, trainer)
        for button in self.buttons.values():
            button.state(['disabled'])
        self.message.set('Updating host controls...')
        self.after_id = self.page.after(50, self._poll)

    @staticmethod
    def _request(server, action, trainer):
        from .client import admin_request
        request = dict(command='host_controls', action=action)
        if action in ('remove', 'allow'):
            request['trainer'] = trainer
        result = admin_request(server.socket_path, request, admin_path=server.admin_path)
        players = []
        if result.get('ok'):
            snapshot = admin_request(server.socket_path, dict(command='inspect'), admin_path=server.admin_path)
            players = [player['id'] for player in snapshot.get('players', [])]
        return result, players

    def _poll(self):
        self.after_id = None
        if not self.future.done():
            self.after_id = self.page.after(50, self._poll)
            return
        try:
            result, players = self.future.result()
            if self.app.session.server is not self.server:
                self.message.set('The hosted world changed. Refresh its host controls.')
            elif not result.get('ok'):
                # Only fixed host-policy errors are returned, not diagnostics.
                self.message.set('Could not apply host control. Finish or cancel native activities, then refresh and retry.')
            else:
                self.trainers['values'] = sorted(set(players) | set(result['removed']))
                if self.trainer.get() not in self.trainers['values']:
                    self.trainer.set('')
                self.message.set('World admission is ' + result['admission'] + '.\nConnected trainers: '
                    + (', '.join(players) or 'none') + '.\nRemoved trainers: '
                    + (', '.join(result['removed']) or 'none') + '.')
        except Exception:
            self.message.set('Host controls unavailable. Check that this world is still hosted, then refresh.')
        self.future = None
        for button in self.buttons.values():
            button.state(['!disabled'])

    def _destroyed(self, event):
        if event.widget is self.page and self.after_id is not None:
            self.page.after_cancel(self.after_id)
            self.after_id = None
