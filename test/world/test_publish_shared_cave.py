"""The local publication tool sends only validated inert geometry to admin."""
from pathlib import Path
from unittest.mock import patch
import base64,tempfile,unittest
from world.publish_cave import publish
from world.shared_cave import SharedCave
ROWS=['#'*31]+['#'+'.'*29+'#']*29+['#'*31]
BLOB=b'EWGMAP01'+''.join(ROWS).encode('ascii')
class PublishCave(unittest.TestCase):
 def test_validated_template_to_explicit_local_admin(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'cave.bin';path.write_bytes(BLOB);identity=SharedCave(BLOB).identity
   with patch('world.publish_cave.admin_request',return_value={'ok':True,'id':identity,'persistent':False}) as request:
    self.assertEqual(publish(path,Path(d)/'admin.sock'),identity)
    args,kwargs=request.call_args;self.assertEqual(args[0],'');self.assertEqual(args[1]['command'],'replace_cave')
    self.assertEqual(base64.b64decode(args[1]['template']),BLOB);self.assertEqual(kwargs['admin_path'],Path(d)/'admin.sock')
 def test_bad_input_and_false_acceptance_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'cave.bin';path.write_bytes(b'bad')
   with patch('world.publish_cave.admin_request') as request:
    with self.assertRaises(ValueError):publish(path,Path(d)/'admin.sock')
    request.assert_not_called()
   path.write_bytes(BLOB)
   with patch('world.publish_cave.admin_request',return_value={'ok':True,'id':'wrong','persistent':False}):
    with self.assertRaises(ValueError):publish(path,Path(d)/'admin.sock')
if __name__=='__main__':unittest.main()
