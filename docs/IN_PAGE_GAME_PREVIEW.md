# Experimental in-page game view

This preview depends on the player-journey launcher and the separate browser-input backend PR. It mirrors the existing native game window using the browser's window-sharing picker; it does not run the game in the browser. The player must explicitly select the window displaying the game. On Linux the browser may list the outer nested display rather than a separately named game window. Video stays in the browser page, while keyboard controls are sent to the local launcher and always control the game, even if another window is selected by mistake.

The preview needs a running human-controlled game, a supported browser, and Linux with the existing dedicated Xephyr display plus `xdotool` and `xwininfo`. Audio and gamepad input are not supported. Fullscreen depends on the browser. Click the view to control it; Ctrl+Shift+G releases keyboard focus, and Escape exits fullscreen. Stopping the preview leaves the native game running.

This is a prototype. It has not been verified on a real player desktop. Before release, check window selection and capture, keyboard focus and key release on disconnect, fullscreen, rendering when the game window is obscured, latency, and behavior under X11 and Wayland. The input backend's display/window isolation also needs security review.
