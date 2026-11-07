import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, LockKeyhole } from 'lucide-react';
import './local-friends.css';

const endpointText = endpoint => endpoint ? `${endpoint.host.includes(':') ? `[${endpoint.host}]` : endpoint.host}:${endpoint.port}` : '';
const validPort = value => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 65535;

export default function LocalFriends({ state, worldKey, ready, busy, onBack, onOpen, onAction }) {
  const world = state.local_worlds?.find(item => item.key === worldKey);
  const sharing = state.local_sharing?.[worldKey];
  const [listen, setListen] = useState('127.0.0.1');
  const [port, setPort] = useState('8765');
  const [host, setHost] = useState('');
  const [friendPort, setFriendPort] = useState('8765');
  const [trainer, setTrainer] = useState('');
  const [existing, setExisting] = useState(false);
  const [review, setReview] = useState(null);
  const [uncertain, setUncertain] = useState(false);
  const sending = useRef(false);
  const reviewTitle = useRef(null);
  const canManage = Boolean(world && sharing?.selected && sharing?.running && ready && !busy && !uncertain);
  const stale = review?.type === 'local_invite' && (review.payload.reviewed_pin !== sharing?.pin || JSON.stringify(review.payload.reviewed_listener) !== JSON.stringify(sharing?.endpoint));
  useEffect(() => { if (review) reviewTitle.current?.focus(); }, [review]);
  useEffect(() => {
    if (!sharing?.endpoint) return;
    if (!host && !['0.0.0.0', '::'].includes(sharing.endpoint.host)) setHost(sharing.endpoint.host);
    setFriendPort(String(sharing.endpoint.port));
  }, [sharing?.endpoint?.host, sharing?.endpoint?.port]);

  async function confirm() {
    if (!review || !canManage || stale || sending.current) return;
    sending.current = true;
    try {
      const ok = await onAction(review.type, review.payload);
      if (ok === true) setReview(null);
      else setUncertain(true);
    } catch { setUncertain(true); }
    finally { sending.current = false; }
  }
  async function refresh() {
    if (sending.current || busy) return;
    sending.current = true;
    try {
      if (await onAction('local_share_refresh', {}) === true) { setUncertain(false); setReview(null); }
    } catch { setUncertain(true); }
    finally { sending.current = false; }
  }

  return <div className="interior narrow local-friends">
    <button className="back" disabled={busy} onClick={onBack}><ArrowLeft size={16} /> Local worlds</button>
    <header className="page-heading"><div><h1>Invite friends</h1><p>{world?.name || 'Local world'} · Runs on this computer.</p></div><LockKeyhole size={24} /></header>
    <section className="sharing-state"><strong>{!sharing ? 'Sharing status unavailable' : sharing.configured ? (sharing.listening ? 'TLS listener active' : 'TLS listener stopped') : 'Not shared'}</strong>{sharing?.endpoint && <span>{endpointText(sharing.endpoint)}</span>}<p>Disconnecting keeps sharing on. Stop sharing, stop the host or quit the launcher to close it.</p></section>
    {!sharing ? <p className="field-hint">Use a matching launcher version to manage local invitations.</p> : !sharing.selected || !sharing.running ? <div className="settings-card"><div><h2>Open this local host</h2><p>The game will stay closed. Switching from another session asks first.</p><button className="button primary" disabled={!ready || busy || !world?.trainer} onClick={() => onOpen(world)}>Open host</button></div></div> : <>
      {!sharing.configured ? <section className="sharing-form"><h2>Enable sharing</h2><label className="field-label" htmlFor="listen-host">Listen address</label><input className="text-input" id="listen-host" value={listen} maxLength={45} disabled={!canManage || Boolean(review)} onChange={event => setListen(event.target.value)} /><p className="field-hint">127.0.0.1 stays on this computer. Use this computer’s LAN IP for friends on your network. 0.0.0.0 listens on all IPv4 interfaces.</p><label className="field-label" htmlFor="listen-port">Listen port</label><input className="text-input port-field" id="listen-port" inputMode="numeric" value={port} maxLength={5} disabled={!canManage || Boolean(review)} onChange={event => setPort(event.target.value)} /><p className="field-hint">Creates or reuses this world’s TLS identity. No firewall, router or relay is configured.</p><button className="button primary" disabled={!canManage || Boolean(review) || !listen.trim() || !validPort(port)} onClick={() => setReview({ type: 'local_share_start', payload: { world: worldKey, listen_host: listen.trim(), port: Number(port), confirmed: true } })}>Review sharing</button></section>
        : <><div className="sharing-tools"><button className="text-button" disabled={!canManage || Boolean(review)} onClick={() => setReview({ type: 'local_share_stop', payload: { world: worldKey, confirmed: true } })}>Stop sharing</button><button className="text-button" disabled={!ready || busy} onClick={refresh}>Refresh</button></div>
          {sharing.listening && sharing.pin && <section className="sharing-form"><h2>Private invitation</h2><div className="invite-tabs" aria-label="Trainer invitation type"><button aria-pressed={!existing} disabled={!canManage || Boolean(review)} onClick={() => setExisting(false)}>New trainer</button><button aria-pressed={existing} disabled={!canManage || Boolean(review)} onClick={() => setExisting(true)}>Existing trainer</button></div><label className="field-label" htmlFor="friend-trainer">Friend’s trainer profile</label><input id="friend-trainer" className="text-input" value={trainer} maxLength={24} disabled={!canManage || Boolean(review)} onChange={event => setTrainer(event.target.value)} /><p className="field-hint">{existing ? 'Re-export access for that same trainer. This does not rotate or revoke older invitations.' : 'Use a separate profile for each player. Letters, numbers, underscores and hyphens.'}</p><label className="field-label" htmlFor="friend-host">Address your friend will use</label><input id="friend-host" className="text-input" value={host} maxLength={253} disabled={!canManage || Boolean(review)} onChange={event => setHost(event.target.value)} /><label className="field-label" htmlFor="friend-port">Invitation port</label><input id="friend-port" className="text-input port-field" value={friendPort} inputMode="numeric" maxLength={5} disabled={!canManage || Boolean(review)} onChange={event => setFriendPort(event.target.value)} /><p className="field-hint">Use an address your friend can reach. Reachability has not been checked.</p><button className="button primary" disabled={!canManage || Boolean(review) || !/^[A-Za-z0-9_-]{1,24}$/.test(trainer) || trainer === state.trainer || !host.trim() || !validPort(friendPort)} onClick={() => setReview({ type: 'local_invite', payload: { world: worldKey, trainer, host: host.trim(), port: Number(friendPort), existing, confirmed: true, reviewed_pin: sharing.pin, reviewed_listener: sharing.endpoint } })}>Review invitation</button></section>}
        </>}
    </>}
    {uncertain && <section className="sharing-warning" role="alert"><p>The last action was not confirmed. Refresh before trying again. If a new trainer was created, use Existing trainer to re-export its invitation.</p><button className="button ghost" disabled={!ready || busy} onClick={refresh}>Refresh sharing</button></section>}
    {review && <section className="sharing-review"><h2 ref={reviewTitle} tabIndex={-1}>{review.type === 'local_share_start' ? 'Enable local sharing?' : review.type === 'local_share_stop' ? 'Stop local sharing?' : `Create invitation for ${review.payload.trainer}?`}</h2>
      {review.type === 'local_share_start' ? <><p>Listen on <strong>{endpointText({ host: review.payload.listen_host, port: review.payload.port })}</strong> for {world?.name}.</p>{['0.0.0.0', '::'].includes(review.payload.listen_host) && <p>All network interfaces will be exposed. {review.payload.listen_host === '::' && 'IPv6 may also accept IPv4 connections, depending on this computer.'}</p>}<p>Reachable devices can connect to this listener. A valid private trainer invitation is still required.</p></>
        : review.type === 'local_share_stop' ? <p>Disconnects friends using this TLS listener. Your local host and game stay running.</p>
        : <><p><strong>{world?.name}</strong> · {endpointText({ host: review.payload.host, port: review.payload.port })}</p><p>{review.payload.existing ? 'Grants access to this existing trainer identity. Share it only with that trainer.' : 'Creates a separate trainer identity and a reusable private invitation.'} No file is sent to anyone automatically.</p><div className="fingerprint"><strong>Server fingerprint</strong><span>{review.payload.reviewed_pin}</span></div><p>Confirm this fingerprint through a separate trusted channel.</p></>}
      {stale && <p className="inline-error" role="alert">Sharing changed. Cancel this review and check the current listener.</p>}
      <div className="modal-actions"><button className="button ghost" disabled={busy} onClick={() => setReview(null)}>Cancel</button><button className="button primary" disabled={!canManage || stale} onClick={confirm}>{review.type === 'local_share_start' ? 'Enable sharing' : review.type === 'local_share_stop' ? 'Stop sharing' : 'Create invitation'}</button></div>
    </section>}
  </div>;
}
