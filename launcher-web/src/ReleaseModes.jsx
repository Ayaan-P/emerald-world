import React from 'react';
import './release-modes.css';

export default function ReleaseModes() {
  return <section className="worlds-section" aria-labelledby="areas-help-title">
    <div className="section-heading"><h2 id="areas-help-title">Generated areas</h2></div>
    <div className="rc8-mode-grid">
      <article className="settings-card"><div><h3>Caves and outdoor worlds</h3><p>Open Explore, choose a local world, then generate or reopen an area. Enter through START → WORLD in the game.</p><p className="field-hint">Generating calls your configured model provider and may cost money. Reopening is free of model calls.</p></div></article>
      <article className="settings-card"><div><h3>Published adventures</h3><p>Open an adventure supplied by a director. Opening it does not start a director. Conversation state resets on a new visit.</p></div></article>
      <article className="settings-card"><div><h3>Offline story tools</h3><p>Authored XL stories use separate command-line tools and story journals. They are not shared multiplayer quests or part of ordinary solo play.</p></div></article>
    </div>
  </section>;
}
