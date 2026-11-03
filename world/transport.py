"""Restricted game-socket brokers, outside the game's networkless sandbox.

TLS carries EWTR1 followed by uint32 big-endian lengths and game bytes. A zero
length is directional EOF, not a TCP shutdown: TLS has no TCP-style half close.
Only these brokers speak framing. The native Unix protocol remains unchanged.
Pin mode trusts exactly the SHA256 of the DER leaf certificate, not its issuer,
name or expiry. Obtain pins over an authenticated independent channel. CA mode
checks chain, expiry and hostname. Neither mode sends game data before trust.
Keep the host private key OUTSIDE every game-visible transport directory.
"""
import argparse
import hashlib
import hmac
import math
import os
from pathlib import Path
import re
import select
import socket
import ssl
import struct
import threading
import time

MAGIC = b'EWTR1'
CHUNK = 16384


def _relay(local, remote, stop, timeout, limit):
    """One bounded, nonblocking duplex pump per admitted connection."""
    local.setblocking(False)
    remote.setblocking(False)
    wire = bytearray()
    incoming = bytearray()
    output = bytearray()
    local_eof = remote_eof = write_closed = False
    last = time.monotonic()
    while not stop.is_set():
        if remote_eof and not output and not write_closed:
            local.shutdown(socket.SHUT_WR)
            write_closed = True
        if local_eof and remote_eof and not wire and not output:
            return
        if time.monotonic() - last > timeout:
            raise TimeoutError('idle transport')
        readers = []
        if not local_eof and len(wire) <= limit - CHUNK - 4:
            readers.append(local)
        if not remote_eof and len(incoming) + len(output) < limit:
            readers.append(remote)
        writers = ([remote] if wire else []) + ([local] if output else [])
        readable, writable, _ = select.select(readers, writers, [], 0.05)
        if remote in readers and remote.pending():
            readable = list(set(readable + [remote]))
        for sock in readable:
            try:
                capacity = CHUNK if sock is local else min(CHUNK, limit - len(incoming) - len(output))
                data = sock.recv(capacity)
            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):
                continue
            if sock is local:
                wire.extend(struct.pack('!I', len(data)))
                wire.extend(data)
                if not data:
                    local_eof = True
            else:
                if not data:
                    if not remote_eof or incoming:
                        raise ValueError('truncated transport')
                    return
                incoming.extend(data)
                while len(incoming) >= 4:
                    size = struct.unpack('!I', incoming[:4])[0]
                    if size > CHUNK or remote_eof:
                        raise ValueError('invalid transport frame')
                    if len(incoming) < size + 4:
                        break
                    output.extend(incoming[4:4+size])
                    del incoming[:4+size]
                    if size == 0:
                        remote_eof = True
            last = time.monotonic()
        for sock in writable:
            buf = wire if sock is remote else output
            try:
                count = sock.send(buf)
            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):
                continue
            if not count:
                raise ConnectionError('closed transport')
            del buf[:count]
            last = time.monotonic()


def _magic(sock):
    sock.sendall(MAGIC)
    received = bytearray()
    while len(received) < len(MAGIC):
        data = sock.recv(len(MAGIC) - len(received))
        if not data:
            raise ValueError('missing transport preface')
        received.extend(data)
    if received != MAGIC:
        raise ValueError('invalid transport preface')


class _Broker:
    def __init__(self, max_clients=8, timeout=30, handshake_timeout=5, buffer_limit=65536):
        if type(max_clients) is not int or not 1 <= max_clients <= 8:
            raise ValueError('max_clients must be between 1 and 8')
        if any(not math.isfinite(n) or n <= 0 for n in (timeout, handshake_timeout)):
            raise ValueError('timeouts must be finite and positive')
        if type(buffer_limit) is not int or not CHUNK + 4 <= buffer_limit <= 1048576:
            raise ValueError('invalid buffer limit')
        self.max_clients, self.timeout = max_clients, timeout
        self.handshake_timeout, self.buffer_limit = handshake_timeout, buffer_limit
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._workers = set()
        self._sockets = set()
        self._listener = self._thread = None
        self._inode = None

    @property
    def active_clients(self):
        with self._lock:
            return len(self._workers)

    def _track(self, sock):
        with self._lock:
            if self._stop.is_set():
                sock.close()
                raise ConnectionError('broker stopped')
            self._sockets.add(sock)
        return sock

    def _start(self, listener):
        self._listener = listener
        listener.settimeout(0.1)
        self._thread = threading.Thread(target=self._accept, name='world-transport-listener', daemon=True)
        self._thread.start()
        return self

    def _accept(self):
        while not self._stop.is_set():
            try:
                sock, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                if len(self._workers) >= self.max_clients or self._stop.is_set():
                    sock.close()
                    continue
                thread = threading.Thread(target=self._worker, args=(sock,),
                                          name='world-transport-client', daemon=True)
                self._workers.add(thread)
                self._sockets.add(sock)
            thread.start()

    def _worker(self, sock):
        owned = [sock]
        try:
            local, remote = self._pair(sock, owned)
            _relay(local, remote, self._stop, self.timeout, self.buffer_limit)
        except (OSError, ValueError):
            # Never log untrusted bytes, trainer tokens, keys or certificate data.
            pass
        finally:
            with self._lock:
                for connection in owned:
                    self._sockets.discard(connection)
                    connection.close()
                self._workers.discard(threading.current_thread())

    def _tls(self, sock, context, owned, **kwargs):
        sock.settimeout(self.handshake_timeout)
        wrapped = context.wrap_socket(sock, do_handshake_on_connect=False, **kwargs)
        owned.append(wrapped)
        self._track(wrapped)
        wrapped.do_handshake()
        return wrapped

    def close(self):
        self._stop.set()
        if self._listener is not None:
            self._listener.close()
        if self._thread is not None:
            self._thread.join()
        with self._lock:
            connections, workers = list(self._sockets), list(self._workers)
        for sock in connections:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        for worker in workers:
            worker.join()
        if self._inode is not None:
            path = Path(self.socket_path)
            try:
                info = path.lstat()
                if (info.st_dev, info.st_ino) == self._inode:
                    path.unlink()
            except FileNotFoundError:
                pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


class HostBroker(_Broker):
    """TLS listener with exactly one fixed public Unix destination.

    Linux O_PATH and /proc/self/fd are required to pin the existing socket inode.
    Start WorldServer first and restart this broker after replacing its socket.
    The destination must be transport/world.sock, never the private admin socket.
    Explicit listen=(LAN_ADDRESS, PORT) opens LAN access. Default is loopback.
    """
    def __init__(self, game_socket, cert, key, listen=('127.0.0.1', 0), **limits):
        super().__init__(**limits)
        path = Path(game_socket).absolute()
        if path.name != 'world.sock' or path.parent.name != 'transport' or path.resolve() != path:
            raise ValueError('destination must be non-symlink transport/world.sock')
        self.game_socket = str(path)
        for secret in (cert, key):
            if Path(secret).resolve().is_relative_to(path.parent.resolve()):
                raise ValueError('TLS files must be outside the game transport directory')
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(str(cert), str(key))
        # Pin the socket inode, not just its pathname. Linux O_PATH plus procfs
        # makes connect immune to a symlink/rename race with the private admin.
        self._target_fd = os.open(self.game_socket, os.O_PATH | os.O_NOFOLLOW)
        info = os.fstat(self._target_fd)
        import stat
        if not stat.S_ISSOCK(info.st_mode):
            os.close(self._target_fd)
            self._target_fd = None
            raise ValueError('public destination is not a socket')
        self._target_inode = (info.st_dev, info.st_ino)
        self.listen = listen
        self.address = None

    def start(self):
        if self._listener is not None or self._stop.is_set():
            raise RuntimeError('broker cannot be restarted')
        family = socket.AF_INET6 if ':' in self.listen[0] else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(self.listen)
            listener.listen(self.max_clients)
            self.address = listener.getsockname()[:2]
            return self._start(listener)
        except BaseException:
            listener.close()
            raise

    def _pair(self, sock, owned):
        remote = self._tls(sock, self.context, owned, server_side=True)
        _magic(remote)
        local = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        owned.append(local)
        self._track(local)
        local.settimeout(self.handshake_timeout)
        info = os.lstat(self.game_socket)
        if (info.st_dev, info.st_ino) != self._target_inode:
            raise ValueError('public game socket replaced; restart broker')
        local.connect('/proc/self/fd/' + str(self._target_fd))
        return local, remote

    def close(self):
        super().close()
        if self._target_fd is not None:
            os.close(self._target_fd)
            self._target_fd = None


class ClientBroker(_Broker):
    """Local private Unix endpoint connected to a fixed, authenticated TLS host.

    Exactly one of fingerprint (64 hex SHA256 leaf DER) or cafile is required.
    CA mode verifies server_hostname, defaulting to remote host. Pin mode does
    not use PKI validation; the supplied pin IS the trust anchor.
    """
    def __init__(self, socket_path, remote, *, fingerprint=None, cafile=None,
                 server_hostname=None, **limits):
        super().__init__(**limits)
        if (fingerprint is None) == (cafile is None):
            raise ValueError('provide exactly one fingerprint or CA file')
        if fingerprint is not None and not re.fullmatch('[0-9a-fA-F]{64}', fingerprint):
            raise ValueError('fingerprint must be exactly 64 hexadecimal characters')
        self.fingerprint = fingerprint.lower() if fingerprint is not None else None
        self.socket_path, self.remote = str(socket_path), remote
        self.server_hostname = server_hostname or remote[0]
        if fingerprint is not None:
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.context.check_hostname = False
            self.context.verify_mode = ssl.CERT_NONE
        else:
            self.context = ssl.create_default_context(cafile=str(cafile))
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2

    def start(self):
        if self._listener is not None or self._stop.is_set():
            raise RuntimeError('broker cannot be restarted')
        path = Path(self.socket_path)
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # Never remove or replace somebody else's existing path, even stale.
            listener.bind(self.socket_path)
            info = path.lstat()
            self._inode = (info.st_dev, info.st_ino)
            path.chmod(0o600)
            listener.listen(self.max_clients)
            return self._start(listener)
        except BaseException:
            listener.close()
            self.close()
            raise

    def _pair(self, local, owned):
        # Numeric/hostname remote is operator configuration, never game input.
        raw = socket.create_connection(self.remote, timeout=self.handshake_timeout)
        owned.append(raw)
        self._track(raw)
        remote = self._tls(raw, self.context, owned, server_hostname=self.server_hostname)
        if self.fingerprint is not None:
            actual = hashlib.sha256(remote.getpeercert(binary_form=True)).hexdigest()
            if not hmac.compare_digest(actual, self.fingerprint):
                raise ssl.SSLCertVerificationError('server certificate fingerprint mismatch')
        _magic(remote)
        return local, remote


def _endpoint(value):
    try:
        host, port = value.rsplit(':', 1)
        host = host.removeprefix('[').removesuffix(']')
        if not host or not 0 <= int(port) <= 65535:
            raise ValueError
        return host, int(port)
    except ValueError:
        raise argparse.ArgumentTypeError('expected HOST:PORT') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve')
    serve.add_argument('--listen', type=_endpoint, default=('127.0.0.1', 8765))
    serve.add_argument('--game-socket', required=True)
    serve.add_argument('--cert', required=True)
    serve.add_argument('--key', required=True)
    connect = commands.add_parser('connect')
    connect.add_argument('--remote', required=True, type=_endpoint)
    connect.add_argument('--socket', required=True)
    trust = connect.add_mutually_exclusive_group(required=True)
    trust.add_argument('--fingerprint')
    trust.add_argument('--ca-file')
    connect.add_argument('--server-name')
    for command in (serve, connect):
        command.add_argument('--max-clients', type=int, default=8)
        command.add_argument('--timeout', type=float, default=30)
        command.add_argument('--handshake-timeout', type=float, default=5)
        command.add_argument('--buffer-limit', type=int, default=65536)
    args = parser.parse_args(argv)
    limits = dict(max_clients=args.max_clients, timeout=args.timeout,
                  handshake_timeout=args.handshake_timeout, buffer_limit=args.buffer_limit)
    import signal
    def terminate(signum, frame):
        raise KeyboardInterrupt
    previous_handler = signal.signal(signal.SIGTERM, terminate)
    try:
        if args.command == 'serve':
            broker = HostBroker(args.game_socket, args.cert, args.key, args.listen, **limits)
        else:
            broker = ClientBroker(args.socket, args.remote, fingerprint=args.fingerprint,
                                  cafile=args.ca_file, server_hostname=args.server_name, **limits)
        with broker:
            while broker._thread.is_alive():
                broker._thread.join(0.5)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError):
        # Do not emit paths, private material or network-supplied exception text.
        parser.exit(1, 'transport: configuration or listener failure\n')
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
