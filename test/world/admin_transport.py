"""In-memory admin wire adapter using the production inspection exchange.

Only socket I/O is replaced. Requests still pass through the real authority,
its bounded JSON frames, frozen connection state and asynchronous job polling.
"""
import json
import time
from world.inspection_transfer import request as transfer_request


def admin_request(server, request, timeout=15):
    conn = dict(id=None, out=bytearray(), closing=False, sock=object(), admin=True)
    server.connections[conn['sock']] = conn
    deadline = time.monotonic() + timeout
    try:
        def exchange(value):
            if conn['closing']:
                raise ConnectionResetError('authority closed the admin connection')
            conn['out'].clear()
            server._admin_line(conn, json.dumps(value, allow_nan=False).encode())
            while not conn['out']:
                if time.monotonic() >= deadline:
                    raise TimeoutError('admin response timeout')
                server._poll_mechanics()
                time.sleep(.01)
            raw = bytes(conn['out'])
            if not raw.endswith(b'\n') or len(raw) > 65536:
                raise ValueError('invalid admin response')
            return json.loads(raw)
        return transfer_request(request, exchange)
    finally:
        server.connections.pop(conn['sock'], None)
