"""Launcher adapter for the existing version-one world-rules authority.

This module never creates rules, migrates a world, or writes its database.
Older authorities stay usable without exposing controls they cannot enforce.
"""
from .client import admin_request
from .launcher import engine_state
from .session import SessionError


def _rules(value):
    if type(value) is not dict or set(value) != {'wild_shuffle'}:
        raise ValueError('unsupported rules')
    shuffle = value['wild_shuffle']
    if (type(shuffle) is not dict or set(shuffle) != {'enabled', 'seed'}
            or type(shuffle['enabled']) is not bool
            or type(shuffle['seed']) is not int or not 1 <= shuffle['seed'] <= 20):
        raise ValueError('unsupported shuffle rules')
    return {'wild_shuffle': dict(shuffle)}


def _status(value):
    if (type(value) is not dict or value.get('ok') is not True
            or type(value.get('version')) is not int or value['version'] != 1
            or type(value.get('revision')) is not int
            or not 0 <= value['revision'] <= 2147483647):
        raise ValueError('unsupported rules response')
    return {'version': 1, 'revision': value['revision'], 'rules': _rules(value.get('rules'))}


def _owned_server(session, key):
    if session.state is not None and session.state.name == key and session.server is not None:
        server = session.server
    else:
        hosts = getattr(session, '_hosts', {})
        owned = hosts.get(key) if isinstance(hosts, dict) else None
        server = owned[0] if owned else None
    return server if server is not None and getattr(server, '_closed', True) is False else None


def options_snapshot(session, worlds):
    result = {}
    for world in worlds:
        server = _owned_server(session, world['key'])
        value = {'status': 'stopped'}
        if server is not None:
            authority = getattr(server, 'world_rules', None)
            value = {'status': 'unsupported'}
            if authority is not None:
                try:
                    with server.lock:
                        value = {'status': 'ready', **_status(authority.status()),
                                 'players': sum(not peer.get('closing') for peer in server.peers.values())}
                except (ValueError, TypeError, KeyError):
                    value = {'status': 'incompatible'}
                except Exception:
                    # Do not expose database paths or server internals to the browser.
                    value = {'status': 'error'}
        result[world['key']] = value
    return result


def replace_options(session, worlds, engine, payload):
    if (type(payload) is not dict or set(payload) != {'world', 'expected_revision', 'rules', 'confirmed'}
            or payload.get('confirmed') is not True):
        raise SessionError('Review the world options before applying them.')
    key = payload['world']
    if not isinstance(key, str) or key not in {world['key'] for world in worlds}:
        raise SessionError('Choose a local world owned by this launcher.')
    server = _owned_server(session, key)
    if server is None:
        raise SessionError('Open this local host before changing its world options.')
    revision = payload['expected_revision']
    try:
        rules = _rules(payload['rules'])
        if type(revision) is not int or not 0 <= revision < 2147483647:
            raise ValueError('invalid revision')
    except ValueError as exc:
        raise SessionError('Invalid world options. Refresh and review your changes.') from exc
    current = options_snapshot(session, [{'key': key}])[key]
    if current['status'] != 'ready':
        raise SessionError('This host does not expose compatible world options.')
    if current['revision'] != revision:
        raise SessionError('World options changed. Refresh and review your changes.')
    if current['players']:
        raise SessionError('All players must leave before changing world options.')
    if current['rules'] == rules:
        return
    # The private admin endpoint owns the atomic presence + revision check.
    # Never hold server.lock across this request: its handler needs that lock.
    request = {'command': 'world_rules', 'action': 'replace',
               'rules': rules, 'expected_revision': revision}
    try:
        response = admin_request('', request,
            admin_path=engine_state(session._world(key), engine) / 'admin.sock')
    except (OSError, ValueError) as exc:
        raise SessionError('The save could not be confirmed. Refresh world options before trying again.') from exc
    if isinstance(response, dict) and response.get('ok') is False:
        error = response.get('error')
        message = {'world rules changed; refresh and retry': 'World options changed. Refresh and review your changes.',
                   'All players must leave before changing world rules.': 'All players must leave before changing world options.'}.get(error if isinstance(error, str) else '')
        raise SessionError(message or 'The host rejected these options. Refresh before trying again.')
    try:
        saved = _status(response)
        if saved['revision'] != revision + 1 or saved['rules'] != rules:
            raise ValueError('unexpected saved rules')
    except (ValueError, TypeError) as exc:
        raise SessionError('The save could not be confirmed. Refresh world options before trying again.') from exc
