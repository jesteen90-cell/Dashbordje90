(()=>{
function e(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function cash(v){let n=Number(v);return Number.isFinite(n)?`£${n.toFixed(1)}m`:'—'}
function actionHtml(a){
  if(!a||a.action==='bank') return '<div class="planAction bankAction"><b>SPAR GRATISBYTTET</b><span>Ingen transfer denne runden.</span></div>';
  let pairs=(a.pairs||[]).map(x=>`<div class="planTransfer"><span class="planOut">UT ${e(x.out?.name||'?')}</span><span>→</span><span class="planIn">INN ${e(x.in?.name||'?')}</span></div>`).join('');
  return `<div class="planAction transferAction"><b>${a.transfers||1} planlagt bytte${Number(a.transfers)>1?'r':''}${a.hit?` · -${a.hit} p hit`:''}</b>${pairs}</div>`;
}
function card(x){
  let a=x.action||{},pi=x.plan_intelligence||{},score=Number(x.xi_xp||pi.expected_team_score||0),ftB=pi.free_transfers_before,ftA=pi.free_transfers_after;
  let why=(pi.why||[]).map(t=>`<div class="planReason">${e(t)}</div>`).join('');
  let triggers=(pi.change_triggers||[]).map(t=>`<div class="planTrigger">${e(t)}</div>`).join('');
  return `<article class="card planDetailed">
    <div class="planRoundHead"><div><div class="eyebrow">Runde ${e(x.gw)}</div><div class="planRoundTitle">${e(a.label||'Ingen handling')}</div></div><span class="planConfidence">PLANSTATUS ${e(pi.confidence||'—')}</span></div>
    ${actionHtml(a)}
    <div class="planMetricGrid">
      <div><b>${score.toFixed(1)} p</b><span>forventet lagscore</span></div>
      <div><b>${e(x.captain||'—')}</b><span>kaptein</span></div>
      <div><b>${ftB??'—'} → ${ftA??'—'}</b><span>gratisbytter</span></div>
      <div><b>${cash(pi.bank_before)} → ${cash(pi.bank_after??x.bank)}</b><span>bank</span></div>
    </div>
    <div class="planExplain"><b>Hvorfor ligger dette i planen?</b>${why||'<div class="planReason">Ingen ekstra forklaring tilgjengelig ennå.</div>'}</div>
    <div class="planExplain triggerBox"><b>Hva kan endre planen?</b>${triggers||'<div class="planTrigger">Planen bygges på nytt når data endres.</div>'}</div>
    <div class="planRolling">${e(pi.note||'Dette er en rullerende plan og kan endres før den aktuelle fristen.')}</div>
  </article>`;
}
function renderPlan(){
  if(typeof D==='undefined'||!D)return;
  let box=document.querySelector('#future'); if(!box)return;
  box.innerHTML=(D.future||[]).map(card).join('')||'<div class="card muted">Ingen fler-runders plan tilgjengelig.</div>';
  let intro=document.querySelector('#plan .tabExplain span');
  if(intro)intro.textContent='Viser den beste ruten modellen ser nå. Hver runde forklarer handling, lagscore, kaptein, gratisbytter, bank og hva som kan få planen til å endres. Dette er en rullerende plan – ikke et løfte om fremtidige bytter.';
}
window.addEventListener('load',()=>setTimeout(renderPlan,250));
})();