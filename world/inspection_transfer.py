"""Bounded host-only inspection transfer, never a game-wire message.

Large inspections are frozen on one admin connection and read sequentially.
No single queue item/line exceeds the established 64 KiB transport limit.
"""
import base64,hashlib,json,time
MAX_BYTES=262144
CHUNK_BYTES=12000

def begin(conn,value):
    conn.pop('inspection_transfer',None)
    raw=json.dumps(value,ensure_ascii=True).encode()
    if len(raw)<=60000:return value
    if len(raw)>MAX_BYTES:raise ValueError('Inspection exceeds bounded transfer budget')
    chunks=[raw[i:i+CHUNK_BYTES] for i in range(0,len(raw),CHUNK_BYTES)]
    digest=hashlib.sha256(raw).hexdigest()
    conn['inspection_transfer']=(time.monotonic()+30,digest,chunks,1)
    return dict(ok=True,inspection_chunks=len(chunks),inspection_bytes=len(raw),digest=digest,data=base64.b64encode(chunks[0]).decode())

def next_chunk(conn,request):
    if set(request)!={'command','digest','index'} or type(request['index']) is not int:raise ValueError('Invalid inspection chunk')
    transfer=conn.get('inspection_transfer')
    if not transfer:raise ValueError('No frozen inspection on this admin connection')
    expires,digest,chunks,index=transfer
    if time.monotonic()>expires or request['digest']!=digest or request['index']!=index or index>=len(chunks):
        conn.pop('inspection_transfer',None);raise ValueError('Expired or out-of-order inspection')
    result=dict(ok=True,index=index,digest=digest,data=base64.b64encode(chunks[index]).decode())
    if index+1==len(chunks):conn.pop('inspection_transfer',None)
    else:conn['inspection_transfer']=(expires,digest,chunks,index+1)
    return result

def request(value,exchange):
    """Negotiate and finish inspection on one connection-bound exchange."""
    if value.get('command')=='inspect':
        return receive(exchange(dict(value,chunked=True)),exchange)
    return exchange(value)


def receive(first,exchange):
    if not isinstance(first,dict) or 'inspection_chunks' not in first:return first
    count=first.get('inspection_chunks');size=first.get('inspection_bytes');digest=first.get('digest')
    if (type(count) is not int or not 2<=count<=22 or type(size) is not int or not 60000<size<=MAX_BYTES
        or type(digest) is not str or len(digest)!=64):raise ValueError('Invalid inspection transfer header')
    def data(value):
        if type(value.get('data')) is not str or len(value['data'])>CHUNK_BYTES*4//3:raise ValueError('Invalid inspection chunk size')
        try:return base64.b64decode(value['data'],validate=True)
        except ValueError:raise ValueError('Invalid inspection chunk encoding') from None
    raw=bytearray(data(first))
    for index in range(1,count):
        value=exchange(dict(command='inspect_chunk',digest=digest,index=index))
        if not isinstance(value,dict) or value.get('ok') is not True or value.get('index')!=index or value.get('digest')!=digest:raise ValueError('Inspection transfer changed')
        raw.extend(data(value))
        if len(raw)>MAX_BYTES:raise ValueError('Inspection transfer exceeds budget')
    if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Inspection digest mismatch')
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError('Inspection must be an object')
    return result
