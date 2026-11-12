# Regional first-rival tutorial integration

Child of app #443 (1b7903dca30389a90a77dcb6360105710ed02f84), paired with
native #92 (fddcf429bd6c93e476a914daac5e3580aa22e6c5). Independent development
stack, not Maya #410/#72 or RC12. Existing combined-region build options apply.

A common native regional policy now covers the stock first-battle branches:
Birch enemy initialization, Oak controller/return paths and HP/stat messages,
tutorial windows, low-HP AI, and introductory accuracy/critical-hit guidance.
Kanto uses the existing FRLG rules; Hoenn keeps its existing rules. Catch
tutorial dispatch from #443 reuses the policy. Existing FIRST_BATTLE setup,
trainer roster, rewards, defeat banks and personal save formats are unchanged.

Four native component tests pass, compiling six fixture executables; actual
setup, policy, catch entrypoints, windows, AI and accuracy are exercised.
Critical-hit guard and remaining large-controller wiring have focused checks.
29 app tests pass. No full native link, rendered Oak/rival sequence, party
preservation/save-restart, arbitrary cross-region replay or two-client QA.
This is not a complete Kanto playthrough. Held operations, actual saves,
donor assets, Maya branches and live providers remain untouched.
