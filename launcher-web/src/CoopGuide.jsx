import React from 'react';
import './coop-guide.css';

export default function CoopGuide() {
  return <details className="coop-guide">
    <summary>How to play together</summary>
    <ol>
      <li><strong>Get into the same world.</strong> The host sends each friend a private player invitation. Each player joins and starts their own trainer. Only accept an invitation from someone you trust.</li>
      <li><strong>Meet in the game.</strong> Go to the same map, stand near each other, and close any menus, dialogue or battles. Each player needs usable Pokémon.</li>
      <li><strong>Tag up.</strong> Face the other trainer and press A (Z on the default keyboard). Choose “Tag up (first 3 mons)”. Your friend must accept the invitation.</li>
      <li><strong>Battle together.</strong> Stay nearby and enter a supported wild or ordinary trainer battle. Each player controls their own Pokémon. Finish the encounter and wait for both players to return to the field before saving or disconnecting.</li>
    </ol>
    <p>To stop teaming up, interact with your partner again and choose “End tag”. Shared encounters have limitations, including restricted battle items.</p>
  </details>;
}
