"""Local-owner UI adapter for DesktopSession's existing TLS invitation flow."""
import ipaddress
import json
from pathlib import Path
import re
import tempfile

from .session import SessionError
from .transport import read_invitation, validate_invitation


def _host(session, world):
    if session.state is not None and session.state.name == world and session.server is not None:
        return session.server, session.broker, session.sharing_pin, True
    hosts = getattr(session, '_hosts', {})
    owned = hosts.get(world) if isinstance(hosts, dict) else None
    return (*owned, False) if owned else (None, None, None, False)


def sharing_snapshot(session, worlds):
    result = {}
    for world in worlds:
        server, broker, pin, selected = _host(session, world['key'])
        running = server is not None and getattr(server, '_closed', True) is False
        value = {'running': running, 'selected': selected, 'configured': broker is not None, 'listening': False}
        if running and broker is not None:
            try:
                value['listening'] = not broker._stop.is_set() and broker._thread is not None and broker._thread.is_alive()
                host, port = broker.address
                if isinstance(host, str) and type(port) is int and 1 <= port <= 65535:
                    value['endpoint'] = {'host': host, 'port': port}
                if isinstance(pin, str) and re.fullmatch(r'[0-9a-fA-F]{64}', pin):
                    value['pin'] = pin.lower()
            except (AttributeError, ValueError, TypeError):
                value['listening'] = False
        result[world['key']] = value
    return result


def _selected(session, worlds, payload, fields):
    if type(payload) is not dict or set(payload) != fields or payload.get('confirmed') is not True:
        raise SessionError('Review the local sharing action before continuing.')
    world = payload.get('world')
    if not isinstance(world, str) or world not in {item['key'] for item in worlds}:
        raise SessionError('Choose a local world owned by this launcher.')
    server, _, _, selected = _host(session, world)
    if not selected or server is None or getattr(server, '_closed', True) is not False:
        raise SessionError('Open this local host before managing its invitations.')
    return server


def start_sharing(session, worlds, payload):
    _selected(session, worlds, payload, {'world', 'listen_host', 'port', 'confirmed'})
    if session.broker is not None:
        raise SessionError('A listener is already configured. Refresh before changing sharing.')
    host, port = payload['listen_host'], payload['port']
    try:
        address = ipaddress.ip_address(host) if isinstance(host, str) and '%' not in host else None
    except ValueError:
        address = None
    effective = getattr(address, 'ipv4_mapped', None) or address
    if effective is None or effective.is_multicast or type(port) is not int or not 1 <= port <= 65535:
        raise SessionError('Enter a numeric listen address and a port from 1 to 65535.')
    try:
        cert, key = session.tls_material()
        session.share(cert, key, (str(address), port))
    except (OSError, ValueError) as exc:
        raise SessionError('Sharing could not start. Check the listen address, port and world TLS identity. OpenSSL is needed to create an identity. Refresh before trying again.') from exc


def stop_sharing(session, worlds, payload):
    _selected(session, worlds, payload, {'world', 'confirmed'})
    if session.broker is None:
        raise SessionError('There is no sharing listener to stop. Refresh the world.')
    # Close only this selected owner's TLS broker. Its world authority, local
    # game and detached worlds remain alive. Existing remote transports close.
    try:
        session.broker.close()
    except (OSError, ValueError) as exc:
        raise SessionError('Sharing shutdown could not be confirmed. Refresh before trying again.') from exc
    session.broker = None
    session.sharing_pin = None
    session.status = 'Local sharing stopped. The local world is still running.'


def export_friend(session, worlds, payload):
    server = _selected(session, worlds, payload,
                       {'world', 'trainer', 'host', 'port', 'existing', 'confirmed', 'reviewed_pin', 'reviewed_listener'})
    state = sharing_snapshot(session, [{'key': payload['world']}])[payload['world']]
    if not state['listening'] or 'pin' not in state or 'endpoint' not in state:
        raise SessionError('Enable a working local sharing listener first.')
    if payload['reviewed_pin'] != state['pin'] or payload['reviewed_listener'] != state['endpoint']:
        raise SessionError('Local sharing changed. Refresh and review the invitation again.')
    trainer, host, port, existing = payload['trainer'], payload['host'], payload['port'], payload['existing']
    if type(existing) is not bool:
        raise SessionError('Choose a new or existing friend trainer.')
    try:
        validate_invitation({'version': 1, 'trainer': trainer, 'token': '0' * 64,
                             'endpoint': {'host': host, 'port': port}, 'pin': state['pin']})
    except (ValueError, TypeError):
        raise SessionError('Enter a valid trainer, reachable host address and port.') from None
    if trainer == session.remote_trainer:
        raise SessionError('Choose a separate friend trainer, not your selected trainer.')
    listen = ipaddress.ip_address(state['endpoint']['host'])
    try:
        advertised = ipaddress.ip_address(host)
    except ValueError:
        advertised = None
    effective_listen = getattr(listen, 'ipv4_mapped', None) or listen
    effective_advertised = getattr(advertised, 'ipv4_mapped', None) or advertised
    if effective_listen.is_loopback and (effective_advertised is None or not effective_advertised.is_loopback):
        raise SessionError('This listener is only on this computer. Use a local-network listen address for remote friends.')
    if advertised is not None and advertised.version != listen.version:
        raise SessionError('The invitation and listener must use the same IP version.')
    with server.lock:
        found = server.db.execute('SELECT 1 FROM identities WHERE id=?', (trainer,)).fetchone() is not None
        if found != existing:
            raise SessionError('That trainer already exists. Review an existing-trainer invitation instead.' if found
                               else 'That trainer does not exist. Review a new-trainer invitation instead.')
        # The session reuses an existing identity only after the explicit
        # existing-trainer review. Never silently re-export someone else's token.
        try:
            with tempfile.TemporaryDirectory(prefix='emerald-local-invite-') as directory:
                target = Path(directory) / 'invitation.json'
                session.export_invitation(trainer, target, (host, port))
                invitation = read_invitation(target)
                if (invitation.get('trainer') != trainer or invitation.get('pin', '').lower() != state['pin']
                        or invitation.get('endpoint') != {'host': host, 'port': port}):
                    raise ValueError('unexpected invitation')
                return json.dumps(invitation)
        except (OSError, ValueError) as exc:
            raise SessionError('The invitation could not be confirmed. The trainer may exist now. Refresh, then review an existing-trainer invitation if needed.') from exc
