"""Durable, opt-in Luna developer GM. Intent text and world snapshots are data.

IntentQueue is safe for concurrent submitters. A runtime holds a separate flock
for its entire life. Claimed requests are never automatically replayed, even if
an author or deployment was interrupted. Operators must submit a new request ID
when they deliberately want another attempt.
"""
import fcntl
import math
import sys
import json
from pathlib import Path
import sqlite3
import time
import uuid

# The author adapter is executed by absolute filename from an isolated candidate
# directory, so locate this package without depending on inherited PYTHONPATH.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


MODEL = 'openai-codex/gpt-6-luna'


def validate_config(model, timeout, poll_interval):
    if model != MODEL:
        raise ValueError('runtime GM requires explicit model ' + MODEL)
    for name, value, limit in (('timeout', timeout, 3600), ('poll_interval', poll_interval, 3600)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= limit:
            raise ValueError(name + ' must be finite in (0,3600] seconds')


def luna_author_argv(model, timeout):
    validate_config(model, timeout, 2)
    return [sys.executable, str(Path(__file__).resolve()), 'author', '--model', model,
            '--timeout', str(timeout)]


class IntentQueue:
    def __init__(self, state_dir):
        self.root = Path(state_dir).resolve() / 'gm'
        self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'runtime.sqlite3', timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS requests (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                player TEXT NOT NULL, text TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL, created REAL NOT NULL,
                started REAL, finished REAL, result TEXT);
            CREATE TABLE IF NOT EXISTS purposes (player TEXT PRIMARY KEY, text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        (self.root / 'runtime.sqlite3').chmod(0o600)

    def close(self):
        self.db.close()

    def submit(self, player, text, request_id=None):
        if not isinstance(player, str) or not player.strip() or len(player.encode()) > 128:
            raise ValueError('player must be nonempty text <=128 UTF-8 bytes')
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > 8192:
            raise ValueError('intent must be nonempty text <=8192 UTF-8 bytes')
        request_id = uuid.uuid4().hex if request_id is None else request_id
        if not isinstance(request_id, str) or not request_id or len(request_id.encode()) > 128:
            raise ValueError('request_id must be nonempty text <=128 UTF-8 bytes')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            if row:
                if (row['player'], row['text'], row['kind']) != (player, text, 'intent'):
                    raise ValueError('request_id already belongs to a different request')
                return request_id
            self.db.execute('INSERT INTO requests(id,player,text,kind,status,created) VALUES(?,?,?,?,?,?)',
                            (request_id, player, text, 'intent', 'queued', time.time()))
            self.db.execute('INSERT OR REPLACE INTO purposes VALUES(?,?)', (player, text))
        return request_id

    def claim(self, *, min_interval=0):
        if type(min_interval) not in (int, float) or not math.isfinite(min_interval) or not 0 <= min_interval <= 3600:
            raise ValueError('min_interval must be finite in [0,3600] seconds')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute("SELECT * FROM requests WHERE status='queued' ORDER BY seq LIMIT 1").fetchone()
            if row is None:
                return None
            now = time.time()
            last = self.db.execute("SELECT value FROM metadata WHERE key='last_author'").fetchone()
            if last and now - float(last[0]) < min_interval:
                return None
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('last_author',?)", (str(now),))
            self.db.execute("UPDATE requests SET status='running',started=? WHERE id=?", (now, row['id']))
            return dict(row)

    def finish(self, identifier, status, result):
        if status not in ('succeeded', 'failed', 'interrupted'):
            raise ValueError('invalid terminal status')
        payload = json.dumps(result, allow_nan=False, sort_keys=True)
        with self.db:
            updated = self.db.execute("UPDATE requests SET status=?,finished=?,result=? WHERE id=? AND status='running'",
                                     (status, time.time(), payload, identifier))
            if updated.rowcount != 1:
                raise ValueError('request is not running')
            if (status == 'succeeded' and type(result) is dict and result.get('ok') is True
                    and type(result.get('source_path')) is str
                    and type(result.get('source_sha256')) is str):
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES('active_source',?)",
                                (json.dumps({key: result[key] for key in ('source_path', 'source_sha256')}),))

    def observe(self, inspection, *, enqueue=True):
        """Presence/position supplement to the durable native event stream.

        Ignore revisions, overlays and mechanic errors, including our own failed
        candidates, so author/deploy outcomes cannot trigger authoring loops.
        """
        from world import gm
        data = inspection.get('data', inspection)
        purposes = dict(self.db.execute('SELECT player,text FROM purposes'))
        snapshot = gm._clean({'players': [player for player in data.get('players', [])
                                           if player.get('id') in purposes],
                              'selected_players': sorted(purposes)})
        payload = json.dumps(snapshot, sort_keys=True, allow_nan=False)
        if len(payload.encode()) > gm.MAX_RESPONSE:
            raise ValueError('observation exceeds limit')
        identifier = None
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            previous = self.db.execute("SELECT value FROM metadata WHERE key='observation'").fetchone()
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('observation',?)", (payload,))
            pending = self.db.execute("SELECT id,result FROM requests WHERE kind='event' AND status='queued' ORDER BY seq LIMIT 1").fetchone()
            intent = self.db.execute("SELECT 1 FROM requests WHERE kind='intent' AND status='queued' LIMIT 1").fetchone()
            has_purpose = self.db.execute('SELECT 1 FROM purposes LIMIT 1').fetchone()
            same_selection = previous and json.loads(previous[0]).get('selected_players') == sorted(purposes)
            if enqueue and previous and same_selection and previous[0] != payload and has_purpose and not intent:
                identifier = pending['id'] if pending else uuid.uuid4().hex
                text = 'React to observed selected-player presence or position changes. Honor only selected player purposes.'
                context = json.loads(pending['result']) if pending and pending['result'] else {}
                context.setdefault('before', json.loads(previous[0]))
                context['after'] = snapshot
                if pending:
                    self.db.execute('UPDATE requests SET result=? WHERE id=?', (json.dumps(context), identifier))
                else:
                    self.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
                                    (identifier, '', text, 'event', 'queued', time.time(), json.dumps(context)))
        return identifier

    def event_cursor(self):
        row = self.db.execute("SELECT value FROM metadata WHERE key='events'").fetchone()
        return json.loads(row[0])['cursor'] if row else 0

    def observe_events(self, page, *, enqueue=True):
        """Atomically acknowledge one bounded native-event page and queue work.

        First startup drains existing history without authoring. Later pages
        coalesce into one queued request, even while another request is running.
        Only explicit-purpose players' native interactions trigger authors. The
        last 32 events and 64 terminal event requests bound retained GM history.
        """
        from world import gm
        if (type(page) is not dict or page.get('ok') is not True
                or type(page.get('events')) is not list or len(page['events']) > 64
                or type(page.get('cursor')) is not int or not 0 <= page['cursor'] <= 2**63 - 1
                or type(page.get('has_more')) is not bool):
            raise ValueError('invalid native event page')
        events = gm._clean(page['events'])
        last = -1
        for event in events:
            if (type(event) is not dict or type(event.get('seq')) is not int
                    or not last < event['seq'] <= page['cursor']
                    or type(event.get('kind')) is not str or type(event.get('data')) is not dict
                    or len(json.dumps(event, allow_nan=False).encode()) > 4096):
                raise ValueError('invalid native event')
            last = event['seq']
        identifier = None
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute("SELECT value FROM metadata WHERE key='events'").fetchone()
            previous = json.loads(row[0]) if row else {'cursor': 0, 'initialized': False}
            if page['cursor'] < previous['cursor']:
                raise ValueError('native event cursor regressed')
            purposes = dict(self.db.execute('SELECT player,text FROM purposes'))
            selected = [event for event in events if event['seq'] > previous['cursor']
                        and event['kind'] == 'interaction' and event['data'].get('player') in purposes]
            if enqueue and previous['initialized'] and selected:
                pending = self.db.execute("SELECT id,result FROM requests WHERE kind='event' AND status='queued' ORDER BY seq LIMIT 1").fetchone()
                context = json.loads(pending['result']) if pending and pending['result'] else {}
                context['events'] = (context.get('events', []) + selected)[-32:]
                context['selected_purposes'] = {event['data']['player']: purposes[event['data']['player']]
                                                for event in context['events']}
                identifier = pending['id'] if pending else uuid.uuid4().hex
                payload = json.dumps(context, allow_nan=False, sort_keys=True)
                if pending:
                    self.db.execute('UPDATE requests SET result=? WHERE id=?', (payload, identifier))
                else:
                    self.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
                                    (identifier, '', 'React to these native interactions in service of the selected player purposes.',
                                     'event', 'queued', time.time(), payload))
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('events',?)",
                            (json.dumps({'cursor': page['cursor'],
                                         'initialized': previous['initialized'] or not page['has_more']}),))
            self.db.execute("DELETE FROM requests WHERE kind='event' AND status NOT IN ('queued','running') AND seq NOT IN (SELECT seq FROM requests WHERE kind='event' AND status NOT IN ('queued','running') ORDER BY seq DESC LIMIT 64)")
        return identifier

    def set_runtime(self, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('runtime',?)", (json.dumps(value, allow_nan=False),))

    def recover(self):
        """Only call while holding the runtime lock, never from a submitter."""
        with self.db:
            result = self.db.execute("UPDATE requests SET status='interrupted',finished=?,result=? WHERE status='running'",
                                     (time.time(), json.dumps({'ok': False, 'error': 'runtime interrupted; outcome may be unknown; not replayed'})))
            return result.rowcount

    def status(self):
        rows = [dict(row) for row in self.db.execute('SELECT * FROM requests ORDER BY seq')]
        for row in rows:
            row['result'] = json.loads(row['result']) if row['result'] else None
        runtime = self.db.execute("SELECT value FROM metadata WHERE key='runtime'").fetchone()
        return {'requests': rows, 'purposes': dict(self.db.execute('SELECT player,text FROM purposes')),
                'runtime': json.loads(runtime[0]) if runtime else None}


class RuntimeGM:
    """One host-authority worker. Explicit model, no provider/model fallback.

    Use as a context manager and call step() to integrate with another loop,
    or run(stop_event) for polling. Do not call step concurrently on one object.
    """
    def __init__(self, state_dir, socket_path, *, model, timeout=120, poll_interval=2,
                 observe_events=True, min_author_interval=15):
        validate_config(model, timeout, poll_interval)
        if (type(min_author_interval) not in (int, float) or not math.isfinite(min_author_interval)
                or not 0 <= min_author_interval <= 3600):
            raise ValueError('min_author_interval must be finite in [0,3600] seconds')
        if type(observe_events) is not bool:
            raise ValueError('observe_events must be bool')
        self.root = Path(state_dir).resolve()
        self.socket_path = socket_path
        self.model, self.timeout, self.poll_interval = model, timeout, poll_interval
        self.observe_events = observe_events
        self.min_author_interval = min_author_interval
        self.queue = IntentQueue(state_dir)
        self.lock = (self.queue.root / '.runtime.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock.close()
            self.queue.close()
            raise ValueError('another runtime GM is active') from exc
        self.queue.recover()
        self.queue.set_runtime({'state': 'ready', 'model': model, 'at': time.time()})

    def close(self):
        if not self.lock.closed:
            self.queue.set_runtime({'state': 'stopped', 'model': self.model, 'at': time.time()})
            self.queue.close()
            self.lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _previous_source(self, inspection):
        """Read only a previously verified candidate matching the live hash."""
        import hashlib
        from world.mechanics import MechanicRuntime
        active = inspection.get('data', inspection).get('module_hash')
        if not active:
            return None
        stored = self.queue.db.execute("SELECT value FROM metadata WHERE key='active_source'").fetchone()
        references = [json.loads(stored[0])] if stored else []
        references.extend(row['result'] for row in reversed(self.queue.status()['requests'])
                          if row['status'] == 'succeeded' and row.get('result'))
        for result in references:
            if result.get('source_sha256') != active:
                continue
            try:
                source = MechanicRuntime(self.root)._read_source(result['source_path'])
                if hashlib.sha256(source.encode()).hexdigest() == active:
                    return source
            except (OSError, ValueError, KeyError):
                pass
        return None

    def step(self):
        from world import gm
        try:
            inspection = gm.admin_request(self.socket_path, {'command': 'inspect'}, self.timeout)
            if inspection.get('ok') is not True:
                raise ValueError('inspection rejected')
            event_page = gm.admin_request(self.socket_path,
                                          {'command': 'events_since', 'cursor': self.queue.event_cursor(), 'limit': 64},
                                          self.timeout)
            self.queue.observe_events(event_page, enqueue=self.observe_events)
            self.queue.observe(inspection, enqueue=self.observe_events)
        except (OSError, ValueError, TimeoutError) as exc:
            self.queue.set_runtime({'state': 'inspection_failed', 'model': self.model,
                                    'error': type(exc).__name__, 'at': time.time()})
            return None
        item = self.queue.claim(min_interval=self.min_author_interval)
        if item is None:
            self.queue.set_runtime({'state': 'idle', 'model': self.model, 'at': time.time()})
            return None
        self.queue.set_runtime({'state': 'authoring', 'model': self.model,
                                'request_id': item['id'], 'at': time.time()})
        try:
            runtime_context = {'request_id': item['id'], 'kind': item['kind'], 'player': item['player'],
                               'model': self.model, 'adapter': 'public_codex_exec',
                               'previous_source': self._previous_source(inspection),
                               'selected_purposes': self.queue.status()['purposes'],
                               'observed_event': json.loads(item['result']) if item['result'] else None}
            report = gm.author_and_deploy(self.root, self.socket_path, item['text'],
                                          luna_author_argv(self.model, self.timeout), self.timeout,
                                          runtime_context=runtime_context)
            report['runtime_model'] = self.model
            status = 'succeeded' if report['ok'] else 'failed'
        except Exception as exc:
            report = {'ok': False, 'error': type(exc).__name__, 'runtime_model': self.model}
            status = 'failed'
        self.queue.finish(item['id'], status, report)
        self.queue.set_runtime({'state': status, 'model': self.model,
                                'request_id': item['id'], 'at': time.time(),
                                **{key: report[key] for key in ('stage', 'error', 'report_path')
                                   if key in report}})
        return next(row for row in self.queue.status()['requests'] if row['id'] == item['id'])

    def run(self, stop_event):
        while not stop_event.is_set():
            self.step()
            stop_event.wait(self.poll_interval)


# Security configuration below is verified against this CLI's tagged source:
# core/src/tools/spec_plan.rs: add_shell_tools and add_core_utility_tools.
# apply_patch is catalog-driven, NOT controlled by features.apply_patch_freeform.
CODEX_VERSION = 'codex-cli 0.156.1'


def tool_disabled_catalog(wire):
    """Use installed, bundled public metadata. Never read auth/config ourselves."""
    catalog = json.loads(wire)
    models = [model for model in catalog['models'] if model.get('slug') == 'gpt-6-luna']
    if len(models) != 1:
        raise ValueError('installed Codex must bundle exactly one Luna model')
    model = dict(models[0], shell_type='disabled', apply_patch_tool_type=None,
                 experimental_supported_tools=[], tool_mode='direct')
    return {'models': [model]}


def codex_argv(model, catalog_path):
    """Existing public OAuth login, no shell/filesystem tools or ambient config.

    Read-only is defense in depth, not the read boundary. Shell and view_image
    are disabled and the pinned model catalog removes apply_patch authority.
    Fail closed on CLI upgrades until its tool registration is reviewed again.
    """
    validate_config(model, 120, 2)
    options = ['model_provider="openai"',
               'model_catalog_json=' + json.dumps(str(catalog_path)),
               'features.shell_tool=false', 'features.view_image=false',
               'features.multi_agent=false', 'features.multi_agent_v2=false',
               'features.js_repl=false', 'features.code_mode=false',
               'features.code_mode_host=false', 'features.plugins=false',
               'features.apps=false', 'features.browser_use=false',
               'features.computer_use=false', 'features.memories=false',
               'features.hooks=false', 'suppress_unstable_features_warning=true',
               'features.skip_host_skill_discovery=true',
               'project_doc_max_bytes=0', 'skills.include_instructions=false',
               'include_environment_context=false', 'web_search="disabled"',
               'tools.update_plan.enabled=false']
    argv = ['codex', 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral',
            '--strict-config', '--skip-git-repo-check', '--sandbox', 'read-only',
            '--model', 'gpt-6-luna', '--json']
    for option in options:
        argv.extend(['-c', option])
    return argv + ['-']


def decode_codex(wire):
    """Decode the supported Codex exec JSONL agent_message event contract."""
    messages = []
    completed = False
    for line in wire.splitlines():
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError('invalid Codex event')
        if event.get('type') in ('error', 'turn.failed'):
            raise ValueError('Codex provider call failed')
        if event.get('type') == 'turn.completed':
            completed = True
        item = event.get('item', {})
        if event.get('type') in ('item.started', 'item.completed') and isinstance(item, dict):
            if item.get('type') not in ('agent_message', 'reasoning'):
                raise ValueError('unexpected Codex author tool activity')
        if event.get('type') == 'item.completed' and isinstance(item, dict) and item.get('type') == 'agent_message':
            messages.append(item.get('text'))
    if not completed or not messages or not isinstance(messages[-1], str):
        raise ValueError('Codex did not complete an author response')
    response = json.loads(messages[-1])
    if type(response) is not dict or set(response) != {'source', 'tests'}:
        raise ValueError('Codex author must return exactly source and tests')
    return response


def main(argv=None):
    import argparse
    import signal
    import threading
    from world import gm
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    submit = sub.add_parser('submit', help='queue an intention; does not start a model')
    submit.add_argument('--state-dir', required=True)
    submit.add_argument('--player', required=True)
    submit.add_argument('--intent', required=True)
    submit.add_argument('--request-id', help='stable client idempotency key')
    status = sub.add_parser('status')
    status.add_argument('--state-dir', required=True)
    run = sub.add_parser('run', help='explicitly enable the public Luna author')
    run.add_argument('--state-dir', required=True)
    run.add_argument('--socket', required=True)
    run.add_argument('--model', required=True, choices=[MODEL])
    run.add_argument('--timeout', type=float, default=120)
    run.add_argument('--poll-interval', type=float, default=2)
    run.add_argument('--min-author-interval', type=float, default=15,
                     help='durable minimum seconds between author starts (default 15)')
    run.add_argument('--no-events', action='store_true')
    run.add_argument('--once', action='store_true')
    author = sub.add_parser('author', help='trusted Codex CLI adapter; prompt on stdin')
    author.add_argument('--model', required=True, choices=[MODEL])
    author.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args(argv)
    try:
        if args.command == 'author':
            validate_config(args.model, args.timeout, 2)
            prompt = sys.stdin.buffer.read(gm.MAX_RESPONSE + 1)
            if len(prompt) > gm.MAX_RESPONSE:
                raise ValueError('author prompt exceeds limit')
            import tempfile
            evidence = {}
            started = time.monotonic()
            def invoke(argv, text=''):
                remaining = args.timeout * .95 - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError('author deadline expired')
                return gm._run_author(argv, text, remaining, evidence, Path.cwd(),
                                      inherit_process_group=True)
            if invoke(['codex', '--version']).decode().strip() != CODEX_VERSION:
                raise ValueError('Codex version has not been security-reviewed')
            catalog = tool_disabled_catalog(invoke(['codex', 'debug', 'models', '--bundled']))
            # No credential handling. The trusted CLI retains its ordinary login.
            with tempfile.TemporaryDirectory(prefix='author-', dir=Path.cwd()) as tmp:
                catalog_path = Path(tmp) / 'catalog.json'
                gm._write(catalog_path, json.dumps(catalog))
                wire = invoke(codex_argv(args.model, catalog_path), prompt.decode())
            print(json.dumps(decode_codex(wire)))
        elif args.command in ('submit', 'status'):
            queue = IntentQueue(args.state_dir)
            try:
                if args.command == 'submit':
                    identifier = queue.submit(args.player, args.intent, args.request_id)
                    print(json.dumps({'id': identifier}))
                else:
                    print(json.dumps(queue.status(), sort_keys=True))
            finally:
                queue.close()
        else:
            stop = threading.Event()
            previous = {}
            for sig in (signal.SIGTERM, signal.SIGINT):
                previous[sig] = signal.signal(sig, lambda *_: stop.set())
            try:
                with RuntimeGM(args.state_dir, args.socket, model=args.model, timeout=args.timeout,
                               poll_interval=args.poll_interval, observe_events=not args.no_events,
                               min_author_interval=args.min_author_interval) as worker:
                    if args.once:
                        result = worker.step()
                        print(json.dumps(result, sort_keys=True))
                        if result is None:
                            return 1 if worker.queue.status()['runtime']['state'] == 'inspection_failed' else 0
                        return 1 if result['status'] != 'succeeded' else 0
                    worker.run(stop)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        return 0
    except (OSError, ValueError, TimeoutError) as exc:
        # Do not persist provider stderr, environment values, or credential errors.
        print(json.dumps({'ok': False, 'error': type(exc).__name__,
                          'detail': 'author/provider/configuration operation failed; no automatic replay'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
