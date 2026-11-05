"""API-immutable SQLite storage for validated generated-map blueprints.

This is not a multiplayer protocol or native map loader. The caller supplies
its own SQLite connection and controls any surrounding transaction. No game
saves, generated code or external services are touched by this module.
"""
import json
import sqlite3

from .procedural_map import PlanError, accept_proposal, validate_generated

MAX_MAPS = 256
MAX_DOCUMENT_BYTES = 100_000
TABLE = 'generated_map_blueprints_v1'


class StoreError(ValueError):
    pass


def _canonical(document):
    try:
        encoded=json.dumps(document,sort_keys=True,separators=(',', ':'),ensure_ascii=True).encode('ascii')
    except (ValueError,TypeError,RecursionError,OverflowError) as error:
        raise StoreError('document cannot be encoded') from error
    if len(encoded)>MAX_DOCUMENT_BYTES:
        raise StoreError('document exceeds size limit')
    return encoded.decode('ascii')


def _checked(kind, document):
    try:
        if kind == 'seeded':
            validate_generated(document)
        elif kind == 'proposal':
            if type(document) is not dict or 'sha256' not in document:
                raise PlanError('invalid proposal envelope')
            candidate=accept_proposal({k:v for k,v in document.items() if k!='sha256'})
            if candidate != document:
                raise PlanError('proposal hash or content does not match')
        else:
            raise PlanError('unsupported generated map kind')
        text=_canonical(document)
        return document['sha256'],text
    except (PlanError,KeyError,TypeError) as error:
        raise StoreError('invalid generated map') from error


class GeneratedMapStore:
    def __init__(self, connection):
        if not isinstance(connection,sqlite3.Connection):
            raise TypeError('connection must be sqlite3.Connection')
        self.db=connection
        self.db.execute(f'''CREATE TABLE IF NOT EXISTS {TABLE} (
            id TEXT PRIMARY KEY NOT NULL CHECK(length(id)=64),
            kind TEXT NOT NULL CHECK(kind IN ('seeded','proposal')),
            document TEXT NOT NULL CHECK(length(document)<={MAX_DOCUMENT_BYTES})
        )''')

    def publish(self, kind, document):
        """Add a validated immutable blueprint, or return its existing ID.

        Atomic capacity check and insertion are a single SQLite statement. If
        a caller has an outer transaction, this method does not commit it.
        """
        identifier,text=_checked(kind,document)
        self.db.execute(f'''INSERT INTO {TABLE} (id,kind,document)
            SELECT ?,?,? WHERE (SELECT count(*) FROM {TABLE}) < ?
            ON CONFLICT(id) DO NOTHING''',(identifier,kind,text,MAX_MAPS))
        row=self.db.execute(f'SELECT kind,document FROM {TABLE} WHERE id=?',(identifier,)).fetchone()
        if row is None:
            raise StoreError('generated map capacity reached')
        if tuple(row) != (kind,text):
            raise StoreError('existing map ID has different content')
        return identifier

    def get(self, identifier):
        if type(identifier) is not str or len(identifier)!=64 or any(c not in '0123456789abcdef' for c in identifier):
            raise StoreError('invalid map ID')
        row=self.db.execute(f'SELECT kind,document FROM {TABLE} WHERE id=?',(identifier,)).fetchone()
        if row is None:
            return None
        kind,text=row
        if type(text) is not str or len(text.encode('utf-8')) > MAX_DOCUMENT_BYTES:
            raise StoreError('stored map is invalid')
        try:
            document=json.loads(text)
            actual,canonical=_checked(kind,document)
        except (ValueError,TypeError,RecursionError) as error:
            raise StoreError('stored map is invalid') from error
        if actual!=identifier or canonical!=text:
            raise StoreError('stored map failed integrity check')
        return kind,document
