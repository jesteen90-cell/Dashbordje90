(()=>{
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let LAST=null;
function visualPlayers(rows){return (rows||[]).map(p=>({...p,captain:!!p.optimal_captain,vice:!!p.optimal_vice}))}
function renderVisualOptimal(d){
  const o=d?.optimal_current_lineup||{};
  if(o.version!=='1.0-xp-legal-xi')return false;
  const after=document.getElementById('after'),bench=document.getElementById('bench');
  if(!after||!bench||typeof pitch!=='function'||typeof benchHtml!=='function')return false;
  after.innerHTML=pitch(visualPlayers(o.lineup||[]));
  bench.innerHTML=benchHtml(visualPlayers(o.bench||[]));
  after.dataset.optimalGw=String(o.gw||'');
  return true;
}
function lineupHtml(d){
  const o=d.optimal_current_lineup||{},cs=d.current_squad||{};
  if(o.version!=='1.0-xp-legal-xi'||!String(cs.version||'').startsWith('1.'))return'';
  const tx=Number(cs.transfer_count_current_gw||0);
  return `<div class="section optimalSummary" id="optimalCurrentSection"><div class="card"><div class="planrow"><div><div class="eyebrow">Anbefaling for GW ${esc(o.gw)}</div><b>Formasjon ${esc(o.formation||'—')}</b></div><div class="optimalScore"><b>${Number(o.expected_team_score||0).toFixed(1)} p</b><span>forventet før kapteinsdobling</span></div></div><div class="miniStats"><div class="mini"><b>${esc(o.captain||'—')}</b><span>kaptein</span></div><div class="mini"><b>${esc(o.vice||'—')}</b><span>visekaptein</span></div><div class="mini"><b>${tx}</b><span>bytte brukt</span></div></div></div></div>`;
}
function postTransferHtml(d){
  const s=d.current_transfer_state||{},o=d.optimal_current_lineup||{};if(!s.post_transfer_mode)return'';
  const moves=(s.moves||[]).map(m=>`${esc(m.out_name)} → ${esc(m.in_name)}`).join(', ');
  return `<div class="section" id="postTransferSection"><div class="card compactStatus"><div><div class="eyebrow">Transfer gjennomført</div><b>${moves||'Transfer registrert'}</b></div><div><b>${esc(s.free_transfers_remaining)} FT</b><span>igjen · nytt bytte normalt −${Number(s.next_extra_transfer_cost_points||4)} p</span></div></div></div>`;
}
function applyPostTransferMode(d){
  const s=d.current_transfer_state||{};if(!s.post_transfer_mode)return;
  const h=document.getElementById('headline'),sum=document.getElementById('summary');
  if(h)h.textContent='SETT OPTIMALT LAG';
  if(sum)sum.textContent='Startellever, kaptein og benk er neste oppgave.';
  const old=document.getElementById('finalDuelSection');if(old)old.remove();
  const decision=document.getElementById('decision');if(decision&&!document.getElementById('postTransferSection'))decision.insertAdjacentHTML('afterbegin',postTransferHtml(d));
}
function ensureTeamUi(d){
  const team=document.getElementById('team');if(!team)return;
  if(!document.getElementById('optimalCurrentSection')){
    const html=lineupHtml(d),note=document.getElementById('sourceNote');
    if(html){if(note)note.insertAdjacentHTML('afterend',html);else team.insertAdjacentHTML('afterbegin',html)}
  }
  renderVisualOptimal(d);
}
async function load(){
  try{const r=await fetch(`data.json?lineup=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;LAST=await r.json();applyPostTransferMode(LAST);ensureTeamUi(LAST)}catch(e){console.error('optimal lineup render failed',e)}
}
window.addEventListener('load',()=>{setTimeout(load,120);setTimeout(()=>LAST&&ensureTeamUi(LAST),700);setTimeout(()=>LAST&&ensureTeamUi(LAST),1600)});
document.addEventListener('click',e=>{const b=e.target.closest?.('.tab[data-tab="team"]');if(b&&LAST)setTimeout(()=>ensureTeamUi(LAST),60)});
})();