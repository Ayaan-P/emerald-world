import React, { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Expand, Gamepad2, Monitor, Square } from 'lucide-react';
import { perform } from './api';
import './game-mirror.css';

const SUPPORTED = new Set([
  ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').map(letter => `Key${letter}`),
  ...'0123456789'.split('').map(digit => `Digit${digit}`),
  'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Enter', 'Space', 'Backspace', 'Tab', 'Escape',
  'ShiftLeft', 'ShiftRight', 'ControlLeft', 'ControlRight', 'Comma', 'Period', 'Slash', 'Backslash',
  'Minus', 'Equal', 'BracketLeft', 'BracketRight',
]);

// Shared across mounts: HTTP starts cannot overtake a pending predecessor.
// Every mutating request also carries server ownership, so late cleanup is safe
// even if another tab starts a relay while this page awaits an HTTP response.
let relayTail = Promise.resolve();
function relayRequest(action, payload) {
  const request = relayTail.then(() => perform(action, payload));
  relayTail = request.catch(() => {});
  return request;
}

/** Browser capture is user-chosen and stays local; only bounded keys go to the relay. */
export default function GameMirror({ gameRunning, onBack }) {
  const [info, setInfo] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [starting, setStarting] = useState(false);
  const [focused, setFocused] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [message, setMessage] = useState('');
  const video = useRef(null), surface = useRef(null);
  const capture = useRef(null), active = useRef(false), mounted = useRef(true);
  const relaySession = useRef(null);
  const generation = useRef(0), held = useRef(new Set()), timer = useRef(null);
  const sending = useRef(false), queued = useRef(false), startGuard = useRef(false);

  function stop(update = true, note = '') {
    generation.current++; startGuard.current = false;
    const session = relaySession.current;
    relaySession.current = null;
    active.current = false; held.current.clear(); queued.current = false;
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    const stream = capture.current; capture.current = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    if (video.current) video.current.srcObject = null;
    if (session) void relayRequest('screen_stop', { session }).catch(() => {});
    if (update && mounted.current) { setStreaming(false); setStarting(false); setFocused(false); if (note) setMessage(note); }
  }

  async function sendKeys() {
    if (!active.current) return;
    if (sending.current) { queued.current = true; return; }
    sending.current = true;
    const session = relaySession.current;
    try { await relayRequest('screen_keys', { session, keys: [...held.current] }); }
    catch { if (active.current && relaySession.current === session) stop(true, 'Browser controls disconnected. Your native game is still running.'); }
    finally {
      sending.current = false;
      if (queued.current && active.current) { queued.current = false; void sendKeys(); }
    }
  }

  function releaseKeys() {
    if (!held.current.size) return;
    held.current.clear(); void sendKeys();
  }

  useEffect(() => {
    mounted.current = true;
    perform('screen_info', {}).then(result => { if (mounted.current) setInfo(result); })
      .catch(() => { if (mounted.current) setInfo({ available: false, reason: 'The in-page input component is not installed yet.' }); });
    const onFullscreen = () => { if (mounted.current) setFullscreen(document.fullscreenElement === surface.current); };
    const onVisibility = () => { if (document.hidden) releaseKeys(); };
    document.addEventListener('fullscreenchange', onFullscreen);
    document.addEventListener('visibilitychange', onVisibility);
    return () => { mounted.current = false; document.removeEventListener('fullscreenchange', onFullscreen); document.removeEventListener('visibilitychange', onVisibility); stop(false); };
  }, []);

  useEffect(() => {
    if (!gameRunning && (active.current || startGuard.current)) stop(true, 'The game closed. Start it again to use the in-page view.');
  }, [gameRunning]);

  useEffect(() => {
    if (streaming && video.current && capture.current) {
      video.current.srcObject = capture.current;
      void video.current.play().catch(() => {});
    }
  }, [streaming]);

  async function start() {
    if (startGuard.current) return;
    if (!navigator.mediaDevices?.getDisplayMedia) { setMessage('This browser does not support window sharing. Use the native game window.'); return; }
    startGuard.current = true;
    const request = ++generation.current;
    setStarting(true); setMessage('');
    let stream, session;
    try {
      // Call directly from the click: browsers require a user gesture for the picker.
      stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'window', frameRate: { ideal: 30, max: 60 } }, audio: false });
      if (!mounted.current || request !== generation.current) { stream.getTracks().forEach(track => track.stop()); return; }
      const track = stream.getVideoTracks()[0];
      if (!track) throw new Error('No window was shared.');
      capture.current = stream;
      track.addEventListener('ended', () => { if (capture.current === stream) stop(true, 'Window sharing stopped. Your native game is still running.'); }, { once: true });
      const result = await relayRequest('screen_start', {});
      session = result.session;
      if (typeof session !== 'string' || !session) throw new Error('The local launcher does not support preview ownership.');
      if (!mounted.current || request !== generation.current || track.readyState === 'ended') {
        stream.getTracks().forEach(item => item.stop());
        void relayRequest('screen_stop', { session }).catch(() => {});
        return;
      }
      relaySession.current = session;
      active.current = true;
      if (video.current) { video.current.srcObject = stream; void video.current.play().catch(() => {}); }
      timer.current = setInterval(() => { if (held.current.size) void sendKeys(); }, 200);
      startGuard.current = false; setStreaming(true); setStarting(false);
    } catch (error) {
      if (session) void relayRequest('screen_stop', { session }).catch(() => {});
      if (stream) stream.getTracks().forEach(track => track.stop());
      if (capture.current === stream) capture.current = null;
      if (mounted.current && request === generation.current) {
        startGuard.current = false; setStarting(false);
        setMessage(error?.name === 'NotAllowedError' ? 'Window sharing was cancelled or not allowed. Your native game is still running.' : 'Could not start the in-page view. Check the game window and try again.');
      }
    }
  }

  function keyDown(event) {
    if (!active.current) return;
    if (event.ctrlKey && event.shiftKey && event.code === 'KeyG') {
      event.preventDefault(); releaseKeys(); surface.current?.blur(); return;
    }
    if ((event.ctrlKey && (event.code === 'KeyR' || event.code === 'KeyP')) || event.altKey || event.metaKey) return;
    if (event.code === 'Escape' && document.fullscreenElement) return;
    if (!SUPPORTED.has(event.code)) return;
    event.preventDefault();
    if (!held.current.has(event.code) && held.current.size < 12) { held.current.add(event.code); void sendKeys(); }
  }

  function keyUp(event) {
    if (!SUPPORTED.has(event.code)) return;
    event.preventDefault();
    if (held.current.delete(event.code)) void sendKeys();
  }

  function toggleFullscreen() {
    if (document.fullscreenElement === surface.current) {
      void document.exitFullscreen().catch(() => setMessage('Could not exit fullscreen.'));
    } else if (surface.current?.requestFullscreen) {
      void surface.current.requestFullscreen().catch(() => setMessage('Fullscreen is unavailable in this browser.'));
    } else setMessage('Fullscreen is unavailable in this browser.');
  }

  return <div className="interior game-view">
    <button className="back" onClick={() => { stop(); onBack(); }}><ArrowLeft size={16} /> Back to launcher</button>
    <span className="eyebrow gold">EXPERIMENTAL</span><h1>In-page preview</h1>
    <p className="lead">Mirror your running game window here and use your keyboard. The native game still runs separately.</p>
    {!streaming && <div className="settings-card"><div className="settings-icon"><Monitor size={22} /></div><div><h3>Choose the game display</h3><p>Your browser will ask what to share. Select the window showing Emerald World. On Linux this may be the nested game display rather than a separately named game window. Avoid sharing your whole screen. The video stays in this page; keyboard input goes to the game even if you select a different window.</p><p>This preview does not carry audio or gamepad input. It needs a running human-controlled game plus xdotool and xwininfo on Linux.</p><button className="button primary" disabled={starting || !gameRunning || !info?.available} onClick={start}><Gamepad2 size={17} /> {starting ? 'Starting…' : 'Choose game display'}</button>{info && !info.available && <p className="inline-error">{info.reason}</p>}</div></div>}
    {streaming && <><div ref={surface} className={`game-surface ${focused ? 'focused' : ''}`} tabIndex={0} role="application" aria-label="Game screen. Click to control. Press Control Shift G to release keyboard." onClick={() => surface.current?.focus()} onFocus={() => setFocused(true)} onBlur={() => { setFocused(false); releaseKeys(); }} onKeyDown={keyDown} onKeyUp={keyUp}><video ref={video} muted autoPlay playsInline /><div className="game-surface-hint">{focused ? 'Keyboard controls active · Ctrl+Shift+G releases keyboard' : 'Click the game to control it'}</div></div><div className="game-view-actions"><button className="button primary" onClick={toggleFullscreen}><Expand size={16} /> {fullscreen ? 'Exit fullscreen' : 'Fullscreen'}</button><button className="button ghost" onClick={() => stop(true, 'Preview stopped. Your native game is still running.')}><Square size={15} /> Stop preview</button></div><p className="field-hint">Press Esc to leave fullscreen. Your game still runs in its native window. Audio and gamepad input are not included in this preview.</p></>}
    {!streaming && <video ref={video} hidden muted autoPlay playsInline />}
    {message && <p className="inline-error" role="status">{message}</p>}
  </div>;
}
