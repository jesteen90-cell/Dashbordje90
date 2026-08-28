(()=>{
function e(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function cash(v){let n=Number(v);return Number.isFinite(n)?`£${n.toFixed(1)}m`:'—'}
function postCard(x){
  const pairs=x.pairs||[],isBank=x.action==='bank',move=pairs[0];
  const action=isBank?'SPAR GRATISBYTTET':move?`${e(move.out_name)} → ${e(move.in_name)}`:'Ingen handling';
  const why=isBank?'Beholder fleksibiliteten til neste deadline.':`Modellen ser dette som beste rute akkurat nå uten poengtrekk.`;
  const change='Skader, minutter, prisendringer eller nye kampdata kan endre dette før runden.';
  return `<article class="card planSimple"><div class="planRoundHead"><div><div class="eyebrow">Runde ${e(x.gw)}</div><div class="planRoundTitle">${action}</div></div><span class="planConfidence">RULLERENDE</span></div><div class="planMetricGrid compact"><div><b>${Number(x.expected_score_with_captain||0).toFixed(1)} p</b><span>forventet inkl. kaptein</span></div><div><b>${e(x.captain||'—')}</b><span>kaptein</span></div><div><b>${e(x.free_transfers_after)}</b><span>FT etter</span></div><div><b>${cash(x.bank_after)}</b><span>bank etter</span></div></div><div class="why"><div class="whyItem"><b>Hvorfor:</b> ${why}</div><div class="whyItem"><b>Kan endres hvis:</b> ${change}</div></div></article>`;
}
function legacyCard(x){let a=x.action||{},score=Number(x.xi_xp||0);return `<article class="card"><div class="planrow"><div><div class="eyebrow">Runde ${e(x.gw)}</div><b>${e(a.label||'Ingen handling')}</b></div><div><b>${score.toFixed(1)} p</b><div class="muted">forventet lagscore</div></div></div><div class="planMeta">Kaptein: ${e(x.captain||'—')}</div></article>`}
function renderPlan(){
  if(typeof D==='undefined'||!D)return;
  const box=document.querySelector('#future');if(!box)return;
  const pp=D.post_transfer_plan||{};
  if(pp.active&&Array.isArray(pp.steps)){
    box.innerHTML=pp.steps.map(postCard).join('');
    const intro=document.querySelector('#plan .tabExplain span');if(intro)intro.textContent='Dette er neste beste rute fra troppen du eier nå. Planen beregnes på nytt før hver deadline.';
    const sum=document.querySelector('#planBudgetSummary');if(sum)sum.innerHTML=`<div class="squadBar"><div><b>GW${e(pp.starting_gw)}</b><span>PLAN STARTER</span></div><div><b>${e(pp.starting_free_transfers)} FT</b><span>VED START</span></div><div><b>${cash(pp.starting_bank)}</b><span>BANK</span></div></div>`;
    return;
  }
  box.innerHTML=(D.future||[]).map(legacyCard).join('')||'<div class="card muted">Ingen fler-runders plan tilgjengelig.</div>';
}
window.addEventListener('load',()=>setTimeout(renderPlan,350));
})();