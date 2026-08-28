(()=>{
  const money=v=>{const n=Number(v);return Number.isFinite(n)?`£${n.toFixed(1)}m`:'—'};
  const el=id=>document.getElementById(id);
  const tile=(value,label,accent='')=>`<div class="budgetTile ${accent}"><b>${value}</b><span>${label}</span></div>`;
  async function run(){
    try{
      const r=await fetch(`data.json?budget=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;
      const d=await r.json(),b=d.budget||{},ft=Number(d.free_transfers_assumed||0),cands=d.candidates||[],first=cands[0]||{},future=d.future||[];
      const liveSale=b.selling_value_live===true;
      const teamValue=liveSale?b.squad_selling_value:b.squad_market_value;
      const teamLabel=liveSale?'faktisk salgsverdi':'lagverdi (markedspris)';
      const hero=el('heroBudget');
      if(hero)hero.innerHTML=tile(ft||'—','gratisbytte'+(ft===1?'':'r'),'good')+tile(money(b.bank),'i banken','money')+tile(money(teamValue),teamLabel)+tile(money(b.market_budget_total),'total markedsverdi');
      const move=el('transferBudgetSummary');
      if(move){
        const after=Number(first.bank_after),hasAfter=Number.isFinite(after);
        move.innerHTML=`<div class="budgetCard"><div><div class="eyebrow">Budsjett før bytte</div><strong>${money(b.bank)}</strong><span>${ft||'—'} gratisbytte${ft===1?'':'r'} tilgjengelig</span></div><div><div class="eyebrow">Beste forslag</div><strong>${hasAfter?money(after):'—'}</strong><span>${hasAfter?'bank etter forslag':'bank etter forslag beregnes når byttet er kjent'}</span></div><div><div class="eyebrow">Lagverdi</div><strong>${money(teamValue)}</strong><span>${teamLabel}</span></div></div>`;
      }
      const plan=el('planBudgetSummary');
      if(plan){
        const last=future.length?future[future.length-1]:null,planned=last&&Number.isFinite(Number(last.bank))?Number(last.bank):null;
        plan.innerHTML=`<div class="budgetCard compact"><div><div class="eyebrow">Startbank</div><strong>${money(b.bank)}</strong></div><div><div class="eyebrow">Bank etter planen</div><strong>${planned===null?'—':money(planned)}</strong></div><div><div class="eyebrow">Total markedsverdi</div><strong>${money(b.market_budget_total)}</strong></div></div>`;
      }
    }catch(_e){}
  }
  run();
})();
