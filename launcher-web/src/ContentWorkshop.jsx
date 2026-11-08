import React, { useEffect, useRef, useState } from 'react';

const construction = {x:15,y:20,width:9,height:7,gate:'west',reservations:[]};
const starters = {
  outpost: construction,
  survey: {seed:1,loops:0,landmarks:[{id:'first_clearing',x:20,y:20,radius:4},{id:'second_clearing',x:85,y:85,radius:5}],reservations:[]},
  settlement: {label:'Name your settlement',construction,resident:{id:'choose_resident_id',name:'Name your resident',role:'Describe their purpose',goals:['Describe their first goal'],team:[{species:277,level:12}],gfx:8,text:'Will you chart a trail?',offer:{id:'choose_offer_id',revision:1,kind:'expedition',place_id:'native:LittlerootTown',target:1},completion_text:'Your trail notes are here.',completion_goals:['Keep the route notes']}},
};

function Layout({rows, before=[]}) {
  if (!rows?.length) return <p>No active generated area. A new route can be created in this empty world.</p>;
  return <svg role="img" aria-label="Content layout preview. Green cells are added walkable terrain." viewBox={`0 0 ${rows[0].length} ${rows.length}`} style={{width:'100%',maxWidth:510,background:'#182222',imageRendering:'pixelated'}}>
    {rows.flatMap((row,y) => [...row].map((cell,x) => cell === '.' ? <rect key={`${x}/${y}`} x={x} y={y} width="1" height="1" fill={before[y]?.[x] === '#' ? '#71cd87' : '#a4aa8c'} /> : null))}
  </svg>;
}

export default function ContentWorkshop({world, available, ready, busy, onBack, onOpen, onRequest}) {
  const [info,setInfo] = useState(null), [kind,setKind] = useState('outpost'), [label,setLabel] = useState('');
  const [text,setText] = useState(''), [outcome,setOutcome] = useState(''), [review,setReview] = useState(null);
  const [confirmed,setConfirmed] = useState(false), [error,setError] = useState(''), [saved,setSaved] = useState(false);
  const [working,setWorking] = useState(false), [uncertain,setUncertain] = useState(false);
  const pending = useRef(false);
  const disabled = busy || working || !ready || !available;
  function edit(fn) { fn(); setReview(null); setConfirmed(false); setSaved(false); }
  async function request(action,payload) {
    if (pending.current) return;
    pending.current=true; setWorking(true); setError('');
    try {
      const result = await onRequest(action,{world:world.key,...payload});
      if (!result) throw new Error('The launcher did not confirm this action.');
      return result;
    } catch(e) { setError(e.message); return null; }
    finally { pending.current=false; setWorking(false); }
  }
  async function reload() {
    setReview(null); setConfirmed(false); setSaved(false);
    const result = await request('content_read',{});
    if (result) {setInfo(result);setUncertain(false);}
  }
  useEffect(() => { if (available && world) reload(); else setInfo(null); }, [available,world?.key]);
  async function preview() {
    let plan;
    try {plan=['field_test','field_story'].includes(kind) ? {} : JSON.parse(text);} catch {setError('Enter a valid JSON content plan. Nothing was changed.');return;}
    const result=await request('content_preview',{kind,label:kind === 'field_test' ? 'RC11 field test' : kind === 'field_story' ? 'The Two-Tower Signal' : label,plan,outcome_seq:outcome ? Number(outcome) : null});
    if(result) {setReview(result);setConfirmed(false);setSaved(false);}
  }
  async function apply() {
    if (!review || !confirmed) return;
    const token=review.token; setReview(null);setConfirmed(false);
    const result=await request('content_apply',{token,confirmed:true});
    if(result) {setInfo(result);setSaved(true);} else setUncertain(true);
  }
  return <div className="interior narrow">
    <button className="back" disabled={working} onClick={onBack}>Back to local worlds</button>
    <h1>Content workshop</h1><p className="lead">{world?.name || 'Choose a local world'}</p>
    <p>Local owner tools for authored content. No model provider is contacted. Nothing is added until you review and apply it. Hosted worlds are not supported by this page.</p>
    {!available ? <><p>Open this local host first. You do not need to start the game.</p><button className="button primary" disabled={!ready || busy || !world} onClick={() => onOpen(world)}>Open local host</button></> : <>
      <button className="text-button" disabled={disabled} onClick={reload}>Reload content status</button>
      {info && <>
        <p>Active area: {info.identity || 'None'}{info.version && ` (template ${info.version})`}</p>
        <p>Existing residents: {info.residents.join(', ') || 'None'}. Existing residents are retained.</p>
        <p>{info.players} connected players. Save and close all games before applying content.</p>
        <p>Only if you want a public test-guild record, press T and send /guild create FieldTest, then /guild chronicle on and /guild expedition start Route101 1. Visit Route101 with your starter to earn an actual recorded completion. Save and close the game, reload this page, select Settlement with recurring resident, choose that completion and edit the starter plan before previewing. No campaign progress is fabricated. Construction creates a new map revision. Surveys and discovery chapters stay bound to their original archived revision, which you can reactivate in Explore.</p>
        <label className="field-label">Content type<select className="text-input" disabled={disabled || uncertain} value={kind} onChange={e => edit(() => {setKind(e.target.value);setText('');})}><option value="field_story">Cooperative field story (RC12)</option><option value="field_test">RC11 field test (curated)</option><option value="outpost">Frontier outpost</option><option value="settlement">Settlement with recurring resident</option><option value="survey">Landmark route and private survey</option></select></label>
        {kind === 'field_story' ? <section><h2>The Two-Tower Signal</h2><p>A complete two-player expedition: separate clues in Petalburg and Rustboro, two linked puzzles, and a shared decision that changes the story later visitors hear. Both parts install together. Existing maps, residents, saves and completed runs are retained.</p><p>Use two matched RC12 clients. The authored station coordinates need an in-game walkability check before public hosting. This adds narrative clues and consequences, not new buildings or transport.</p><p>After installation, play this world. Press T and send /mystery start signal_v2. Share the displayed invitation with your partner. Use /mystery status to find your station, then /mystery clue. The designated solver submits the displayed answer command while both players are at their stations. Progress survives reconnects; /mystery leave cancels for both.</p><p>After the final puzzle, read /story signal_after_v2 in Rustboro. Choose whether the town restores its warning relay or archives the message. Later visitors see that choice. Only participants unlock the decision.</p><button className="button primary" disabled={disabled || uncertain} onClick={preview}>Preview cooperative field story</button></section> : kind === 'field_test' ? <section><h2>Try the new RC11 content</h2><p>Use a separate empty local world named RC11 field test and a new trainer. This curated area is authored test content, not a model-generated campaign. Preview adds nothing. Applying saves a route with a field station, a registered private survey and a recurring Field Scholar.</p><p>After applying, use Explore → Play now. Get your first conscious Pokémon, go outdoors on foot, open the WORLD menu and choose Explore generated area. There is no need to reach Slateport. At the field station (8,8), talk to the scholar. Press T and send /explore start, then walk to lookout (22,8). Private arrival alone does not move the scholar.</p><p>Only if you want to publish this fictional landmark discovery, send /explore share lookout, read the warning, then /explore share lookout confirm. The scholar’s next authored chapter appears at the lookout with new dialogue and team. /explore status reports your private survey. Public sharing is optional and irreversible.</p><p>The field station is a route clearing, not an outcome-founded settlement. To exercise real settlement construction, complete a public guild expedition with explicit chronicle consent, save and close the game, then use Settlement with recurring resident below. An uninhabited frontier outpost needs no guild outcome.</p><button className="button primary" disabled={disabled || uncertain || Boolean(info.identity)} onClick={preview}>Preview RC11 field test</button>{info.identity && <p>Create a separate empty local world for this preset. Existing geography is never replaced.</p>}</section> : <>
        <p>{kind === 'survey' ? 'For a new route, use an empty local world. In a world with existing geography, only the exact already archived route plan can be registered. Registration never activates a different map. Return to Explore to activate that saved route.' : 'Adds a courtyard and connected trail to unused rock in the active plain 127 × 127 XL area. Existing floor and inhabitants are protected. Choose a footprint with a one-tile buffer clear of old paths.'}</p>
        {kind === 'settlement' ? <>
          <label className="field-label">Public guild completion<select className="text-input" disabled={disabled || uncertain} value={outcome} onChange={e => edit(() => setOutcome(e.target.value))}><option value="">Choose recorded outcome</option>{info.outcomes.map(e => <option key={e.seq} value={e.seq}>#{e.seq} {e.guild_name} {e.goal_kind}</option>)}</select></label>
          {!info.outcomes.length && <p>No public guild completion exists yet. In game, a guild leader must explicitly enable the guild chronicle and complete an expedition. This page never changes publication settings. You can still build an uninhabited outpost.</p>}
          <p>Author the settlement label and resident in the plan. Use a unique resident ID. The expedition offer requires explicit in-game acceptance by a guild leader with chronicle enabled. Completing that offer updates this resident’s goals and dialogue. Team species are enabled numeric IDs, not private player teams. This does not create proof of a battle or catch.</p>
        </> : <label className="field-label">Destination name<input className="text-input" maxLength={80} disabled={disabled || uncertain} value={label} onChange={e => edit(() => setLabel(e.target.value))} /></label>}
        <button className="button ghost" disabled={disabled || uncertain} onClick={() => edit(() => setText(JSON.stringify(starters[kind],null,2)))}>Start editable plan</button>
        <p>Edit every name and purpose to fit your world. This button only fills a local draft. Coordinates are tile positions, not screen pixels.</p>
        <label className="field-label">Content plan JSON<textarea className="text-input" rows={20} maxLength={16384} spellCheck={false} disabled={disabled || uncertain} value={text} onChange={e => edit(() => setText(e.target.value))} /></label>
        <details><summary>Plan format</summary><p>Outposts use x, y, width and height (5..15), gate (north/east/south/west) and reservations ([x,y,width,height] rectangles). Survey plans use seed, loops (0..4), 2..12 landmarks (unique lowercase id, x, y, radius 2..10) and reservations. Settlement plans include label, construction (an outpost plan) and resident. The editable starter shows all resident fields. Text is one or two ASCII lines, at most 28 characters each. The authority validates species IDs and offer destinations. No code or extra keys are accepted.</p></details>
        <button className="button primary" disabled={disabled || uncertain || !text.trim() || (kind === 'settlement' ? !outcome : !label.trim())} onClick={preview}>Preview content</button>
        </>}
        {review && <section aria-label="Reviewed content"><h2>Review content</h2><p>{review.validation}</p><Layout rows={review.proposed_rows} before={info.rows} /><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(review.report,null,2)}</pre><details><summary>Exact reviewed plan</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(review.plan,null,2)}</pre></details><label><input type="checkbox" disabled={disabled} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I reviewed this content and consent to saving it in this local world.</label><button className="button primary" disabled={disabled || !confirmed || info.players > 0} onClick={apply}>Apply reviewed content</button></section>}
        {!review && <Layout rows={info.rows} />}
        {saved && kind === 'field_story' && <p role="status">Both story parts are saved. Play this world with your partner, press T and send /mystery start signal_v2. Use /mystery status to resume. No generated-area entry is needed.</p>}
        {saved && kind !== 'field_story' && <p role="status">Content saved and read back from this local world. Open Explore, play this world and get a conscious Pokémon, go outdoors on foot and choose WORLD → Explore generated area. For a registered route survey, press T and send /explore start. Use /explore status or /explore stop. Visits remain private. Only /explore share LANDMARK confirm publishes a discovery. Face a resident and press Z to talk. An expedition offer needs your explicit acceptance.</p>}
        {uncertain && <p role="status">The save was not confirmed. Nothing retries automatically. Reload content status and inspect the world before creating another review.</p>}
      </>}
    </>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
