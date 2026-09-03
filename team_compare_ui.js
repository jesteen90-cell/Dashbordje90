(()=>{
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const score=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1)} p`:'—';
const nameById=(rows,id)=>(rows||[]).find(x=>Number(x.id)===Number(id))?.name||'—';
function formation(rows){return ['DEF','MID','FWD'].map(pos=>(rows||[]).filter(x=>x.position===pos).length).join('-')}
function visual(rows,source){return (rows||[]).map(p=>({...p,captain:!!(p.captain||p.optimal_captain||Number(p.id)===Number(source?.captain_id)),vice:!!(p.vice||p.optimal_vice||Number(p.id)===Number(source?.vice_id))}))}
function transferHtml(action){
 const pairs=action?.pairs||[];
 if(!pairs.length)return '<div class="teamAction bank"><b>Ingen bytter</b><span>Du beholder troppen og gratisbyttet.</span></div>';
 return `<div class="teamAction"><div><span>UT</span><b>${pairs.map(x=>esc(x.out?.name||'—')).join(' + ')}</b></div><i>→</i><div><span>INN</span><b>${pairs.map(x=>esc(x.in?.name||'—')).join(' + ')}</b></div>${Number(action.hit||0)?`<em>−${Number(action.hit)} p</em>`:'<em>0 p</em>'}</div>`;
}
function metaHtml(view){
 const rows=view.lineup||[],captain=nameById(rows,view.captain_id)||rows.find(x=>x.captain)?.name;
 return `<div class="lineupMeta"><div><span>Formasjon</span><b>${esc(view.formation||formation(rows))}</b></div><div><span>Kaptein</span><b>${esc(captain)} (C)</b></div><div><span>Forventet</span><b>${score(view.expected_team_score)}</b></div></div>`;
}
function renderView(root,views,index,action){
 const view=views[index],lineup=visual(view.lineup,view),bench=visual(view.bench,view),incoming=new Set((action?.pairs||[]).map(x=>Number(x.in?.id))),outgoing=new Set((action?.pairs||[]).map(x=>Number(x.out?.id)));
 root.querySelectorAll('[role="tab"]').forEach((button,i)=>{button.classList.toggle('active',i===index);button.setAttribute('aria-selected',String(i===index))});
 const stage=root.querySelector('.lineupStage');if(!stage||typeof pitch!=='function'||typeof benchHtml!=='function')return;
 stage.innerHTML=`<article class="lineupIntro"><div><span>${esc(view.kicker)}</span><h2>${esc(view.title)}</h2><p>${esc(view.description)}</p></div></article>${index===2?transferHtml(action):''}${metaHtml(view)}<div class="section lineupPitch"><div class="pitch">${pitch(lineup,index===2?outgoing:new Set(),index===2?incoming:new Set())}</div></div><div class="benchLabel"><b>Anbefalt benkerekkefølge</b><span>1 · 2 · 3 · keeper</span></div><div class="bench">${benchHtml(bench,index===2?outgoing:new Set(),index===2?incoming:new Set())}</div>`;
}
async function run(){try{
 const response=await fetch(`data.json?teams=${Date.now()}`,{cache:'no-store'});if(!response.ok)return;const d=await response.json(),root=document.getElementById('teamCompare'),team=document.getElementById('team');if(!root||typeof pitch!=='function')return;
 const confirmed=d.confirmed_fpl||{},current=d.optimal_current_lineup||{},selected=d.selected_package_lineup||{},action=d.action_package_selection?.selected||{pairs:[]},gw=Number(d.gameweek||d.gw||current.gw||0);
 if((confirmed.lineup||[]).length!==11||(current.lineup||[]).length!==11||(selected.lineup||[]).length!==11)return;
 const selectedBank=action.kind==='bank';
 const views=[
  {...confirmed,kicker:`Troppen nå · lagret GW${confirmed.gw||'—'}`,title:'Sist lagret i FPL',description:'Dette er lagbildet som faktisk er hentet fra FPL-kontoen din.'},
  {...current,kicker:`Neste runde · GW${gw}`,title:'Beste XI uten bytte',description:'Slik bør du stille med spillerne du allerede eier.'},
  {...selected,kicker:`Neste runde · GW${gw}`,title:selectedBank?'Beste XI når du sparer':'Beste XI med forslaget',description:selectedBank?'Motoren velger å spare. Laget er derfor det samme, men startelleveren er optimalisert.':'Dette er laget etter nøyaktig samme byttepakke som vurderes i Valget-fanen.'}
 ];
 root.innerHTML=`<div class="teamHeader"><span class="eyebrow">Tre lagbilder · ett tydelig valg</span><h1>Se hva som faktisk endres</h1><p>Bytt mellom troppen som er lagret, beste lag uten bytte og laget etter motorens forslag.</p></div><div class="lineupTabs" role="tablist" aria-label="Velg lagbilde"><button role="tab" aria-selected="false">Troppen nå</button><button role="tab" aria-selected="true">XI uten bytte</button><button role="tab" aria-selected="false">${selectedBank?'XI ved sparing':'XI med forslag'}</button></div><div class="lineupStage"></div>`;
 root.querySelectorAll('[role="tab"]').forEach((button,index)=>button.addEventListener('click',()=>renderView(root,views,index,action)));
 team.classList.add('compareReady');renderView(root,views,1,action);
 }catch(error){console.error('team comparison failed',error)}}
window.addEventListener('load',()=>setTimeout(run,500));
})();
