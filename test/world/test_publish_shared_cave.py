"""The local publication tool sends only validated inert geometry to admin."""
from pathlib import Path
from unittest.mock import patch
import base64,json,tempfile,unittest
from world.publish_cave import publish, publish_blueprint
from world.cave_blueprint import proposal_from_blueprint
from scripts.export_generated_cave import encode
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
 def test_persistent_acceptance_is_valid(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'cave.bin';path.write_bytes(BLOB);identity=SharedCave(BLOB).identity
   with patch('world.publish_cave.admin_request',return_value={'ok':True,'id':identity,'persistent':True}):
    self.assertEqual(publish(path,Path(d)/'admin.sock'),identity)
 def test_bad_input_and_false_acceptance_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'cave.bin';path.write_bytes(b'bad')
   with patch('world.publish_cave.admin_request') as request:
    with self.assertRaises(ValueError):publish(path,Path(d)/'admin.sock')
    request.assert_not_called()
   path.write_bytes(BLOB)
   with patch('world.publish_cave.admin_request',return_value={'ok':True,'id':'wrong','persistent':False}):
    with self.assertRaises(ValueError):publish(path,Path(d)/'admin.sock')
 def test_blueprint_compiles_and_publishes_same_validated_bytes(self):
  doc={'rooms':[[2,2,5,5],[21,21,5,5]],'links':[[0,1]],'entrance_room':0,'exit_room':1}
  blob=encode(proposal_from_blueprint(doc));identity=SharedCave(blob).identity
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'blueprint.json';path.write_text(json.dumps(doc))
   with patch('world.publish_cave.admin_request',return_value={'ok':True,'id':identity,'persistent':False}) as request:
    self.assertEqual(publish_blueprint(path,Path(d)/'admin.sock'),identity)
    self.assertEqual(base64.b64decode(request.call_args.args[1]['template']),blob)
   for invalid in (json.dumps({**doc,'links':[]}), 'x'*16385):
    path.write_text(invalid)
    with patch('world.publish_cave.admin_request') as request:
     with self.assertRaises(ValueError):publish_blueprint(path,Path(d)/'admin.sock')
     request.assert_not_called()
if __name__=='__main__':unittest.main()
