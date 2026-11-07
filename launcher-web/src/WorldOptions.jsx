import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Check, SlidersHorizontal } from 'lucide-react';
import './world-options.css';

const defaultRules = () => ({ wild_shuffle: { enabled: false, seed: 1 } });
const same = (a, b) => a?.wild_shuffle.enabled === b?.wild_shuffle.enabled && a?.wild_shuffle.seed === b?.wild_shuffle.seed;
const remaining = [
  ['Collecting', 'Species pools · Expanded encounters'],
  ['Battle', 'Mega Evolution · Z-Moves · Dynamax / Gigantamax · Terastallization'],
  ['Progression', 'Exp. Share · Level caps · Challenge rules'],
  ['Team-building', 'Reusable TMs · Evolution · Move learning · Breeding'],
  ['Exploration', 'Followers · NPC partners · Fishing · Repels / lures · Rematches'],
];

function supported(value) {
  const shuffle = value?.rules?.wild_shuffle;
  return value?.status === 'ready' && value.version === 1
    && Number.isInteger(value.revision) && value.revision >= 0 && value.revision <= 2147483647
    && Number.isInteger(value.players) && value.players >= 0
    && value.rules && Object.keys(value.rules).length === 1 && shuffle && Object.keys(shuffle).length === 2
    && typeof shuffle.enabled === 'boolean' && Number.isInteger(shuffle.seed) && shuffle.seed >= 1 && shuffle.seed <= 20;
}

export default function WorldOptions({ state, worldKey, ready, busy, onChoose, onBack, onOpen, onSave, onRefresh, onDirtyChange }) {
  const worlds = state.local_worlds || [];
  const world = worlds.find(item => item.key === worldKey);
  const current = state.world_options?.[worldKey];
  const compatible = Boolean(world) && supported(current);
  const [base, setBase] = useState(null);
  const [draft, setDraft] = useState(defaultRules);
  const [review, setReview] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [saved, setSaved] = useState(false);
  const pending = useRef(false);
  const reviewHeading = useRef(null);
  const editButton = useRef(null);
  const savedMessage = useRef(null);
  const wasReviewing = useRef(false);
  const dirty = Boolean(base && !same(base.rules, draft));
  const stale = Boolean(base && compatible && (base.revision !== current.revision || !same(base.rules, current.rules)));
  const validSeed = Number.isInteger(draft.wild_shuffle.seed) && draft.wild_shuffle.seed >= 1 && draft.wild_shuffle.seed <= 20;
  const editable = ready && !busy && compatible && !uncertain && !stale && current.revision < 2147483647;
  const canSave = editable && dirty && validSeed && current.players === 0;

  useEffect(() => {
    // Polls must not replace a draft or erase an uncertain write outcome.
    if (compatible && !dirty && !review && !uncertain
        && (!base || current.revision > base.revision || (current.revision === base.revision && same(current.rules, base.rules)))) {
      setBase(current);
      setDraft(current.rules);
    }
  }, [compatible, current?.revision, current?.rules?.wild_shuffle?.enabled, current?.rules?.wild_shuffle?.seed, dirty, review, uncertain]);
  useEffect(() => { onDirtyChange(dirty || uncertain); }, [dirty, uncertain, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    if (!dirty && !uncertain) return;
    const guard = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty, uncertain]);
  useEffect(() => {
    if (review) reviewHeading.current?.focus();
    else if (wasReviewing.current) (saved ? savedMessage : editButton).current?.focus();
    wasReviewing.current = review;
  }, [review, saved]);

  function edit(shuffle) {
    setDraft({ wild_shuffle: shuffle }); setReview(false); setSaved(false);
  }

  async function reload() {
    if (pending.current) return;
    pending.current = true;
    try {
      const next = await onRefresh();
      const fresh = next?.world_options?.[worldKey];
      if (supported(fresh)) {
        setBase(fresh); setDraft(fresh.rules); setUncertain(false); setReview(false); setSaved(false);
      }
    } finally { pending.current = false; }
  }

  async function apply() {
    if (!canSave || !review || pending.current) return;
    pending.current = true;
    try {
      const next = await onSave({ world: worldKey, expected_revision: base.revision, rules: draft, confirmed: true });
      const fresh = next?.world_options?.[worldKey];
      if (supported(fresh) && fresh.revision === base.revision + 1 && same(fresh.rules, draft)) {
        setBase(fresh); setDraft(fresh.rules); setReview(false); setUncertain(false); setSaved(true);
      } else { setUncertain(true); setReview(false); }
    } catch { setUncertain(true); setReview(false); }
    finally { pending.current = false; }
  }

  const unavailable = !world ? 'Choose a local world.' : !current || current.status === 'unsupported'
    ? 'This host does not provide world options. It needs the world-rules update.'
    : current.status === 'stopped' ? 'Open the local host to load its options. The game will stay closed.'
    : current.status === 'error' ? 'World options could not be read. Refresh to try again.'
    : 'This host uses options this launcher cannot edit. Use a matching launcher version.';

  return <div className="interior rules-page">
    <button className="back" disabled={busy} onClick={onBack}><ArrowLeft size={16} /> Local worlds</button>
    <header className="page-heading"><div><h1>World options</h1><p>Shared gameplay. Display and controls stay personal.</p></div><SlidersHorizontal size={25} aria-hidden="true" /></header>
    <section className="rules-world" aria-label="Selected world">
      <label htmlFor="rules-world">Local world</label>
      <select id="rules-world" className="text-input" value={worldKey || ''} disabled={busy || !worlds.length} onChange={event => onChoose(event.target.value)}>
        {!world && <option value="">Choose a world</option>}
        {worlds.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}
      </select>
      {compatible && <span className="rules-revision">Revision {current.revision} · {current.players} {current.players === 1 ? 'player' : 'players'}</span>}
    </section>
    {!compatible && <section className="rules-notice" role="status"><p>{unavailable}</p>
      {world && current?.status === 'stopped' ? <button className="button ghost" disabled={!ready || busy || !world.trainer} onClick={() => onOpen(world)}>Open host</button>
        : <button className="text-button" disabled={!ready || busy || !world} onClick={reload}>Refresh options</button>}
    </section>}
    {saved && <p className="rules-saved" role="status" tabIndex={-1} ref={savedMessage}><Check size={16} /> World options saved.</p>}
    {(stale || uncertain) && <section className="rules-notice warning" role="alert"><p>{uncertain ? 'Check the saved options before trying again. The last save was not confirmed.' : 'World options changed while you were editing. Reload before applying a new draft.'}</p><button className="button ghost" disabled={!ready || busy} onClick={reload}>Discard draft & reload</button></section>}
    {compatible && current.players > 0 && <p className="rules-notice" role="status">All players must leave before applying changes. No one is disconnected automatically.</p>}
    {compatible && current.revision === 2147483647 && <p className="rules-notice" role="status">This world has reached its options revision limit. Ask the server operator to check it.</p>}
    <section className="rules-presets" aria-label="Presets"><div><h2>Preset</h2><p>Review changes before applying.</p></div><button className="button ghost" disabled={!editable} onClick={() => edit(defaultRules().wild_shuffle)}>Use default</button><div className="rules-pending-preset"><button className="button ghost" disabled>Expansion playground</button><small>Needs a matching host and game update.</small></div></section>
    {compatible && <section className="rules-section" aria-labelledby="collecting-title"><div className="rules-category"><span>01</span><h2 id="collecting-title">Collecting</h2></div>
      <div className="rule-row"><div><label htmlFor="shuffle">Wild shuffle</label><p>Shuffle ordinary encounters from the first 386 species.</p></div><label className="rule-switch"><input id="shuffle" type="checkbox" checked={draft.wild_shuffle.enabled} disabled={!editable} onChange={event => edit({ ...draft.wild_shuffle, enabled: event.target.checked })} /><span>{draft.wild_shuffle.enabled ? 'On' : 'Off'}</span></label></div>
      <div className="rule-row seed-row"><div><label htmlFor="shuffle-seed">Shuffle seed</label><p>The same seed gives world members the same shuffle.</p></div><input id="shuffle-seed" className="text-input" type="number" min="1" max="20" step="1" inputMode="numeric" aria-describedby="shuffle-seed-help" aria-invalid={!validSeed} value={draft.wild_shuffle.seed} disabled={!editable} onChange={event => edit({ ...draft.wild_shuffle, seed: event.target.value === '' ? '' : Number(event.target.value) })} /></div>
      <p id="shuffle-seed-help" className={validSeed ? 'field-hint' : 'inline-error'}>Seed 1–20. Kept when shuffle is off.</p>
      <p className="field-hint">Enabling shuffle requires a matching world-rules game client for every player.</p>
    </section>}
    <details className="rules-planned"><summary>Additional world controls</summary><p>These controls need a matching host and game update.</p><dl>{remaining.map(([category, systems]) => <div key={category}><dt>{category}</dt><dd>{systems}</dd></div>)}</dl></details>
    {review && <section className="rules-review" aria-labelledby="review-title"><h2 id="review-title" ref={reviewHeading} tabIndex={-1}>Apply to {world?.name}?</h2><dl>
      {base.rules.wild_shuffle.enabled !== draft.wild_shuffle.enabled && <div><dt>Wild shuffle</dt><dd>{base.rules.wild_shuffle.enabled ? 'On' : 'Off'} → {draft.wild_shuffle.enabled ? 'On' : 'Off'}</dd></div>}
      {base.rules.wild_shuffle.seed !== draft.wild_shuffle.seed && <div><dt>Shuffle seed</dt><dd>{base.rules.wild_shuffle.seed} → {draft.wild_shuffle.seed}</dd></div>}
    </dl><p>Applies to this world for everyone who joins. Trainer saves are not edited.</p><div className="rules-actions"><button className="button ghost" disabled={busy} onClick={() => setReview(false)}>Keep editing</button><button className="button primary" disabled={!canSave} onClick={apply}>Apply changes</button></div></section>}
    {compatible && !review && <div className="rules-actions"><span>{dirty ? 'Unapplied changes' : 'No changes'}</span>{!stale && !uncertain && <button className="text-button" disabled={!ready || busy} onClick={reload}>{dirty ? 'Discard draft & reload' : 'Refresh options'}</button>}<button ref={editButton} className="button primary" disabled={!canSave} onClick={() => setReview(true)}>Review changes</button></div>}
  </div>;
}
