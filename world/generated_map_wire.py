"""Bounded, transactional wire framing for generated-map blueprints.

No sockets, authentication, authorization or gameplay side effects live here.
Integrators must bind transfers to an authenticated world session and must not
apply content until the complete message is validated and safely admitted.
"""
import base64
import binascii
import json

from .generated_map_store import MAX_DOCUMENT_BYTES, StoreError, _checked

CHUNK_BYTES=384
MAX_FRAME=768
MAX_CHUNKS=(MAX_DOCUMENT_BYTES+CHUNK_BYTES-1)//CHUNK_BYTES


class TransferError(ValueError):
    pass


def _id_valid(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def encode_transfer(kind,document):
    """Return deterministic, bounded ASCII frames for a validated document."""
    try: identifier,text=_checked(kind,document)
    except StoreError as error: raise TransferError('invalid map') from error
    raw=text.encode('ascii')
    chunks=[raw[i:i+CHUNK_BYTES] for i in range(0,len(raw),CHUNK_BYTES)]
    if not chunks or len(chunks)>MAX_CHUNKS: raise TransferError('invalid transfer length')
    frames=[f'GENMAP1 BEGIN {identifier} {kind} {len(raw)} {len(chunks)}']
    frames.extend(f'GENMAP1 CHUNK {identifier} {i} {base64.b64encode(chunk).decode("ascii")}' for i,chunk in enumerate(chunks))
    frames.append(f'GENMAP1 END {identifier}')
    if any(len(line)>MAX_FRAME for line in frames): raise TransferError('frame exceeds limit')
    return frames


def _decimal(value, upper):
    if not value or len(value)>6 or not value.isascii() or not value.isdecimal() or (len(value)>1 and value[0]=='0'):
        raise TransferError('invalid number')
    n=int(value)
    if n>upper: raise TransferError('number out of range')
    return n


class Assembler:
    """Assemble at most one transfer; return a document only after full validation."""
    def __init__(self): self.abort()
    def abort(self): self._transfer=None
    @property
    def in_progress(self): return self._transfer is not None

    def feed(self,line):
        if type(line) is not str or len(line)>MAX_FRAME or not line.isascii() or '\n' in line or '\r' in line:
            raise TransferError('invalid frame')
        fields=line.split(' ')
        if len(fields)<3 or fields[0]!='GENMAP1' or not _id_valid(fields[2]):
            raise TransferError('invalid frame header')
        op,identifier=fields[1],fields[2]
        if op=='BEGIN':
            if len(fields)!=6 or fields[3] not in ('seeded','proposal'):
                raise TransferError('invalid begin')
            size=_decimal(fields[4],MAX_DOCUMENT_BYTES);count=_decimal(fields[5],MAX_CHUNKS)
            if not size or count!=(size+CHUNK_BYTES-1)//CHUNK_BYTES:
                raise TransferError('invalid transfer dimensions')
            data={'id':identifier,'kind':fields[3],'size':size,'count':count,'chunks':{}}
            if self._transfer:
                existing=self._transfer
                if any(existing[k]!=data[k] for k in ('id','kind','size','count')):
                    raise TransferError('another transfer is active')
                return None
            self._transfer=data
            return None
        transfer=self._transfer
        if not transfer or transfer['id']!=identifier:
            raise TransferError('no matching transfer')
        if op=='CHUNK':
            if len(fields)!=5: raise TransferError('invalid chunk')
            index=_decimal(fields[3],transfer['count']-1)
            try: chunk=base64.b64decode(fields[4],validate=True)
            except (ValueError,binascii.Error): raise TransferError('invalid chunk encoding') from None
            expected=CHUNK_BYTES if index<transfer['count']-1 else transfer['size']-CHUNK_BYTES*(transfer['count']-1)
            if len(chunk)!=expected or base64.b64encode(chunk).decode('ascii')!=fields[4]:
                raise TransferError('invalid chunk length or encoding')
            previous=transfer['chunks'].get(index)
            if previous is not None and previous!=chunk:
                self.abort();raise TransferError('conflicting duplicate chunk')
            transfer['chunks'][index]=chunk
            return None
        if op=='END':
            if len(fields)!=3: raise TransferError('invalid end')
            if len(transfer['chunks'])!=transfer['count']:
                raise TransferError('transfer is incomplete')
            raw=b''.join(transfer['chunks'][i] for i in range(transfer['count']))
            # No partial data survives an invalid or complete transfer.
            self.abort()
            try:
                text=raw.decode('ascii')
                document=json.loads(text)
                actual,canonical=_checked(transfer['kind'],document)
            except (UnicodeDecodeError,ValueError,TypeError,RecursionError,StoreError):
                raise TransferError('map content is invalid') from None
            if actual!=identifier or canonical!=text:
                raise TransferError('map content does not match transfer')
            return transfer['kind'],document
        raise TransferError('unknown frame operation')


class LineDecoder:
    """Incrementally split a bounded byte stream without exposing partial frames."""
    def __init__(self): self._pending=b''
    def feed(self,data):
        if type(data) is not bytes or len(data)>8192:
            raise TransferError('invalid input chunk')
        data=self._pending+data
        pieces=data.split(b'\n')
        pending=pieces.pop()
        if len(pending)>MAX_FRAME or any(len(piece)>MAX_FRAME or b'\r' in piece for piece in pieces):
            self._pending=b''
            raise TransferError('oversized or invalid line')
        try: lines=[piece.decode('ascii') for piece in pieces]
        except UnicodeDecodeError:
            self._pending=b''
            raise TransferError('non-ASCII line') from None
        self._pending=pending
        return lines
    def finish(self):
        if self._pending:
            self._pending=b''
            raise TransferError('truncated frame')
