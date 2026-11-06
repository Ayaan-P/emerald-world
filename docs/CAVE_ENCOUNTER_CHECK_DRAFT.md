# Native generated-cave encounter and return

This draft extends the verified offline generated-cave encounter check. A disposable native test-mode game enters a generated cave, walks until a visible wild opponent appears, checks its species and level against the existing cave encounter table, selects RUN, waits for the trainer and party to return to the cave, then leaves through the World menu and verifies the original field position and unchanged save bytes. The test uses no world connection, account, model request or personal save.

The fake-driver fixture tests the harness control flow only. The new escape-and-return path has not yet passed a native run; inspect exact-head CI before making that claim. Even a pass does not cover winning or catching, blackout, manual saving, multiplayer, human visual play or all cave layouts. The generated cave and its parents remain experimental and default-off.
