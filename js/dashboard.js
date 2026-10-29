/* Side panel ("drawer") that slides in from the right: the board dashboard and action plan for a stage.
   Also the company form shown on the outside-in page (research a new company, or import assessment files). */
function openDrawer(html,cls){
  const d=$('#drawer'); $('#drawerBody').innerHTML=html; d.className='drawer on'+(cls?' '+cls:''); document.body.classList.add('noscroll');
  const p=$('#drawerPanel'); p.scrollTop=0; setTimeout(()=>p.focus(),50);
}
function closeDrawer(){ $('#drawer').className='drawer'; document.body.classList.remove('noscroll'); S.drawer=null; }
function redrawDrawer(){ if(S.drawer==='dash') openDrawer(dashView(S.dashStage),'wide'); else if(S.drawer==='plan') openDrawer(planView(S.dashStage),'mid'); }
document.addEventListener('keydown',e=>{ if(e.key==='Escape'){ if($('#modal').classList.contains('on')) $('#modal').classList.remove('on'); else if(S.drawer) closeDrawer(); } });
function listJoin(a){ return a.length<2?a.join(''):a.slice(0,-1).join(', ')+' and '+a[a.length-1]; }
function ordinal(n){ return n+(['th','st','nd','rd'][(n%100>10&&n%100<14)?0:n%10]||'th'); }

/* ---------- dashboard ---------- */
/* Tabbed, full-width tables; every rating carries the evidence behind it (codes open the source). */
function kpi(label,value,sub,cls){ return '<div class="kpi'+(cls?' '+cls:'')+'"><div class="kl">'+label+'</div><div class="kv2v">'+value+'</div>'+(sub?'<div class="ks">'+sub+'</div>':'')+'</div>'; }
function evChips(ev){ return (ev||[]).length?' '+ev.map(c=>'<button class="code" data-act="ev" data-c="'+esc(c)+'">'+esc(c)+'</button>').join(''):''; }
/* text with its evidence codes made clickable, plus chips for any cited codes the text does not mention */
function evText(t,ev){ const x=String(t||''); return codes(x)+evChips((ev||[]).filter(c=>x.indexOf(c)<0)); }
function firstSentence(t){ t=String(t||'').trim(); const k=t.search(/\.\s/); return k>0?t.slice(0,k+1):t; }
function indLine(i){ const x=(D.ind_summary||[]).find(r=>String(r.name).split(' ')[0]===i); return x&&x.line?x.line:firstSentence(D.ind[i].rationale); }
function delta(a,b){ if(a==null||b==null||a===b) return '<td class="dl">–</td>'; const d=b-a; return '<td class="dl '+(d>0?'up':'dn')+'">'+(d>0?'▲':'▼')+'<b>'+Math.abs(d)+'</b></td>'; }
function dashTabs(io){ return [['overview','Overview'],['indicators','Indicators']].concat(io?[['inside','Inside-out changes']]:[]).concat([['peers','Peers'],['trend','Trend'],['actions','Actions']]); }
function dashView(stage){
  const m=M(), io=stage==='io', L=io?m.io:m.oi, O=m.oi, last=S.history.length?S.history[S.history.length-1]:null;
  const tabs=dashTabs(io); if(!tabs.some(t=>t[0]===S.dtab)) S.dtab='overview';
  const g=L.overall.grade||'NA', chg=io?arrow(m.io.overall.grade,O.overall.grade):(last?arrow(O.overall.grade,last.overall.grade):'');
  let h='<div class="dhd"><div class="dhl"><div class="deb">Board dashboard · '+(io?'After inside-out':'Outside-in')+'</div><h2>'+esc(COFULL)+' <span>'+esc(TK)+' · '+esc(S.period)+'</span></h2><div class="dsub">Benchmarked against '+esc(listJoin(PEERS))+'</div></div>'+
   '<div class="dhr">'+(hasFile(io?'io_html':'oi_html')?'<button class="btn ghost sm" data-act="dl" data-k="'+(io?'io_html':'oi_html')+'">'+ico('dl',15)+'Download</button>':'')+'<button class="btn ghost sm" data-act="dreport">'+ico('doc',15)+'Full report</button><button class="xbtn" data-act="dclose" aria-label="Close dashboard">×</button></div></div>';
  h+='<div class="dtabs">'+tabs.map(t=>'<button class="tab'+(S.dtab===t[0]?' on':'')+'" data-act="dtab" data-t="'+t[0]+'">'+t[1]+'</button>').join('')+'</div><div class="dbody2">';
  const T=S.dtab;
  if(T==='overview'){
    h+='<div class="kpis k2">'+
     '<div class="kpi kg"><div class="kl">Overall grade · '+(io?'after inside-out':'outside-in')+'</div><div class="kgrade"><span class="gsq g'+g+'">'+(L.overall.grade||'–')+'</span><div><b>'+esc(L.overall.label)+'</b><div class="ks">'+(L.overall.avg!=null?L.overall.avg.toFixed(2)+' of 5.00':'n/a')+'</div></div></div></div>'+
     kpi(io?'Change vs outside-in':'Change vs earlier quarter',chg||'<span class="muted">No earlier quarter selected</span>',io?'Outside-in '+gchip(O.overall.grade):(last?esc(last.period):''))+'</div>';
    h+='<div class="dcard dlead"><div class="deb2">Headline</div><p class="dlh">'+esc(io?D.io.headline:D.headline)+'</p><ol class="flist">'+findingsList(stage)+'</ol></div>';
    h+='<div class="dcard"><h3>Grades by dimension</h3><div class="scroll"><table class="dt ev"><tr><th>Dimension</th><th>Outside-in</th>'+(io?'<th>After inside-out</th>':'')+'<th>Evidence</th></tr>'+
     DIMS.map((d,k)=>'<tr><td><b>'+d+'. '+esc(DIMN[d])+'</b></td>'+gc(O.dims[d].grade)+(io?gc(m.io.dims[d].grade):'')+'<td>'+codes((D.scorecard[k]||{}).line||'')+'</td></tr>').join('')+
     '<tr class="tot"><td>Overall</td>'+gc(O.overall.grade)+(io?gc(m.io.overall.grade):'')+'<td>Rounded average of the dimension grades (A = 5 to F = 1).</td></tr></table></div></div>';
  }
  else if(T==='indicators'){
    h+='<div class="dcard"><h3>Rationale per indicator</h3><p class="ks">Each indicator is scored 1 (Day 2) to 5 (Day 1) against written anchors. Select an indicator for its definition and anchors; evidence codes open the source.</p><div class="scroll"><table class="dt ev">'+
     '<tr><th>Indicator</th><th>Outside-in</th>'+(io?'<th>After inside-out</th>':'')+'<th>Summary of the evidence</th></tr>';
    DIMS.forEach(d=>{ h+='<tr class="dimrow"><td colspan="'+(io?4:3)+'"><b>'+d+'. '+esc(DIMN[d])+'</b> &nbsp;Outside-in '+gchip(O.dims[d].grade)+(io?' &nbsp;After inside-out '+gchip(m.io.dims[d].grade):'')+'</td></tr>';
      IDS.filter(i=>DIM_OF[i]===d).forEach(i=>{ const o=D.ind[i], c=io?ioCell(i):null, moved=io&&!c.carried;
        h+='<tr><td><button class="lnk" data-act="ind" data-i="'+i+'">'+i+'</button> '+esc(o.name)+'</td>'+sc_(o.score)+(io?sc_(c.score):'')+
         '<td>'+(moved?'<b>Inside-out:</b> '+evText(firstSentence(c.rat),c.ev)+'<div class="ks">Outside-in: '+evText(indLine(i),o.ev)+'</div>':evText(indLine(i),o.ev)+(io?'<div class="ks">Carried forward: nothing supplied settles this indicator.</div>':''))+'</td></tr>'; }); });
    h+='</table></div></div>';
  }
  else if(T==='inside'){
    const ch=IDS.filter(i=>{ const c=ioCell(i); return !c.carried; });
    h+='<div class="dcard"><h3>What the board’s own material changed</h3><p class="ks">Indicators re-scored from the board documents and the directors’ anonymous self-assessment. Every other indicator keeps its outside-in score.</p>'+
     (ch.length?'<div class="scroll"><table class="dt ev"><tr><th>Indicator</th><th>Outside-in</th><th>After inside-out</th><th>Δ</th><th>Evidence that moved the score</th></tr>'+
      ch.map(i=>{ const o=D.ind[i], c=ioCell(i); return '<tr><td><button class="lnk" data-act="ind" data-i="'+i+'">'+i+'</button> '+esc(o.name)+'</td>'+sc_(o.score)+sc_(c.score)+delta(o.score,c.score)+'<td>'+evText(c.rat,c.ev)+'</td></tr>'; }).join('')+'</table></div>':'<p class="muted">No indicator was re-scored: nothing supplied settled an indicator.</p>')+'</div>';
    h+='<div class="dcard dpos"><h3>Better than the public record</h3>'+((D.io.better||[]).length?'<ul>'+D.io.better.map(x=>'<li>'+codes(x)+'</li>').join('')+'</ul>':'<p class="muted">None.</p>')+'</div>'+
     '<div class="dcard dneg"><h3>Worse than the public record</h3>'+((D.io.worse||[]).length?'<ul>'+D.io.worse.map(x=>'<li>'+codes(x)+'</li>').join('')+'</ul>':'<p class="muted">None.</p>')+'</div>';
  }
  else if(T==='peers'){
    const rows=(D.peer_table||[]).slice(1);
    h+='<div class="dcard"><h3>Peer comparison</h3><p class="ks">Peers are graded outside-in from public information with the same rubric.</p><div class="scroll"><table class="dt ev"><tr><th>Dimension</th><th>'+esc(CO)+'</th>'+PEERS.map(p=>'<th>'+esc(p)+'</th>').join('')+'<th>How the company compares</th></tr>'+
     DIMS.map((d,k)=>'<tr><td><b>'+d+'. '+esc(DIMN[d])+'</b></td>'+gc(O.dims[d].grade)+m.peers.map(p=>gc(p.c.dims[d].grade)).join('')+'<td>'+codes(((rows[k]||[])[rows[k]?rows[k].length-1:0])||'')+'</td></tr>').join('')+
     '<tr class="tot"><td>Overall</td>'+gc(O.overall.grade)+m.peers.map(p=>gc(p.c.overall.grade)).join('')+'<td>'+codes(D.position||'')+'</td></tr></table></div></div>';
    h+='<div class="dcard"><h3>Peer-relative indicators</h3><p class="ks">Scored against the named peer set.</p><div class="scroll"><table class="dt ev"><tr><th>Indicator</th><th>'+esc(CO)+'</th>'+PEERS.map(p=>'<th>'+esc(p)+'</th>').join('')+'<th>Evidence ('+esc(CO)+')</th></tr>'+
     IDS.filter(i=>(FW.peer_relative||['3.2','5.1','6.1','6.2']).indexOf(i)>=0).map(i=>'<tr><td>'+i+' '+esc(indName(i))+'</td>'+sc_(D.ind[i].score)+D.peers.map(p=>sc_(p.ind[i].score)).join('')+'<td>'+evText(indLine(i),D.ind[i].ev)+'</td></tr>').join('')+'</table></div></div>';
  }
  else if(T==='trend'){
    if(!last) h+='<div class="dcard"><h3>Trend</h3><p class="muted">No earlier quarter is selected for this readout. Choose up to two earlier assessments on the outside-in page to see the trend.</p></div>';
    else {
      const now=io?m.ioSc:m.oiSc, ch=IDS.filter(i=>last.ind[i]!=null&&now[i]!=null&&last.ind[i]!==now[i]);
      h+='<div class="dcard"><h3>Grades by quarter</h3><div class="scroll"><table class="dt cmp"><tr><th>Dimension</th>'+S.history.map(x=>'<th>'+esc(x.period)+'</th>').join('')+'<th>'+esc(S.period)+'</th>'+(io?'<th>Inside-out</th>':'')+'</tr>'+
       DIMS.map(d=>'<tr><td>'+d+'. '+esc(DIMN[d])+'</td>'+S.history.map(x=>gc(x.dims[d].grade)).join('')+gc(O.dims[d].grade)+(io?gc(m.io.dims[d].grade):'')+'</tr>').join('')+
       '<tr class="tot"><td>Overall</td>'+S.history.map(x=>gc(x.overall.grade)).join('')+gc(O.overall.grade)+(io?gc(m.io.overall.grade):'')+'</tr></table></div></div>';
      h+='<div class="dcard"><h3>What changed since '+esc(last.period)+'</h3>'+(ch.length?'<div class="scroll"><table class="dt ev"><tr><th>Indicator</th><th>Prior</th><th>Now</th><th>Δ</th><th>Evidence that moved the score</th></tr>'+
       ch.map(i=>{ const c=io?ioCell(i):null; return '<tr><td>'+i+' '+esc(indName(i))+'</td>'+sc_(last.ind[i])+sc_(now[i])+delta(last.ind[i],now[i])+'<td>'+(c&&!c.carried?evText(c.rat,c.ev):evText(D.ind[i].rationale,D.ind[i].ev))+'</td></tr>'; }).join('')+'</table></div>':'<p class="muted">No indicator score changed.</p>')+'</div>';
    }
  }
  else if(T==='actions'){
    const pal=io?priorActionsList():[];
    h+='<div class="dcard"><h3>What the board could do next</h3>'+(io?D.io.actions:D.actions).map(a=>'<div class="dact"><span>'+esc(a.n)+'</span><div><b>'+esc(a.heading)+'</b><p class="m0">'+codes(a.description)+'</p><div class="ks">Target '+esc(a.target||'–')+((a.measures||[]).length?' · '+esc(a.measures.join('; ')):'')+'</div></div></div>').join('')+'</div>';
    if(pal.length) h+='<div class="dcard"><h3>Last quarter’s actions</h3><div class="scroll"><table class="dt ev"><tr><th>Action</th><th>Status</th><th>Evidence</th></tr>'+pal.map(a=>'<tr><td>'+esc(a.heading)+'</td><td><span class="st-'+esc(a.status)+'">'+esc(a.status.replace(/_/g,' '))+'</span></td><td>'+codes(a.note||'')+'<div class="ks">'+esc(a.metrics||'')+'</div></td></tr>').join('')+'</table></div></div>';
    if((D.metrics||[]).length) h+='<div class="dcard"><h3>Metrics worth tracking</h3><div class="scroll"><table class="dt ev"><tr><th>Metric</th><th>Why it matters</th><th>Current</th></tr>'+D.metrics.map(r=>'<tr><td><b>'+esc(r[0])+'</b></td><td>'+esc(r[1])+'</td><td>'+esc(r[2])+'</td></tr>').join('')+'</table></div></div>';
  }
  h+='<div class="draft">'+DRAFT+'</div></div>';
  return h;
}
function openDash(stage){ S.drawer='dash'; S.dashStage=stage; S.dtab='overview'; openDrawer(dashView(stage),'wide'); }

/* ---------- action plan ---------- */
function planView(stage){
  const io=stage==='io', acts=io?D.io.actions:D.actions, pal=io?priorActionsList():[], back=io&&D.io.back?D.io.back:[];
  const targets=acts.map(a=>a.target).filter(Boolean).sort(), measures=acts.reduce((n,a)=>n+(a.measures||[]).length,0);
  let h='<div class="dhd"><div class="dhl"><div class="deb">Board action plan · '+(io?'After inside-out':'Outside-in')+'</div><h2>'+esc(COFULL)+' <span>'+esc(TK)+' · '+esc(S.period)+'</span></h2><div class="dsub">What the board could do next, each action tied to a finding, with measures and a target date.</div></div>'+
   '<div class="dhr">'+(hasFile(io?'io_docx':'oi_docx')?'<button class="btn ghost sm" data-act="dl" data-k="'+(io?'io_docx':'oi_docx')+'">'+ico('dl',15)+'Report (Word)</button>':'')+'<button class="xbtn" data-act="dclose" aria-label="Close action plan">×</button></div></div><div class="dbody2">';
  h+='<div class="kpis k3">'+kpi('Actions',acts.length,'Up to five per readout')+kpi('First target',esc(targets[0]||'–'),targets.length>1?'Last '+esc(targets[targets.length-1]):'')+kpi('Measures',measures,'To track progress quarter by quarter')+'</div>';
  h+=acts.map(a=>'<div class="pact"><div class="pnum">'+esc(a.n)+'</div><div class="pbody"><div class="phead"><h3>'+esc(a.heading)+'</h3><span class="ptgt">Target '+esc(a.target||'–')+'</span></div><p>'+codes(a.description)+'</p>'+
   ((a.measures||[]).length?'<div class="kl">How progress is measured</div><ul class="pmeas">'+a.measures.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+'</div></div>').join('');
  if(pal.length){
    h+='<h3 class="psec">Last quarter’s actions'+'</h3><div class="dcard">'+pal.map(a=>{ const b=back.find(x=>x.id===a.id);
      return '<div class="dact st"><i class="sd st-'+esc(a.status)+'"></i><div><b>'+esc(a.heading)+'</b><div class="ks"><span class="st-'+esc(a.status)+'">'+esc(a.status.replace(/_/g,' '))+'</span>'+(a.note?' · '+codes(a.note):'')+'</div>'+
       (b?'<details class="pback"><summary>How to get back on track</summary><div class="dbody"><p><b>What happened.</b> '+esc(b.what)+'</p><p><b>Root cause.</b> '+esc(b.cause)+'</p><p><b>To prevent it recurring.</b> '+esc(b.prevent)+'</p>'+((b.measures||[]).length?'<p><b>Measures.</b> '+esc(b.measures.join('; '))+'</p>':'')+'</div></details>':'')+'</div></div>'; }).join('')+'</div>';
  } else h+='<p class="muted">Progress on these actions is reviewed in the inside-out stage and in next quarter’s assessment.</p>';
  return h+'<div class="draft">'+DRAFT+'</div></div>';
}
function openPlan(stage){ S.drawer='plan'; S.dashStage=stage; openDrawer(planView(stage),'mid'); }

/* ---------- company form (outside-in page) ---------- */
function newAdd(tab){ return {tab:tab||'research',company:'',ticker:'',period:S.period,peers:[{name:'',ticker:''},{name:'',ticker:''}],job:null,err:'',problems:null,busy:false,files:[]}; }
function redrawAdd(){ if(S.page==='journey'&&S.stage===1&&S.sub==='setup') draw(); }
function addFields(){
  const A=S.add;
  if(A.job) return jobView(A.job);
  if(A.tab==='file') return '<div class="fgrid"><div><label for="company">Company</label><select id="company">'+API.companies.map(c=>'<option value="'+esc(c.id)+'"'+(c.id===S.company?' selected':'')+'>'+esc(coLabel(c))+'</option>').join('')+'</select></div><div><label>Ticker</label><input type="text" value="'+esc(TK)+'" readonly></div><div><label>Period</label><input type="text" value="'+esc(S.period)+'" readonly></div></div>'+
   '<label>Peers</label><div class="chips">'+PEERS.map(p=>'<span class="chip">'+esc(p)+'</span>').join('')+'</div>';
  if(A.tab==='import') return '<p class="muted">Add a company from the assessment files prepared by the A&amp;M team. They are checked against the scoring rules before the company is added, and the report and dashboard are prepared from them.</p>'+
   '<label for="a_oi">Outside-in assessment file (required)</label><div class="frow"><input type="file" id="a_oi" accept=".json"></div>'+
   '<label for="a_io">Inside-out assessment file (optional)</label><div class="frow"><input type="file" id="a_io" accept=".json"></div>'+
   '<label for="a_pr">Earlier quarters (optional, up to four)</label><div class="frow"><input type="file" id="a_pr" accept=".json" multiple></div>';
  return (API.research.enabled?'<p class="muted">The board is researched from approved public sources for the company and each peer, scored against the 22 indicators and checked against the scoring rules. It usually takes 10 to 20 minutes. To assess a company on file for a new quarter, enter it again with the new period.</p>':
    '<div class="notice">'+(API.on?'New-company research is not switched on yet. Your A&amp;M team can still add a company from its assessment files.':'Companies are held by the assessment service, which is not connected. Your A&amp;M engagement team can give you access.')+'</div>')+
   '<div class="fgrid3"><div><label for="a_company">Company</label><input type="text" id="a_company" data-add="company" value="'+esc(A.company)+'" placeholder="e.g. Microsoft Corporation"></div><div><label for="a_ticker">Ticker</label><input type="text" id="a_ticker" data-add="ticker" value="'+esc(A.ticker)+'" placeholder="MSFT"></div><div><label for="a_period">Period</label><input type="text" id="a_period" data-add="period" value="'+esc(A.period)+'" placeholder="2026-Q4"></div></div>'+
   '<label>Peers (two to five listed competitors)</label>'+A.peers.map((p,i)=>'<div class="prow"><input type="text" data-addp="name" data-i="'+i+'" value="'+esc(p.name)+'" placeholder="Peer '+(i+1)+' name" aria-label="Peer '+(i+1)+' name"><input type="text" data-addp="ticker" data-i="'+i+'" value="'+esc(p.ticker)+'" placeholder="Ticker" aria-label="Peer '+(i+1)+' ticker">'+(A.peers.length>2?'<button class="btn sec sm" data-act="rmpeer" data-i="'+i+'" aria-label="Remove peer">×</button>':'')+'</div>').join('')+
   (A.peers.length<5?'<button class="btn sec sm" data-act="addpeer">'+ico('plus',14)+'Add a peer</button>':'');
}
function addErr(){ const A=S.add; return A.err?'<div class="notice bad"><b>'+esc(A.err)+'</b>'+(A.problems&&A.problems.length?'<ul>'+A.problems.slice(0,10).map(p=>'<li>'+esc(Array.isArray(p)?p.join(' · '):(typeof p==='string'?p:JSON.stringify(p)))+'</li>').join('')+'</ul>':'')+'</div>':''; }
function jobView(j){
  const pct=Math.max(2,Math.min(100,j.progress||0));
  return '<div class="job"><div class="jt"><b id="jmsg">'+esc(j.message||'Working…')+'</b><span id="jpct">'+Math.round(pct)+'%</span></div><div class="bar2"><i id="jbar" style="width:'+pct+'%"></i></div>'+
   '<ul class="jlog" id="jlog">'+(j.log||[]).slice(-8).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>'+
   (j.status==='error'?'<div class="notice bad"><b>'+esc(j.error||'This could not be completed.')+'</b></div><button class="btn sec" data-act="jobback">Back</button>':'<p class="ks">You can leave this page; the work continues in the background.</p>')+'</div>';
}
function updJob(j){
  const b=$('#jbar'); if(!b){ redrawAdd(); if(S.page==='journey') updLive(j); return; }
  const pct=Math.max(2,Math.min(100,j.progress||0)); b.style.width=pct+'%'; $('#jpct').textContent=Math.round(pct)+'%'; $('#jmsg').textContent=j.message||'Working…';
  $('#jlog').innerHTML=(j.log||[]).slice(-8).map(x=>'<li>'+esc(x)+'</li>').join('');
}
/* Research or import, then straight to the outside-in readout of the company */
async function runAddJob(start){
  const A=S.add; A.busy=true; A.err=''; A.problems=null; redrawAdd();
  try{
    const r=await start(); A.job={status:'queued',progress:1,message:'Queued',log:[]}; redrawAdd();
    const j=await pollJob(r.job_id,x=>{ A.job=x; updJob(x); });
    const id=(j.result&&(j.result.company_id||j.result.id))||r.id;
    await refreshCompanies(); await selectCompany(id); S.add=newAdd('file'); S.page='journey'; finish1();
    toast(COFULL+' is ready.');
  }catch(e){ A.job=null; A.busy=false; A.err=e.message; A.problems=e.problems||null; if(S.page==='journey'&&S.sub==='setup') redrawAdd(); else toast(e.message); }
}
function startResearch(){
  const A=S.add, peers=A.peers.filter(p=>p.name.trim());
  if(!A.company.trim()||!A.ticker.trim()){ A.err='Enter the company name and ticker.'; return redrawAdd(); }
  if(peers.length<2){ A.err='Add at least two peers.'; return redrawAdd(); }
  if(!/^\d{4}-Q[1-4]$/.test(A.period.trim())){ A.err='Period must look like 2026-Q4.'; return redrawAdd(); }
  runAddJob(async()=>{ const documents=[]; for(const f of A.files||[]) documents.push({name:f.name,mime:f.file.type,data_b64:await fileToB64(f.file)});
    return startJob('/research',{company:A.company.trim(),ticker:A.ticker.trim().toUpperCase(),peers:peers.map(p=>({name:p.name.trim(),ticker:p.ticker.trim().toUpperCase()})),period:A.period.trim(),mode:S.mode,documents}); });
}
async function startImport(){
  const A=S.add; if(A.busy||A.job) return;
  A.busy=true; const btn=$('[data-act="addimport"]'); if(btn) btn.disabled=true;  /* no second import while the files are read */
  const f=id=>{ const e=$('#'+id); return e&&e.files?Array.from(e.files):[]; }, read=async x=>JSON.parse(await x.text()), fail=m=>{ A.busy=false; A.err=m; redrawAdd(); };
  const oi=f('a_oi'), io=f('a_io'), pr=f('a_pr');
  if(!oi.length) return fail('Choose the outside-in assessment file.');
  const big=oi.concat(io,pr).filter(x=>x.size>MAX_FILE); if(big.length) return fail(listJoin(big.map(x=>x.name))+': over the 25 MB limit per file.');
  let body; try{ body={outside_in:await read(oi[0])}; if(io.length) body.inside_out=await read(io[0]); if(pr.length) body.priors=await Promise.all(pr.slice(0,4).map(read)); }
  catch(e){ return fail('One of the files is not valid JSON: '+e.message); }
  runAddJob(()=>startJob('/companies/import',body));
}
document.addEventListener('input',e=>{
  const t=e.target; if(!S.add) return;
  if(t.dataset.add){ S.add[t.dataset.add]=t.value; }
  else if(t.dataset.addp){ S.add.peers[+t.dataset.i][t.dataset.addp]=t.value; }
});
