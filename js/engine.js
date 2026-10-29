/* Constants, grading engine (rules v1.2) and data helpers. */
const DIMS=['1','2','3','4','5','6'];
const DIMN={'1':'Customer Obsession','2':'Resisting Proxies','3':'Embracing External Trends','4':'High-Velocity Decision-Making','5':'Building over Protecting','6':'Liquidity and Capital Management'};
const LV={A:5,B:4,C:3,D:2,F:1}, VL={5:'A',4:'B',3:'C',2:'D',1:'F'};
/* Company-specific globals, recomputed whenever a view is loaded (the framework base or a company from the backend) */
let IDS, DIM_OF, MODES, CO, COFULL, TK, PEERS, PEERFULL;
function setData(view){
  D=view; IDS=Object.keys(D.ind).filter(i=>/^\d+\.\d+$/.test(i)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
  DIM_OF={}; IDS.forEach(i=>DIM_OF[i]=i[0]);
  MODES=D.modes; CO=D.meta.short||D.meta.company; COFULL=D.meta.company; TK=D.meta.ticker; PEERS=D.meta.peer_short; PEERFULL=D.meta.peers;
}
setData(D);
/* An inside-out result exists only once the backend has scored the board's own uploaded material */
function ioFinal(){ return !!D.io; }
const DRAFT='DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use.';
const $=s=>document.querySelector(s);
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/(\w)'(\w)/g,'$1’$2').replace(/(\w)'(\s)/g,'$1’$2'); }
function codes(s){ return esc(s).replace(/\[((?:IO|SA|[A-Z])\d{2,3})\]/g,(m,c)=>'<button class="code" data-act="ev" data-c="'+c+'">'+c+'</button>'); }
function gval(g){ return LV[g]||0; }
function labelOf(g){ const b=D.scale.find(b=>b.grade===g); return b?b.label:''; }
function toGrade(avg){ for(const b of D.scale) if(avg>=b.min-1e-9) return [b.grade,b.label]; return ['F','Day 2 entrenched']; }
/* Coverage a dimension needs to be reported: half outside-in, two-thirds inside-out (the framework's 0.67) */
const THR={oi:0.5,io:2/3};
function compute(sc,thr){
  const dims={};
  DIMS.forEach(d=>{
    const ids=IDS.filter(i=>DIM_OF[i]===d), v=ids.map(i=>sc[i]).filter(x=>x!=null), n=v.length, m=ids.length;
    let r={assessed:n,of:m,reported:false,grade:null,avg:null,label:'Insufficient evidence'};
    if(n>0&&n/m>=thr-0.005){  /* tolerance so a rounded 0.67 still accepts 2 of 3 */ const a=v.reduce((x,y)=>x+y,0)/n, gl=toGrade(a); r={assessed:n,of:m,avg:+a.toFixed(2),grade:gl[0],label:gl[1],reported:true}; }
    dims[d]=r;
  });
  const L=DIMS.filter(d=>dims[d].reported).map(d=>dims[d].grade);
  let o={n:L.length,grade:null,provisional:false,label:'No overall grade'};
  if(L.length>=3){ const avg=L.reduce((s,g)=>s+LV[g],0)/L.length, g=VL[Math.ceil(avg-0.5-1e-9)]; o={n:L.length,grade:g,avg:+avg.toFixed(2),provisional:L.length===3,label:labelOf(g)}; }
  return {dims,overall:o,assessed:IDS.filter(i=>sc[i]!=null).length};
}
function saDim(d){ return D.q.map((x,i)=>[x[0],i+1]).filter(x=>x[0]===d).map(x=>x[1]); }
function saAnswered(d){ return saDim(d).every(n=>(S.answers[n]||'').trim().length>0); }
/* Inside-out re-scoring (skill Part D) is done by the backend from the material supplied: a cell it re-scored cites that
   material; every other indicator carries its outside-in score forward. */
function ioCell(id){
  const o=D.ind[id], c=(D.io&&D.io.cells||{})[id];
  if(c) return {score:c.score,conf:c.conf,rat:c.rationale,ev:c.ev||[],carried:!!c.carried,src:c.carried?'carried forward':'board documents'};
  return {score:o.score,conf:o.conf,rat:'Carried forward: nothing supplied settles this indicator, so the outside-in score stands.',ev:o.ev,carried:true,src:'carried forward'};
}
function M(){
  const oiSc={},ioSc={}; IDS.forEach(i=>{oiSc[i]=D.ind[i].score; ioSc[i]=ioCell(i).score;});
  const m={oiSc,ioSc,oi:compute(oiSc,THR.oi),io:compute(ioSc,THR.io),peers:[]};
  PEERS.forEach((n,p)=>{ const sc={}; IDS.forEach(i=>sc[i]=D.peers[p].ind[i].score); m.peers.push({name:n,full:PEERFULL[p],sc,c:compute(sc,THR.oi)}); });
  return m;
}
function historyFromRun(run){
  /* Port of load_history.py summarise(): one compact entry per prior run file. */
  if(!run||!run.run||!Array.isArray(run.subjects)) throw new Error('not a run file');
  if(run.run.simulated) throw new Error('simulated assessments cannot be used for trend');
  if(String(run.run.rule_version)!==String(FW.rule_version)) throw new Error('rule version '+run.run.rule_version+' differs from '+FW.rule_version+'; re-run before comparing');
  const subj=run.subjects.find(s=>s.role==='company'); if(!subj) throw new Error('no company subject');
  const oi={},io={}; let hasIO=false;
  IDS.forEach(i=>{ const c=(subj.indicators||{})[i]||{}; oi[i]=c.board&&c.board.score!=null?c.board.score:null; if(c.board_io){ hasIO=true; io[i]=c.board_io.score!=null?c.board_io.score:null; } });
  const a=compute(oi,THR.oi), b=hasIO?compute(io,THR.io):null, c=hasIO?b:a;
  return {period:run.run.period,stage:run.run.stage,ind:hasIO?io:oi,dims:c.dims,overall:c.overall,oiOverall:a.overall,actions:run.actions||[]};
}
function buildHistory(){
  /* the earlier assessments on file that the user picked (up to two), never the current period */
  S.history=(D.priors||[]).filter(p=>S.priorSel.indexOf(p.period)>=0&&p.period!==S.period).map(p=>{ const c=compute(p.scores,p.stage==='inside_out'?THR.io:THR.oi);
    return {period:p.period,stage:p.stage,ind:p.scores,dims:c.dims,overall:c.overall,actions:p.actions}; }).sort((a,b)=>a.period<b.period?-1:1).slice(-2);
}
function priorActionsList(){
  if(D.io&&D.io.prior_actions&&D.io.prior_actions.length) return D.io.prior_actions.map(a=>({id:a.id,heading:a.heading,status:a.status,note:a.note,metrics:a.metrics}));
  const last=S.history.length?S.history[S.history.length-1]:null;
  if(last&&last.actions&&last.actions.length) return last.actions.map(a=>({id:a.id,heading:a.heading,status:'no_public_evidence',note:'Status needs the action tracker or minutes; none supplied in this run.',metrics:(a.measures||[]).join('; ')}));
  return [];
}
/* ---- Guardrails (references/guardrails.md): board as a body, non-accusatory, no legal conclusions or investment advice ---- */
const RUN_CIRC={director_request:'Requesting director and engagement team',internal_dry_run:'A&M team only',methodology_pilot:'Methodology team only'};
function guardrailScan(text){
  const w=[], t=text||'';
  if(/\b(Mr|Mrs|Ms|Mx|Dr|Prof)\.?\s+[A-Z][a-z]+/.test(t)||/\b(director|chair|chairman|CEO|CFO)\s+[A-Z][a-z]+\s+[A-Z][a-z]+/.test(t)) w.push('Names an individual. Grades apply to the board as a body; refer to roles or the board.');
  if(/\b(incompetent|corrupt|lazy|dishonest|lying|liar)\b/i.test(t)) w.push('Characterises people. Keep language evidence-based and non-accusatory.');
  if(/breach(ed|es)?\s+(of\s+|its\s+|their\s+|the\s+)?(fiduciary\s+)?dut|\bfraud|\billegal|\bunlawful|negligen|\bliable\b|violat(ed|ion) of (the )?(law|securities)/i.test(t)) w.push('Reads as a legal conclusion. Describe what the record shows instead.');
  if(/\b(buy|sell|short)\s+(the\s+)?(stock|shares)|price target|will (rise|fall|outperform|underperform)|undervalued|overvalued/i.test(t)) w.push('Reads as investment advice or a share-price view.');
  return w;
}
function languageWarnings(){ const out=[]; for(let n=1;n<=D.q.length;n++){ const a=S.answers[n]; if(a&&a.trim()) guardrailScan(a).forEach(m=>out.push({q:n,msg:m})); } return out; }
/* ---- Questionnaire return: port of parse_questionnaire.py (reads the .docx in the browser) ---- */
async function readZipEntry(buf,name){
  const dv=new DataView(buf), u8=new Uint8Array(buf); let eocd=-1;
  for(let i=buf.byteLength-22;i>=0;i--){ if(dv.getUint32(i,true)===0x06054b50){ eocd=i; break; } }
  if(eocd<0) throw new Error('not a zip file');
  const n=dv.getUint16(eocd+10,true); let p=dv.getUint32(eocd+16,true);
  for(let k=0;k<n;k++){
    if(dv.getUint32(p,true)!==0x02014b50) break;
    const method=dv.getUint16(p+10,true), csize=dv.getUint32(p+20,true), nl=dv.getUint16(p+28,true), el=dv.getUint16(p+30,true), cl=dv.getUint16(p+32,true), off=dv.getUint32(p+42,true);
    const nm=new TextDecoder().decode(u8.subarray(p+46,p+46+nl));
    if(nm===name){
      const lnl=dv.getUint16(off+26,true), lel=dv.getUint16(off+28,true), start=off+30+lnl+lel, data=u8.subarray(start,start+csize);
      if(method===0) return new TextDecoder().decode(data);
      const ds=new DecompressionStream('deflate-raw'), w=ds.writable.getWriter(); w.write(data); w.close();
      return await new Response(ds.readable).text();
    }
    p+=46+nl+el+cl;
  }
  throw new Error(name+' not found');
}
async function parseQuestionnaire(file){
  const xml=await readZipEntry(await file.arrayBuffer(),'word/document.xml');
  const W='http://schemas.openxmlformats.org/wordprocessingml/2006/main', doc=new DOMParser().parseFromString(xml,'application/xml');
  const body=doc.getElementsByTagNameNS(W,'body')[0], tables=Array.from(body.children).filter(x=>x.localName==='tbl').slice(1);
  const cellText=tc=>Array.from(tc.getElementsByTagNameNS(W,'p')).map(p=>Array.from(p.getElementsByTagNameNS(W,'t')).map(t=>t.textContent).join('')).join('\n').trim();
  const answers=[], ratings={}; let qi=0;
  tables.forEach(t=>{ const row=t.getElementsByTagNameNS(W,'tr')[0], cells=Array.from(row.children).filter(c=>c.localName==='tc');
    if(cells.length===1&&qi<D.q.length){ let txt=cellText(cells[0]); if(txt.indexOf('Your answer:')===0) txt=''; answers.push(txt); qi++; }
    else if(cells.length===4&&qi>0){ const d=D.q[qi-1][0]; [[1,1],[2,3],[3,5]].forEach(kv=>{ if(cellText(cells[kv[0]]).indexOf('\u2612')>=0) ratings[d]=kv[1]; }); } });
  if(answers.length<D.q.length) throw new Error('expected '+D.q.length+' questions, found '+answers.length);
  return {answers:answers,ratings:ratings};
}
function evOf(c){
  const iev=(D.io&&D.io.ev)||{};
  return D.ev[c]||iev[c]||null;
}
function loadSaved(){ try{ return JSON.parse(localStorage.getItem('d1d2:runs2')||'[]'); }catch(e){ return []; } }
function saveRun(entry){ try{ const a=loadSaved().filter(r=>!(r.company===entry.company&&r.period===entry.period&&r.stage===entry.stage)); a.push(entry); localStorage.setItem('d1d2:runs2',JSON.stringify(a)); return true; }catch(e){ return false; } }
function indName(i){ return D.ind[i].name; }
function dimName(d){ return DIMN[d]; }
function gchip(g){ return '<span class="g g'+esc(g||'NA')+'">'+esc(g||'n/a')+'</span>'; }
function schip(s){ return s==null?'<span class="g gNA">n/a</span>':'<span class="g s'+esc(s)+'">'+esc(s)+'</span>'; }
function arrow(now,prev){ if(!now||!prev) return ''; const d=gval(now)-gval(prev); return d>0?'<span class="delta up">▲ up from '+esc(prev)+'</span>':d<0?'<span class="delta dn">▼ down from '+esc(prev)+'</span>':'<span class="muted">▬ unchanged</span>'; }
function ioSummaryLine(i){ const c=ioCell(i); return c; }
/* Not-assessable split by cause, as in grade.py coverage. */
function causeSplit(sc){ const sp={}; FW.na_causes.forEach(k=>sp[k]=0); IDS.forEach(i=>{ if(sc[i]==null){ const c=(D.ind[i]||{}).na; sp[c&&sp[c]!==undefined?c:FW.na_causes[0]]++; } }); return sp; }
