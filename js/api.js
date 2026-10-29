/* Backend client (server/app.py). Companies live on the server; without it (file:// or a plain static server) the app
   opens with the framework only (js/data/base.js) and no companies. */
const BASE=D;
const API={on:false,research:{enabled:false,reason:'The assessment service is not connected.'},companies:[]};
async function api(path,opts){
  const r=await fetch('/api'+path,Object.assign({headers:{'Content-Type':'application/json'}},opts||{}));
  let j=null; try{ j=await r.json(); }catch(e){}
  if(!r.ok){ const err=new Error((j&&(j.error||j.detail))||('Request failed ('+r.status+')')); err.status=r.status; err.problems=j&&j.problems; err.job_id=(j&&j.job_id)||null; throw err; }
  return j;
}
const post=(path,body)=>api(path,{method:'POST',body:JSON.stringify(body)});
/* Start a background job; if the server says one is already running (409 with its job_id), follow that one instead */
async function startJob(path,body){
  try{ return await post(path,body); }
  catch(e){ if(e.status===409&&e.job_id) return {job_id:e.job_id,attached:true}; throw e; }
}
function useOffline(){ API.on=false; API.companies=[]; S.company=null; setData(BASE); }
async function apiInit(){
  if(location.protocol==='file:'){ useOffline(); return; }
  try{ const h=await api('/health'); API.on=true; API.research=h.research||API.research; }
  catch(e){ useOffline(); return; }
  /* connected: a problem loading the companies is reported, not treated as being offline */
  try{ await refreshCompanies(); if(S.company) await selectCompany(S.company); }
  catch(e){ console.error(e); toast('Could not load the companies on file: '+e.message); }
}
async function refreshCompanies(){
  API.companies=await api('/companies');
  if(!API.companies.some(c=>c.id===S.company)){ S.company=(API.companies[0]||{}).id||null; if(!S.company){ setData(BASE); resetRun(); } }
}
function companyOf(id){ return API.companies.find(c=>c.id===(id||S.company))||{}; }
/* Load one company's view (same shape as js/data/base.js, filled in) and start a fresh run on it */
/* Every upload: at most 25 MB a file (the server checks again) */
const MAX_FILE=25*2**20;
function sizeOk(files){ const big=files.filter(f=>f.size>MAX_FILE); if(big.length) toast(listJoin(big.map(f=>f.name))+': over the 25 MB limit per file, so not added.'); return files.filter(f=>f.size<=MAX_FILE); }
async function selectCompany(id){
  const v=await api('/companies/'+encodeURIComponent(id)+'/view');
  setData(v); S.company=id; S.period=v.meta.period||S.period; S.history=[]; S.priorSel=[]; S.srcf='all'; resetRun();
  S.oiDone=true; if(D.io){ S.ioDone=true; S.final=true; }
}
/* Follow a background job. A brief network drop is retried for about a minute; a job the server no longer knows
   (it was restarted, which ends running jobs) is reported in plain words. */
async function pollJob(id,onTick){
  let misses=0;
  for(;;){
    let j;
    try{ j=await api('/jobs/'+id); misses=0; }
    catch(e){
      if(/not found/i.test(e.message)) throw new Error('The assessment service was restarted, so this run stopped before it finished. Nothing was saved; please start it again.');
      if(++misses>40) throw new Error('Lost contact with the assessment service. Check that it is running, then start the run again.');
      await new Promise(r=>setTimeout(r,1500)); continue;
    }
    onTick(j);
    if(j.status==='done') return j;
    if(j.status==='error') throw new Error(j.error||'The job failed.');
    await new Promise(r=>setTimeout(r,1500));
  }
}
function fileToB64(f){ return new Promise((res,rej)=>{ const r=new FileReader(); r.onload=()=>res(String(r.result).split(',')[1]||''); r.onerror=()=>rej(r.error); r.readAsDataURL(f); }); }
