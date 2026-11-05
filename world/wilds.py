"""Offline 63x63 generated outdoor terrain, with no executable content."""
from .large_cave import encode as encode_geometry

def encode(proposal):
    return b'EWGMAP06' + encode_geometry(proposal)[8:]
