"""Regression for the native player movement flag's idle/tile-state contract."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PlayerMovementSignalTests(unittest.TestCase):
    def test_stationary_movement_action_does_not_report_transit(self):
        """Face/walk-in-place actions can be active while the avatar is stationary."""
        source = (ROOT / 'engines/expansion-native/platform/main.c').read_text()
        match = re.search(r'player && (?P<expression>[^;]+?)\s*\? "true" : "false"', source)
        if match is None:
            self.fail('native observation must publish a moving signal')
        harness = f'''#include <stdbool.h>
#include <stdlib.h>
#define MOVEMENT_ACTION_NONE 0xFF
#define T_NOT_MOVING 0
#define T_TILE_TRANSITION 1
#define T_TILE_CENTER 2
struct ObjectEvent {{ unsigned char movementActionId; }};
struct PlayerAvatar {{ unsigned char tileTransitionState; }};
static struct ObjectEvent objectEvent;
static struct PlayerAvatar gPlayerAvatar;
static const struct ObjectEvent *player = &objectEvent;
int main(int argc, char **argv) {{
    if (argc != 4) return 9;
    objectEvent.movementActionId = (unsigned char)atoi(argv[1]);
    gPlayerAvatar.tileTransitionState = (unsigned char)atoi(argv[2]);
    bool moving = player && ({match.group('expression')});
    return moving == (atoi(argv[3]) != 0) ? 0 : 1;
}}
'''
        with tempfile.TemporaryDirectory(prefix='player-moving-') as directory:
            c_file = Path(directory) / 'moving.c'
            binary = Path(directory) / 'moving'
            c_file.write_text(harness)
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(c_file), '-o', str(binary)], check=True, capture_output=True, text=True)
            # A non-NONE face/walk-in-place action is not physical tile movement.
            idle = subprocess.run([str(binary), '1', '0', '0'], capture_output=True, text=True)
            self.assertEqual(idle.returncode, 0, 'an idle face/walk-in-place action must not be moving')
            # Only the between-tile transition is physical movement; centered
            # completion is aligned and may still have an animation/action id.
            subprocess.run([str(binary), '255', '1', '1'], check=True)
            centered = subprocess.run([str(binary), '1', '2', '0'], capture_output=True, text=True)
            self.assertEqual(centered.returncode, 0, 'tile-center alignment must not report movement')


if __name__ == '__main__':
    unittest.main()
