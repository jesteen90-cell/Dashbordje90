(()=>{
  const money=v=>{const n=Number(v);return Number.isFinite(n)?`£${n.toFixed(1)}m`:'—'};
  const el=id=>document.getElementById(id);
  const tile=(value,label,accent='')=>`<div class="budgetTile ${accent}"><b>${value}</b><span>${label}</span></div>`;
  const hitCost=(move,ft)=>{const t=Number(move?.transfers||move?.pairs?.length||0);return Math.max(0,t-Number(ft||0))*4};
  const pressureClass=s=>Number(s?.score||0)>=.55?'up':Number(s?.score||0)<=-.55?'down':'neutral';
  function decorateTransferCards(d){
    const cards=[...document.querySelectorAll('#transfers article.card')],cands=d.candidates||[];
    if(!cards.length)return false;
    cards.forEach((card,i)=>{
      card.querySelectorAll('.budgetLine,.exactBudgetLine,.timingLine').forEach(x=>x.remove());
      const c=cands[i]||{},after=Number(c.bank_after);
      if(Number.isFinite(after)){
        const cost=hitCost({transfers:(c.pairs||[]).length},d.free_transfers_assumed);
        const box=document.createElement('div');box.className='exactBudgetLine';
        box.innerHTML=`<b>Bank etter byttet: ${money(after)}</b><span>${cost?` · poengkostnad -${cost}`:' · 0 poeng i byttehit'}</span>`;
        const stats=card.querySelector('.stats');card.insertBefore(box,stats||null);
      }
      const mt=c.market_timing||{},incoming=mt.incoming,outgoing=mt.outgoing,notes=c.timing_notes||[];
      if(incoming||outgoing||notes.length){
        const line=document.createElement('div');line.className='timingLine';
        const inTxt=incoming?`Inn: ${incoming.label}`:'';
        const outTxt=outgoing?`Ut: ${outgoing.label}`:'';
        const flex=c.budget_flexibility?.grade?`Budsjettfleks: ${c.budget_flexibility.grade}`:'';
        line.innerHTML=`<div>${inTxt?`<span class="signal ${pressureClass(incoming)}">${inTxt}</span>`:''}${outTxt?`<span class="signal ${pressureClass(outgoing)}">${outTxt}</span>`:''}${flex?`<span class="signal neutral">${flex}</span>`:''}</div>${notes.length?`<small>${notes.join(' · ')}</small>`:''}`;
        card.appendChild(line);
      }
    });
    return true;
  }
  async function run(){
    try{
      const r=await fetch(`data.json?budget=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;
      const d=await r.json(),b=d.budget||{},bi=d.budget_intelligence||{},ft=Number(d.free_transfers_assumed||0),cands=d.candidates||[],first=cands[0]||{},future=d.future||[],plan0=(d.optimizer?.plan||[])[0]||{};
      const liveSale=b.selling_value_live===true;
      const teamValue=liveSale?b.squad_selling_value:b.squad_market_value;
      const teamLabel=liveSale?'faktisk salgsverdi':'lagverdi (markedspris)';
      const cost=hitCost(plan0,ft);
      const hero=el('heroBudget');
      if(hero)hero.innerHTML=tile(ft||'—','gratisbytte'+(ft===1?'':'r'),'good')+tile(`${cost} p`,'kostnad anbefalt trekk',cost?'warn':'good')+tile(money(b.bank),'i banken','money')+tile(money(teamValue),teamLabel);
      const move=el('transferBudgetSummary');
      if(move){
        const after=Number(first.bank_after),hasAfter=Number.isFinite(after),flex=bi.flexibility||{},watch=(bi.watchlist||[])[0];
        const watchText=watch?`${watch.name}: ${watch.signal?.label||'rolig'} · ${money(watch.bank_after)} etter byttet`:'Ingen tydelig prispress blant toppforslagene';
        move.innerHTML=`<div class="budgetCard"><div><div class="eyebrow">Nå</div><strong>${money(b.bank)}</strong><span>${ft||'—'} gratisbytte${ft===1?'':'r'} · anbefalt trekk koster ${cost} poeng</span></div><div><div class="eyebrow">Beste forslag</div><strong>${hasAfter?money(after):'—'}</strong><span>${hasAfter?'bank etter forslaget':'bank etter forslag beregnes når byttet er kjent'}</span></div><div><div class="eyebrow">Lagverdi</div><strong>${money(teamValue)}</strong><span>${teamLabel}${liveSale?'':' · salgsverdi kan være lavere'}</span></div></div><div class="budgetIntel"><div><b>Budsjettintelligens</b><span class="shadowTag">SHADOW</span></div><p>Fleksibilitet nå: <strong>${flex.grade||'—'}</strong> · ${flex.note||''}</p><p>Premium-bundet: <strong>${Number(bi.premium_share_pct||0).toFixed(1)}%</strong> (${money(bi.premium_locked_value)})</p><p>Prispress: ${watchText}</p><small>Prispress endrer ikke anbefalingen ennå. Poeng og fler-GW-plan har prioritet.</small></div>`;
      }
      const plan=el('planBudgetSummary');
      if(plan){
        const last=future.length?future[future.length-1]:null,planned=last&&Number.isFinite(Number(last.bank))?Number(last.bank):null;
        plan.innerHTML=`<div class="budgetCard compact"><div><div class="eyebrow">Startbank</div><strong>${money(b.bank)}</strong></div><div><div class="eyebrow">Bank etter planen</div><strong>${planned===null?'—':money(planned)}</strong></div><div><div class="eyebrow">Total markedsverdi</div><strong>${money(b.market_budget_total)}</strong></div></div>`;
      }
      let tries=0,t=setInterval(()=>{tries++;if(decorateTransferCards(d)||tries>8)clearInterval(t)},150);
    }catch(_e){}
  }
  run();
})();
