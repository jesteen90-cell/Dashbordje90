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
  after.dataset.visual='true';
  return after.querySelectorAll('.kit').length===11;
}
function lineupHtml(d){
  const o=d.optimal_current_lineup||{},cs=d.current_squad||{},st=d.current_transfer_state||{};
  if(o.version!=='1.0-xp-legal-xi'||!String(cs.version||'').startsWith('1.'))return'';
  return `<div id="optimalCurrentSection" class="squadBar optimalQuick"><div><b>${esc(o.formation||'—')}</b><span>FORMASJON</span></div><div><b>${esc(o.captain||'—')} C</b><span>KAPTEIN</span></div><div><b>${esc(o.vice||'—')} VC</b><span>VISEKAPTEIN</span></div><div><b>${Number(st.free_transfers_remaining??0)} FT</b><span>IGJEN</span></div></div>`;
}
function applyPostTransferMode(d){
  const s=d.current_transfer_state||{};if(!s.post_transfer_mode)return;
  const h=document.getElementById('headline'),sum=document.getElementById('summary');
  if(h)h.textContent='SETT OPTIMALT LAG';
  if(sum)sum.textContent='Startellever, kaptein og benk er neste oppgave.';
  const old=document.getElementById('finalDuelSection');if(old)old.remove();
}
function ensureTeamUi(d){
  const team=document.getElementById('team');if(!team)return false;
  if(!document.getElementById('optimalCurrentSection')){
    const html=lineupHtml(d),note=document.getElementById('sourceNote');
    if(html){if(note)note.insertAdjacentHTML('afterend',html);else team.insertAdjacentHTML('afterbegin',html)}
  }
  return renderVisualOptimal(d);
}
async function load(){
  try{
    const r=await fetch(`data.json?lineup=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;
    LAST=await r.json();applyPostTransferMode(LAST);
    const ok=ensureTeamUi(LAST);
    if(!ok){setTimeout(()=>ensureTeamUi(LAST),250);setTimeout(()=>ensureTeamUi(LAST),800);setTimeout(()=>ensureTeamUi(LAST),1800)}
  }catch(e){console.error('optimal lineup render failed',e)}
}
window.addEventListener('load',()=>setTimeout(load,80));
document.addEventListener('click',e=>{const b=e.target.closest?.('.tab[data-tab="team"]');if(b&&LAST)setTimeout(()=>ensureTeamUi(LAST),40)});
})();