"""Hosted product operations composed with the existing native-session backend.

No GUI, game launch, save creation or state injection. A launcher can call
create/join/resume, then use its EXISTING native Play and Disconnect controls.
The world UUID supplies a stable private-save namespace across reconnects.
"""
from .hosting_client import HostingClient
from .transport import validate_invitation


class HostedWorldSession:
    def __init__(self, desktop_session, host_profile=None):
        self.desktop = desktop_session
        self.host_profile = host_profile

    def _disconnected(self):
        if self.desktop.state is not None:
            raise ValueError('disconnect before changing worlds')

    def _owner(self):
        if self.host_profile is None:
            raise ValueError('enroll a host account before creating or resuming an owned world')
        return HostingClient.from_file(self.host_profile)

    def _connect(self, result):
        world = result['world']
        world_id = HostingClient._world_id(world['id'])
        identity = validate_invitation(result['invitation'])
        cache = self.desktop.root / '.hosted-invitations'
        if cache.resolve() != cache:
            raise ValueError('hosted invitation cache must not contain symlinks')
        cache.mkdir(mode=0o700, exist_ok=True)
        destination = cache / (world_id+'-'+identity['trainer']+'.json')
        HostingClient.save_invitation(result,destination)
        key = 'hosted-'+world_id
        endpoint = identity['endpoint']
        paths = self.desktop.connect_remote(key,destination,
                        (endpoint['host'],endpoint['port']),identity['pin'])
        # Do not return bearer credentials to UI display/logging code.
        return dict(world=world,key=key,paths=paths)

    def create(self,name,trainer,*,request_id):
        self._disconnected()
        return self._connect(self._owner().create(name,trainer,request_id=request_id))

    def resume(self,world_id):
        self._disconnected()
        return self._connect(self._owner().resume(world_id))

    def join(self,invitation_path,trainer):
        self._disconnected()
        return self._connect(HostingClient.redeem(invitation_path,trainer))
