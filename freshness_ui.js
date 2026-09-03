(()=>{
const actionsUrl='https://github.com/jesteen90-cell/Dashbordje90/actions/workflows/refresh.yml';
const fmtTime=value=>value?new Date(value).toLocaleTimeString('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}):'—';
const ageText=minutes=>minutes<1?'akkurat nå':minutes<60?`${minutes} min siden`:`${Math.floor(minutes/60)} t ${minutes%60} min siden`;
function paint(root,generatedAt){
 const generated=generatedAt?new Date(generatedAt):null,minutes=generated&&!Number.isNaN(generated.getTime())?Math.max(0,Math.floor((Date.now()-generated.getTime())/60000)):null;
 const state=minutes===null?'unknown':minutes<=25?'fresh':minutes<=50?'aging':'stale';
 const title=state==='fresh'?'Dataene er ferske':state==='aging'?'Litt eldre enn normalt':state==='stale'?'Dataene bør sjekkes':'Ukjent datatid';
 root.dataset.state=state;
 root.querySelector('[data-fresh-title]').textContent=title;
 root.querySelector('[data-fresh-age]').textContent=minutes===null?'Tidspunkt mangler':`${ageText(minutes)} · kl. ${fmtTime(generatedAt)}`;
}
async function run(){try{
 const response=await fetch(`data.json?freshness=${Date.now()}`,{cache:'no-store'});if(!response.ok)return;const data=await response.json(),hero=document.querySelector('.hero');if(!hero)return;
 const root=document.createElement('section');root.className='freshnessCard';root.setAttribute('aria-label','Datastatus');
 root.innerHTML=`<div class="freshnessMain"><span class="freshnessDot" aria-hidden="true"></span><div><span class="eyebrow">Datastatus</span><b data-fresh-title>Laster…</b><small data-fresh-age></small><small>Automatisk analyse omtrent hvert 15. minutt</small></div></div><div class="freshnessActions"><button type="button" data-get-latest>Hent siste data</button><a href="${actionsUrl}" target="_blank" rel="noopener">Kjør ny analyse</a></div><p><b>Hent siste data</b> laster nyeste publiserte resultat. <b>Kjør ny analyse</b> åpner GitHub; trykk «Run workflow» der.</p>`;
 hero.appendChild(root);paint(root,data.generated_at);
 root.querySelector('[data-get-latest]').addEventListener('click',()=>{const url=new URL(location.href);url.searchParams.set('oppdater',Date.now());location.assign(url.toString())});
 setInterval(()=>paint(root,data.generated_at),30000);
}catch(error){console.error('freshness UI failed',error)}}
window.addEventListener('load',()=>setTimeout(run,650));
})();
