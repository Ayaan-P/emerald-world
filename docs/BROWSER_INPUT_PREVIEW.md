# Experimental in-page game controls

This change provides the **input half** of an opt-in in-page game preview. It does not capture or stream pixels by itself. A separate browser UI must explicitly ask the player to share the already-running game window using the browser's screen-sharing picker. Capture stays in the browser; this backend does not read or send the screen image.

The game continues running in its native window and dedicated nested X display. When the player opts in, this helper identifies one matching human-controlled game window on that display, then forwards a bounded set of keyboard states to it using `xdotool`. It does not target the host desktop display, send arbitrary commands, read clipboard contents, modify saves, or take control of an agent-controlled game. A short lease releases held keys when updates stop; disconnecting, leaving, quitting or explicitly stopping also releases them.

The launcher already authenticates local API actions with its per-session capability and validates origin. `xdotool` and `xwininfo` must be available on the user's Linux system; no OS packages are installed by this change. This is a keyboard-control prototype, not gamepad support, audio streaming, a native WebAssembly port, or a guarantee that all browsers can capture an obscured window. Reset and pause chords are deliberately not forwarded.

Actual browser/window capture, input latency, focus behavior, key release after crashes, fullscreen behavior, and native gameplay need verification on a real supported Linux desktop before enabling this for players. The implementation has only fake-process tests in the development environment. Keep the native game window available as the fallback.
