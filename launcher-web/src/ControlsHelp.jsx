import React from 'react';
import './controls-help.css';

const controls = [
  ['Move', 'Arrow keys'], ['A / confirm', 'Z'], ['B / back', 'X'],
  ['Start / menu', 'Enter'], ['Select', 'Backspace or \\'], ['L / R', 'A / S'],
];

export default function ControlsHelp() {
  return <details className="controls-help">
    <summary>Game controls</summary>
    <p>Default keyboard controls for the native game. Click its window before playing; your own remapped keys may be different.</p>
    <dl>{controls.map(([action, keys]) => <div key={action}><dt>{action}</dt><dd>{keys}</dd></div>)}</dl>
    <p>F11 toggles fullscreen in the native game window. Depending on your display setup, it may fill the game display rather than your monitor. Save in the game before closing it.</p>
  </details>;
}
