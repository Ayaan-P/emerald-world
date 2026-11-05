import base64
import copy
import json
import random
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from world import procedural_map as pm
from world import generated_map_wire as wire


def plan(seed=1):
    return {'schema':1,'seed':seed,'width':31,'height':25,'rooms':3,'room_size':5,'biome':'forest','points':['landmark','encounter']}

class WireTests(unittest.TestCase):
    def test_roundtrip_out_of_order_and_duplicate_chunks(self):
        doc=pm.generate(plan());frames=wire.encode_transfer('seeded',doc)
        self.assertTrue(all(len(x)<=wire.MAX_FRAME for x in frames))
        receiver=wire.Assembler();self.assertIsNone(receiver.feed(frames[0]))
        chunks=frames[1:-1];random.Random(7).shuffle(chunks)
        for chunk in chunks:self.assertIsNone(receiver.feed(chunk))
        self.assertIsNone(receiver.feed(chunks[0]))
        self.assertEqual(receiver.feed(frames[-1]),('seeded',doc));self.assertFalse(receiver.in_progress)
        with self.assertRaises(wire.TransferError):receiver.feed(frames[-1])
    def test_proposal_roundtrip(self):
        r=pm.generate(plan());p=pm.accept_proposal({k:r[k] for k in ('rows','spawn','exit','points')}|{'schema':1,'biome':'cave'})
        frames=wire.encode_transfer('proposal',p);a=wire.Assembler();result=None
        for frame in frames:result=a.feed(frame)
        self.assertEqual(result,('proposal',p))
    def test_incomplete_does_not_publish_and_can_resume(self):
        d=pm.generate(plan());f=wire.encode_transfer('seeded',d);a=wire.Assembler();a.feed(f[0]);a.feed(f[1])
        with self.assertRaisesRegex(wire.TransferError,'incomplete'):a.feed(f[-1])
        self.assertTrue(a.in_progress)
        for x in f[2:-1]:a.feed(x)
        self.assertEqual(a.feed(f[-1]),('seeded',d))
    def test_conflicting_chunk_aborts_and_never_returns_partial(self):
        f=wire.encode_transfer('seeded',pm.generate(plan()));a=wire.Assembler();a.feed(f[0]);a.feed(f[1])
        parts=f[1].split(' ');raw=bytearray(base64.b64decode(parts[-1]));raw[0]^=1;parts[-1]=base64.b64encode(raw).decode()
        with self.assertRaisesRegex(wire.TransferError,'conflicting'):a.feed(' '.join(parts))
        self.assertFalse(a.in_progress)
        with self.assertRaises(wire.TransferError):a.feed(f[-1])
    def test_corrupt_content_rejected_even_if_well_formed_frames(self):
        f=wire.encode_transfer('seeded',pm.generate(plan()));a=wire.Assembler();a.feed(f[0])
        parts=f[1].split(' ');raw=bytearray(base64.b64decode(parts[-1]));raw[10]^=1;parts[-1]=base64.b64encode(raw).decode();f[1]=' '.join(parts)
        for x in f[1:-1]:a.feed(x)
        with self.assertRaises(wire.TransferError):a.feed(f[-1])
        self.assertFalse(a.in_progress)
    def test_wrong_identity_and_limits_do_not_displace_valid_transfer(self):
        f=wire.encode_transfer('seeded',pm.generate(plan()));other=wire.encode_transfer('seeded',pm.generate(plan(2)));a=wire.Assembler();a.feed(f[0])
        with self.assertRaises(wire.TransferError):a.feed(other[0])
        with self.assertRaises(wire.TransferError):a.feed(other[1])
        with self.assertRaises(wire.TransferError):a.feed('X'*769)
        self.assertTrue(a.in_progress)
        for x in f[1:-1]:a.feed(x)
        self.assertEqual(a.feed(f[-1])[1]['sha256'],pm.generate(plan())['sha256'])
    def test_invalid_dimensions_chunk_indices_and_noncanonical_numbers(self):
        doc=pm.generate(plan());f=wire.encode_transfer('seeded',doc);a=wire.Assembler();parts=f[0].split(' ')
        for change in ('0','100001','01'):
            p=parts.copy();p[4]=change
            with self.subTest(change=change),self.assertRaises(wire.TransferError):a.feed(' '.join(p))
        a.feed(f[0]);parts=f[1].split(' ');parts[3]='999999'
        with self.assertRaises(wire.TransferError):a.feed(' '.join(parts))
        parts=f[1].split(' ');parts[-1]='!!!'
        with self.assertRaises(wire.TransferError):a.feed(' '.join(parts))
    def test_encoder_never_serializes_unvalidated_data(self):
        doc=pm.generate(plan());doc['rows'][0]='.'*31
        with self.assertRaises(wire.TransferError):wire.encode_transfer('seeded',doc)


class SocketTransferTests(unittest.TestCase):
    def test_two_disposable_clients_receive_and_persist_same_blueprint(self):
        import socket,sqlite3,threading
        from world.generated_map_store import GeneratedMapStore
        document=pm.generate(plan(987));frames=wire.encode_transfer('seeded',document)
        payload=('\n'.join(frames)+'\n').encode('ascii');received=[];errors=[]
        def client(sock):
            try:
                db=sqlite3.connect(':memory:');store=GeneratedMapStore(db);decoder=wire.LineDecoder();assembler=wire.Assembler();found=[]
                while True:
                    block=sock.recv(97)
                    if not block:break
                    for frame in decoder.feed(block):
                        value=assembler.feed(frame)
                        if value is not None:found.append(store.publish(*value))
                decoder.finish()
                if assembler.in_progress:raise AssertionError('partial transfer remained')
                self.assertEqual(found,[document['sha256']])
                self.assertEqual(store.get(found[0]),('seeded',document))
                received.append(found[0]);db.close()
            except BaseException as error:errors.append(error)
            finally:sock.close()
        pairs=[socket.socketpair() for _ in range(2)]
        threads=[threading.Thread(target=client,args=(peer,)) for _,peer in pairs]
        for thread in threads:thread.start()
        for sender,_ in pairs:
            for i in range(0,len(payload),53):sender.sendall(payload[i:i+53])
            sender.shutdown(socket.SHUT_WR);sender.close()
        for thread in threads:thread.join(timeout=5)
        self.assertFalse(any(t.is_alive() for t in threads));self.assertEqual(errors,[])
        self.assertEqual(received,[document['sha256']]*2)

    def test_line_decoder_rejects_overlong_truncated_and_binary(self):
        d=wire.LineDecoder();self.assertEqual(d.feed(b'abc'),[]);self.assertEqual(d.feed(b'd\ne\n'),['abcd','e']);d.finish()
        d=wire.LineDecoder();d.feed(b'partial')
        with self.assertRaises(wire.TransferError):d.finish()
        with self.assertRaises(wire.TransferError):d.feed(b'x'*(wire.MAX_FRAME+1))
        with self.assertRaises(wire.TransferError):d.feed(b'\xff\n')

if __name__=='__main__':unittest.main()
