"""PyInstaller entry point for the remote-only Windows guest."""
from world.windows_client import main

if __name__ == '__main__':
    raise SystemExit(main())
