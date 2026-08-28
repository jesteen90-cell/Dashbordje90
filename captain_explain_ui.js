(function(){
  function pct(v){return v==null?'—':Math.round(Number(v)*100)+'%'}
  function num(v,d=2){return v==null?'—':Number(v).toFixed(d)}
  function haulStrip(row){
    if(!row || row.p10_plus==null) return '';
    return `<div class="haulStrip" style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-top:8px"><div style="text-align:center;padding:5px 2px;border-radius:8px;background:#0002"><b style="display:block;font-size:11px">${pct(row.p10_plus)}</b><span style="font-size:7px;color:#aaa2ba">10+</span></div><div style="text-align:center;padding:5px 2px;border-radius:8px;background:#0002"><b style="display:block;font-size:11px">${pct(row.p15_plus)}</b><span style="font-size:7px;color:#aaa2ba">15+</span></div><div style="text-align:center;padding:5px 2px;border-radius:8px;background:#0002"><b style="display:block;font-size:11px">${pct(row.p_goal_2plus)}</b><span style="font-size:7px;color:#aaa2ba">2+ mål</span></div><div style="text-align:center;padding:5px 2px;border-radius:8px;background:#0002"><b style="display:block;font-size:11px">${pct(row.p_multi_return)}</b><span style="font-size:7px;color:#aaa2ba">multi</span></div></div>`;
  }
  function addCardHaul(e){
    const rows=[e.captain||{},e.runner_up||{}];
    document.querySelectorAll('#captains .captCard').forEach(card=>{
      if(card.querySelector('.haulStrip')) return;
      const name=(card.querySelector('.captName')?.textContent||'').trim();
      const row=rows.find(x=>String(x.name||'').trim()===name);
      if(!row || row.p10_plus==null) return;
      card.insertAdjacentHTML('beforeend',haulStrip(row));
      if(row.id===e.captain?.id){
        card.style.borderColor='#00e99088';
        card.style.boxShadow='0 0 0 1px #00e99018 inset';
      }
    });
  }
  function render(){
    if(!window.D || !D.captain_explanation) return;
    const e=D.captain_explanation,c=e.captain||{},r=e.runner_up||{};
    const host=document.querySelector('#captains');
    if(!host) return;
    addCardHaul(e);
    if(document.querySelector('#captainExplain')) return;
    const box=document.createElement('div');
    box.id='captainExplain';
    box.style.cssText='grid-column:1/-1;margin-top:2px;padding:13px;border-radius:17px;border:1px solid #00e99044;background:linear-gradient(145deg,#00e9900d,#ffffff08);';
    const haul=(c.p10_plus!=null)?`<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px"><div class="mini"><b>${pct(c.p10_plus)}</b><span>10+ poeng</span></div><div class="mini"><b>${pct(c.p15_plus)}</b><span>15+ poeng</span></div><div class="mini"><b>${pct(c.p_goal_2plus)}</b><span>2+ mål</span></div><div class="mini"><b>${pct(c.p_multi_return)}</b><span>flere returns</span></div></div>`:'';
    box.innerHTML=`<div class="eyebrow">Hvorfor kaptein?</div><div style="display:flex;justify-content:space-between;gap:10px;align-items:end"><div><div style="font-size:20px;font-weight:950">${c.name||'—'} (C)</div><div class="muted" style="font-size:11px">${c.team||''} · modell ${e.model||'—'}</div></div><div style="text-align:right"><b>${num(c.xp)} xP</b><div class="muted" style="font-size:10px">${num(c.expected_minutes,0)} min · ${pct(c.availability)}</div></div></div>${haul}<div style="margin-top:10px;padding:9px 10px;border-radius:12px;background:#0002;font-size:11px"><b>Mot #2 ${r.name||'—'}:</b> modellgap ${e.score_gap==null?'—':(Number(e.score_gap)>=0?'+':'')+num(e.score_gap,3)} · xP-gap ${e.xp_gap==null?'—':(Number(e.xp_gap)>=0?'+':'')+num(e.xp_gap)}. ${e.selected_pick_safe?'Består':'Består ikke'} sikkerhetsgaten for minutter/availability.</div>`;
    host.appendChild(box);
  }
  window.addEventListener('load',()=>{setTimeout(render,350);setTimeout(render,1200)});
  new MutationObserver(()=>render()).observe(document.documentElement,{childList:true,subtree:true});
})();
