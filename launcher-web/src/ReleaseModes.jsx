import React from 'react';
import './release-modes.css';

export default function ReleaseModes() {
  return <section className="worlds-section" aria-labelledby="rc8-modes-title">
    <div className="section-heading"><div><span className="eyebrow gold">RC8 · WHAT YOU CAN PLAY</span><h2 id="rc8-modes-title">RC8 play modes</h2></div></div>
    <div className="rc8-mode-grid">
      <article className="settings-card"><div><h3>Shared exploration</h3>
        <p>Open a local expedition, choose or generate an area, then enter it from WORLD in the game. Friends using matching RC8 clients can explore the same terrain.</p>
        <p className="field-hint">Choose standard wilds for guide/cast options, or XL outdoor worlds for 127 × 127 terrain. Shared XL does not include the offline story system or editable XL overlays.</p>
      </div></article>
      <article className="settings-card"><div><h3>Interactive adventures</h3>
        <p>Open an adventure published by your director, talk to its characters, and follow its interaction rules. A connected director can change dialogue and supported standard-area terrain.</p>
        <p className="field-hint">Opening an adventure does not start a director. Standard shared adventure state resets on a new visit; it is not a persistent multiplayer quest system.</p>
      </div></article>
      <article className="settings-card"><div><h3>Offline story tools</h3>
        <p>Advanced authoring tools create painted XL worlds with characters and progress that can survive restart and compatible terrain revisions. These are not shared multiplayer quests.</p>
        <details><summary>How this differs from the launcher</summary>
          <p className="field-hint">There is no offline-story editor or story launch button here yet. Authoring uses the shipped Python tools; play uses a separate offline save with the native generated-map and generated-progress options. See the release notes for the exact workflow. Ordinary solo play does not automatically load an authored story.</p>
        </details>
      </div></article>
    </div>
    <p className="field-hint">Generating from a theme sends it to the configured model provider and may incur charges. Reopening saved areas makes no model call. Trainer saves, shared area files and offline story journals are separate; save Pokémon progress normally in the game.</p>
  </section>;
}
