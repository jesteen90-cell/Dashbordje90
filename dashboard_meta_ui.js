(()=>{
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function planCard(x){const a=x.action||{},pi=x.plan_intelligence||{},score=Number(x.xi_xp||pi.expected_team_score||0);return `<article class="card"><div class="planrow"><div><div class="eyebrow">Runde ${esc(x.gw)}</div><b>${esc(a.label||'Ingen handling')}</b></div><div><b>${score.toFixed(1)} p</b><div class="muted">forventet lagscore</div></div></div><div class="planMeta">Kaptein: ${esc(x.captain||'—')}</div></article>`}
async function run(){try{
 const r=await fetch(`data.json?meta=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;const d=await r.json();
 const el=document.getElementById('teamId');if(el)el.textContent=d.fpl_team_id?`FPL-lag #${d.fpl_team_id}`:'FPL-lag: ikke tilgjengelig';
 // Etter gjennomført transfer skal hovedbildet være Lag + Plan, ikke gamle pre-transfer diagnostikk-kort.
 if(!(d.current_transfer_state||{}).post_transfer_mode){
   const decision=document.getElementById('decision');
   if(decision&&d.deadline_lock?.version){const details=document.createElement('details');details.className='historyDetails';details.innerHTML=`<summary>Avansert beslutningsgrunnlag</summary><div class="card"><b>${esc(d.deadline_lock.verdict||'—')}</b><div class="muted">Sikkerhetskontroll for transferbeslutningen.</div></div>`;decision.appendChild(details)}
 }
 const future=document.getElementById('future');if(future&&!(d.post_transfer_plan||{}).active&&(d.future||[]).some(x=>x.plan_intelligence)){future.innerHTML=(d.future||[]).map(planCard).join('')}
}catch(_e){}}
run();
})();