/* Report views modelled on the Word report: summary, scorecard, evidence, peers, sources, method. */
/* ================= report views (modelled on the Word report) ================= */
const gc=g=>'<td class="gc g'+esc(g||'NA')+'">'+esc(g||'n/a')+'</td>';
const sc_=s=>'<td class="gc s'+(s==null?'NA':esc(s))+'">'+(s==null?'n/a':esc(s))+'</td>';
function eb(t){ return '<div class="eb">'+esc(t)+'</div>'; }
function seg(n){ let s='<span class="seg">'; for(let i=1;i<=5;i++) s+='<i class="'+(n!=null&&i<=n?'on':'')+'"></i>'; return s+'</span>'; }
/* the research window, counted back from the run date: 24 months of behaviour, five years of filings */
function evWindow(){ const d=new Date(D.meta.date||Date.now()); if(isNaN(d)) return 'Behaviour indicators over 24 months; trend indicators over five years.'; return 'Behaviour indicators from '+(d.getFullYear()-2)+'-'+String(d.getMonth()+1).padStart(2,'0')+'; trend indicators from FY'+(d.getFullYear()-5)+'.'; }
function cover(stage){
  return '<div class="dcover"><div class="eb w">Alvarez &amp; Marsal</div><h1>Day 1 / Day 2<br>Board Assessment</h1><div class="cl">'+esc(COFULL)+' ('+esc(TK)+') &nbsp;·&nbsp; '+esc(S.period)+'</div><div class="cs">'+(stage==='io'?'Inside-out update'+' on top of an outside-in assessment from public information, benchmarked against ':'Outside-in assessment from public information, benchmarked against ')+esc(PEERFULL.join(', ').replace(/\.$/,''))+'.</div><div class="cr"></div><div class="cd">'+esc(stage==='io'?((D.io||{}).date||D.meta.date):D.meta.date)+'</div></div>'+
  '<table class="kvt"><tr><th>Purpose</th><td>Grade the board of '+esc(COFULL)+' A–F on six Day 1 / Day 2 dimensions and 22 indicators, attributing what the company did under the board’s watch to the board, against a named peer set.</td></tr><tr><th>Basis</th><td>'+(stage==='io'?'Public information plus board documents and a director self-assessment. ':'Public information only. ')+esc(MODES[S.mode])+'.</td></tr><tr><th>Circulation</th><td>'+esc(RUN_CIRC[S.mode])+'.</td></tr><tr><th>Evidence window</th><td>'+evWindow()+'</td></tr></table>';
}
/* Peer marker colours (up to five peers) and evidence-code prefix -> subject */
const PEER_C=['var(--slate)','var(--amber)','#722282','#29702A','#C8187D'];
function peerColor(i){ return PEER_C[i%PEER_C.length]; }
function srcPrefixes(){ if(D.meta.prefixes) return D.meta.prefixes; const p={E:CO}; ['X','B','K','L','N'].slice(0,PEERS.length).forEach((k,i)=>p[k]=PEERS[i]); return p; }
function gtile(label,g,sub,note){ return '<div class="gt"><div class="eb">'+label+'</div><div class="gl"><span class="gbig" style="color:var(--g'+(g||'NA')+')">'+(g||'–')+'</span><b>'+esc(labelOf(g))+'</b></div><div class="muted">'+sub+'</div>'+(note?'<div class="muted">'+note+'</div>':'')+'</div>'; }
function heatmap(m,stage){
  const sc=stage==='io'?m.ioSc:m.oiSc; let h='<div class="heat">';
  DIMS.forEach(d=>{ h+='<div class="dn">'+d+'. '+esc(DIMN[d])+'</div><div>'+IDS.filter(i=>DIM_OF[i]===d).map(i=>'<button class="sq '+(sc[i]==null?'sNA':'s'+esc(sc[i]))+'" data-act="ind" data-i="'+i+'" title="'+esc(indName(i))+'" aria-label="'+i+' '+esc(indName(i))+'">'+i+'</button>').join('')+'</div>'; });
  return h+'</div><div class="legend"><span style="--c:var(--s5)">5 Day 1</span><span style="--c:var(--s4)">4</span><span style="--c:var(--s3)">3 Mixed</span><span style="--c:var(--s2)">2</span><span style="--c:var(--s1)">1 Day 2</span></div>';
}
function tReport(stage,m){
  const io=stage==='io', L=io?m.io:m.oi, O=m.oi, last=S.history.length?S.history[S.history.length-1]:null;
  let h=cover(stage);
  /* executive summary */
  h+='<section class="sec">'+eb('Executive summary')+'<h2 class="dh">'+esc(io?D.io.headline:D.headline)+'</h2><div class="gtiles">';
  h+=gtile('Outside-in',O.overall.grade,O.overall.n+' of 6 dimensions reported',last?arrow(O.overall.grade,last.overall.grade)+' ('+esc(last.period)+')':'');
  if(io) h+=gtile('After inside-out',m.io.overall.grade,m.io.overall.n+' of 6 dimensions reported',arrow(m.io.overall.grade,O.overall.grade)+' vs outside-in');
  const gr=o=>o.grade?esc(o.grade)+' ('+esc(o.label)+')':'no overall grade';
  h+='</div><p class="lede">'+(io?esc(CO)+'’s board '+(m.io.overall.grade?'grades '+gr(m.io.overall):'has no overall grade')+' once board documents and a director self-assessment are added, against '+gr(O.overall)+' from public information alone.'+(!m.io.overall.grade||!O.overall.grade?' An overall grade needs at least three dimensions with enough evidence to be reported.':''):esc(D.overall_line))+'</p>';
  h+=eb('What drives the rating')+'<p>'+esc(io?D.io.drives:D.drives)+'</p>';
  if(io){ h+=eb('Inside view against the public record')+'<div class="two"><div><b>Better than the public record</b><ul>'+(D.io.better||[]).map(x=>'<li>'+codes(x)+'</li>').join('')+'</ul></div><div><b>Worse than the public record</b><ul>'+(D.io.worse||[]).map(x=>'<li>'+codes(x)+'</li>').join('')+'</ul></div></div>'; }
  h+=eb('Key actions')+(io?D.io.actions:D.actions).map(a=>'<p class="ka"><span>▸</span> <b>'+esc(a.heading)+'.</b> '+codes(a.description)+'</p>').join('');
  h+=eb('Metrics worth tracking')+'<div class="scroll"><table class="dt"><tr><th>Metric</th><th>Why it matters</th><th>Now</th></tr>'+(D.metrics||[]).map(r=>'<tr><td><b>'+esc(r[0])+'</b></td><td>'+esc(r[1])+'</td><td>'+esc(r[2])+'</td></tr>').join('')+'</table></div>';
  h+=eb('Position relative to peers')+'<p>'+esc(D.position)+'</p>'+(D.position_lines||[]).map(x=>'<p class="ln">'+esc(x)+'</p>').join('')+(io?'<p class="muted">Peers are compared on outside-in grades only; they are never re-scored with inside-out information.</p>':'');
  h+='</section>';
  /* at a glance */
  h+='<section class="sec">'+eb('At a glance')+'<h2 class="dh">Twenty-two indicators</h2><p class="muted">Select a square for the rationale and evidence.</p>'+heatmap(m,stage)+'</section>';
  /* scorecard: each dimension opens to its indicators */
  const now=io?m.ioSc:m.oiSc, Lg=io?m.io:O;
  h+='<section class="sec">'+eb('Scorecard and trend')+'<h2 class="dh">Grades by dimension</h2><p class="muted">Select a dimension to see its indicators.</p><div class="scroll"><table class="dt acc"><tr><th>Dimension</th>'+S.history.map(x=>'<th>'+esc(x.period)+'</th>').join('')+'<th>'+(io?'Outside-in':esc(S.period))+'</th>'+(io?'<th>After inside-out'+'</th>':'')+(last?'<th>Change</th>':'')+'<th>Evidence in this run</th></tr>';
  DIMS.forEach((d,k)=>{ const open=S.rdim.indexOf(String(d))>=0;
    h+='<tr class="dimx'+(open?' open':'')+'" data-act="dimx" data-d="'+d+'"><td><b><span class="car">▸</span>'+d+'. '+esc(DIMN[d])+'</b></td>'+S.history.map(x=>gc(x.dims[d].grade)).join('')+gc(O.dims[d].grade)+(io?gc(m.io.dims[d].grade):'')+(last?'<td>'+arrow(Lg.dims[d].grade,last.dims[d].grade)+'</td>':'')+'<td>'+codes((D.scorecard[k]||{}).line)+'</td></tr>';
    IDS.filter(i=>DIM_OF[i]===d).forEach(i=>{ const c=io?ioCell(i):null;
      h+='<tr class="subr" data-d="'+d+'"'+(open?'':' hidden')+'><td><button class="lnk" data-act="ind" data-i="'+i+'">'+i+'</button> '+esc(indName(i))+'</td>'+S.history.map(x=>sc_(x.ind[i])).join('')+sc_(m.oiSc[i])+(io?sc_(m.ioSc[i]):'')+(last?delta(last.ind[i],now[i]):'')+'<td>'+(c&&!c.carried?evText(firstSentence(c.rat),c.ev):evText(indLine(i),D.ind[i].ev))+'</td></tr>'; }); });
  h+='<tr class="tot"><td>Overall</td>'+S.history.map(x=>gc(x.overall.grade)).join('')+gc(O.overall.grade)+(io?gc(m.io.overall.grade):'')+(last?'<td>'+arrow(Lg.overall.grade,last.overall.grade)+'</td>':'')+'<td><i>Rounded average of dimension letters (midpoints round down).</i></td></tr></table></div>'+(io?'':'<p class="muted"><i>'+esc(D.coverage_note)+'</i></p>')+'</section>';
  /* what changed since the earlier quarter */
  if(last){ const ch=IDS.filter(i=>last.ind[i]!=null&&now[i]!=null&&last.ind[i]!==now[i]);
    h+='<section class="sec">'+eb('What changed since '+last.period)+'<h2 class="dh">Indicators that moved</h2>'+(ch.length?'<div class="scroll"><table class="dt"><tr><th>Indicator</th><th>Prior</th><th>Now</th><th>Δ</th><th>Evidence that moved the score</th></tr>'+
     ch.map(i=>{ const c=io?ioCell(i):null; return '<tr><td><b>'+i+' '+esc(indName(i))+'</b></td>'+sc_(last.ind[i])+sc_(now[i])+delta(last.ind[i],now[i])+'<td>'+(c&&!c.carried?evText(c.rat,c.ev):evText(D.ind[i].rationale,D.ind[i].ev))+'</td></tr>'; }).join('')+'</table></div>':'<p class="muted">No indicator score changed.</p>')+'</section>'; }
  /* evidence behind each indicator, grouped by dimension */
  h+='<section class="sec">'+eb('Evidence behind each indicator')+'<h2 class="dh">One line per indicator; the detailed view is in Dimension detail</h2><div class="scroll"><table class="dt"><tr><th>Indicator</th><th>Score'+(io?' (OI → IO)':'')+'</th><th>Summary of the evidence</th></tr>';
  DIMS.forEach(d=>{ h+='<tr class="dimrow"><td colspan="3"><b>'+d+'. '+esc(DIMN[d])+'</b> &nbsp;Outside-in '+gchip(O.dims[d].grade)+(io?' &nbsp;After inside-out '+gchip(m.io.dims[d].grade):'')+'</td></tr>';
    IDS.filter(i=>DIM_OF[i]===d).forEach(i=>{ const c=io?ioCell(i):null; h+='<tr><td><button class="lnk" data-act="ind" data-i="'+i+'">'+i+'</button> '+esc(indName(i))+'</td>'+(io?'<td class="gcw">'+schip(D.ind[i].score)+(c.score!==D.ind[i].score?' → ':' = ')+schip(c.score)+'</td>':sc_(D.ind[i].score))+'<td>'+evText(indLine(i),D.ind[i].ev)+'</td></tr>'; }); });
  h+='</table></div></section>';
  /* peer comparison: the last column of each row is the written comparison */
  const prow=k=>{ const r=(D.peer_table||[])[k]||[]; return r.length?r[r.length-1]:''; };
  h+='<section class="sec">'+eb('Peer comparison')+'<h2 class="dh">Dimension grades against the peer set</h2><div class="scroll"><table class="dt"><tr><th>Dimension</th><th>'+esc(CO)+(io?' (outside-in)':'')+'</th>'+PEERS.map(p=>'<th>'+esc(p)+'</th>').join('')+'<th>How the company compares</th></tr>';
  DIMS.forEach((d,k)=>{ h+='<tr><td><b>'+d+'. '+esc(DIMN[d])+'</b></td>'+gc(O.dims[d].grade)+m.peers.map(p=>gc(p.c.dims[d].grade)).join('')+'<td>'+codes(prow(k+1))+'</td></tr>'; });
  h+='<tr class="tot"><td>Overall</td>'+gc(O.overall.grade)+m.peers.map(p=>gc(p.c.overall.grade)).join('')+'<td>'+codes(prow(DIMS.length+1))+'</td></tr></table></div></section>';
  /* actions */
  h+='<section class="sec">'+eb('Actions')+'<h2 class="dh">What the board could do next</h2>'+(io?D.io.actions:D.actions).map(a=>'<div class="act"><h4><span>'+esc(a.n)+'</span> '+esc(a.heading)+'</h4><p>'+codes(a.description)+'</p><p class="muted">Measures: '+esc((a.measures||[]).join('; ')||'–')+' &nbsp; Target: '+esc(a.target||'–')+'</p></div>').join('');
  const pal=priorActionsList();
  if(io&&pal.length){
    h+=eb('Status of prior actions')+'<div class="scroll"><table class="dt"><tr><th>Prior action</th><th>Status</th><th>Evidence</th></tr>'+pal.map(a=>'<tr><td><b>'+esc(a.heading)+'</b></td><td><span class="st-'+esc(a.status)+'">'+esc(a.status.replace(/_/g,' '))+'</span></td><td>'+codes(a.note)+'<div class="muted">'+esc(a.metrics)+'</div></td></tr>').join('')+'</table></div>';
    const behind=pal.filter(a=>a.status==='behind'||a.status==='not_started');
    if(behind.length&&D.io.back) h+=eb('Getting back on track')+D.io.back.filter(b=>behind.some(a=>a.id===b.id)).map(b=>'<details><summary>'+esc(b.heading)+'</summary><div class="dbody"><table class="dt"><tr><th>What happened</th><td>'+esc(b.what)+'</td></tr><tr><th>Impact</th><td>'+esc(b.impact)+'</td></tr><tr><th>Root cause</th><td>'+esc(b.cause)+'</td></tr><tr><th>Mechanism to prevent</th><td>'+esc(b.prevent)+'</td></tr><tr><th>Measures</th><td>'+esc((b.measures||[]).join('; '))+'</td></tr></table></div></details>').join('');
  } else if(!io){ h+='<p class="muted">Status of prior actions is not forced from public information; it is asked for in the inside-out stage.</p>'; }
  h+='</section>';
  if(!io) h+='<section class="sec">'+eb('Additional information that would sharpen the assessment')+'<h2 class="dh">Only where it would change a grade or an action</h2>'+(D.addl||[]).map(x=>'<p class="ln">'+esc(x)+'</p>').join('')+'</section>';
  return h;
}
/* ---- dimension detail (Appendix 1) ---- */
function tDetail(stage,m){
  const io=stage==='io'; let h='<div class="notice">Each indicator is scored once, for the board, against written anchors. Evidence codes open the source.</div>';
  DIMS.forEach(d=>{ const t=D.dimtext[d], L=io?m.io:m.oi;
    h+='<section class="sec">'+eb('Appendix 1 · Detailed indicator view')+'<h2 class="dh">'+d+'. '+esc(DIMN[d])+' &nbsp;·&nbsp; Outside-in '+gchip(m.oi.dims[d].grade)+(io?' &nbsp;→&nbsp; after inside-out'+' '+gchip(m.io.dims[d].grade):'')+'</h2><p>'+codes(t.text)+'</p><p class="muted"><b>Where this grade is limited:</b> '+esc(t.limit.replace(/^Where this grade is limited:\s*/,''))+'</p>'+
     '<div class="scroll"><table class="dt"><tr><th>Indicator</th><th>Outside-in</th>'+(io?'<th>Post inside-out</th>':'')+'<th>Rationale and sources</th><th>Conf.</th></tr>';
    IDS.filter(i=>DIM_OF[i]===d).forEach(i=>{ const o=D.ind[i], c=io?ioCell(i):null;
      h+='<tr><td><b><button class="lnk" data-act="ind" data-i="'+i+'">'+i+'</button> '+esc(o.name)+'</b></td>'+sc_(o.score)+(io?sc_(c.score):'')+'<td>'+codes(o.rationale)+(io?'<div class="iob"><b>Inside-out'+':</b> '+codes(c.rat)+'</div>':'')+'</td><td>'+esc(io?c.conf:o.conf)+'</td></tr>'; });
    h+='</table></div></section>'; });
  return h;
}
/* ---- peers (Appendix 2) ---- */
function tPeers(stage,m){
  let h='<div class="notice">Peers are graded outside-in from public information with the same rubric and depth as the company.'+(stage==='io'?' They are not re-scored with inside-out information.':'')+'</div>';
  m.peers.forEach((p,pi)=>{ const pd=D.peers[pi];
    h+='<section class="sec">'+eb('Appendix 2 · '+(pi+1)+' of '+m.peers.length)+'<h2 class="dh">'+esc(p.full)+': outside-in indicator view</h2><div class="scroll"><table class="dt strip"><tr>'+DIMS.map(d=>gc(p.c.dims[d].grade)).join('')+gc(p.c.overall.grade)+'</tr><tr>'+DIMS.map(d=>'<td class="sl">'+d+'. '+esc(DIMN[d])+'</td>').join('')+'<td class="sl">Overall</td></tr></table></div><p>'+esc(pd.summary)+'</p>'+
     '<div class="scroll"><table class="dt"><tr><th>Indicator</th><th>Score</th><th>Rationale and sources</th></tr>'+IDS.map(i=>'<tr><td><b>'+i+' '+esc(indName(i))+'</b></td>'+sc_(pd.ind[i].score)+'<td>'+codes(pd.ind[i].rationale)+'</td></tr>').join('')+'</table></div></section>'; });
  return h;
}
/* ---- sources (Appendix 5) ---- */
function srcList(){
  const f=S.srcf, q=S.srcq.trim().toLowerCase(); const all=Object.assign({},D.ev,(D.io&&D.io.ev)||{}); let keys=Object.keys(all);
  const isIO=k=>k.indexOf('IO')===0||k.indexOf('SA')===0;
  keys=keys.filter(k=>f==='all'||(f==='io'&&isIO(k))||(!isIO(k)&&k[0]===f));
  if(q) keys=keys.filter(k=>(k+' '+all[k].doc+' '+(all[k].excerpt||'')+' '+(all[k].used||'')).toLowerCase().indexOf(q)>=0);
  const pre=Object.keys(srcPrefixes()), order=k=>(isIO(k)?(k[0]==='I'?90:91):pre.indexOf(k[0]))*1000+parseInt(k.replace(/\D/g,''),10);
  keys.sort((a,b)=>order(a)-order(b));
  return '<p class="muted">'+keys.length+' of '+Object.keys(all).length+' sources shown.</p>'+keys.map(k=>{ const e=all[k];
    return '<div class="src" id="src_'+esc(k)+'"><div><b>'+esc(k)+'</b> &nbsp; '+esc(e.doc)+'</div><div class="muted">'+esc(e.date)+(e.recent?' · <b style="color:var(--navy)">RECENT</b>':'')+'</div><div>“'+esc(e.excerpt||'')+'”</div>'+(e.question?'<div class="muted">Question: '+esc(e.question)+'</div>':'')+(e.url?'<div class="muted">'+esc(e.url)+'</div>':'')+(e.used?'<div class="muted">Used in: '+esc(e.used)+'</div>':'')+'</div>'; }).join('');
}
function tSources(stage){
  const p=srcPrefixes(), f=[['all','All']].concat(Object.keys(p).map(k=>[k,p[k]])).concat(stage==='io'?[['io','Inside-out and self-assessment']]:[]);
  return eb('Appendix 5')+'<h2 class="dh" style="margin-top:4px">Sources consulted</h2><p class="muted">Each entry is referenced from the tables by its code. Verbatim excerpts are kept under 15 words.</p><div class="row" style="margin:10px 0">'+f.map(x=>'<button class="chipb'+(S.srcf===x[0]?' on':'')+'" data-act="srcf" data-f="'+esc(x[0])+'">'+esc(x[1])+'</button>').join('')+'<input type="text" id="srcq" placeholder="Search sources" value="'+esc(S.srcq)+'" style="max-width:260px"></div><div id="srclist">'+srcList()+'</div>';
}
/* ---- method (Appendices 3, 4, 6) ---- */
function tMethod(stage,m){
  let h='<section class="sec">'+eb('Appendix 3')+'<h2 class="dh">How to read this report</h2>'+D.read.map(x=>'<p>'+esc(x)+'</p>').join('')+
   '<div class="scroll"><table class="dt"><tr><th>Average indicator score</th><th>Grade</th><th>Classification</th></tr>'+D.scale.map((b,i)=>'<tr><td>'+(b.min>0?b.min.toFixed(2)+' – '+(i===0?'5.00':(D.scale[i-1].min-0.01).toFixed(2)):'below 2.00')+'</td>'+gc(b.grade)+'<td>'+esc(b.label)+'</td></tr>').join('')+'</table></div></section>';
  /* omit the internal quality-control rules (evidence de-duplication, repeat runs) */
  h+='<section class="sec">'+eb('Appendix 4')+'<h2 class="dh">Methodology and scoring rules</h2><ol class="mlist">'+D.method.filter((x,k)=>k!==9&&k!==12).map(x=>'<li>'+esc(x.replace(/^\d+\s+/,''))+'</li>').join('')+'</ol></section>';
  h+='<section class="sec">'+eb('Appendix 6')+'<h2 class="dh">Indicator definitions and anchors</h2>';
  DIMS.forEach(d=>{ h+='<h3 class="sh">'+d+'. '+esc(DIMN[d])+'</h3>'+IDS.filter(i=>DIM_OF[i]===d).map(i=>{ const x=D.defs[i]; return '<details><summary>'+i+' '+esc(indName(i))+'</summary><div class="dbody"><p>'+esc(x.def)+'</p><p class="muted">'+esc(x.prompt)+'</p><table class="dt"><tr><th>1 – Day 2</th><th>3 – Mixed</th><th>5 – Day 1</th></tr><tr><td>'+esc(x.anchors['1'])+'</td><td>'+esc(x.anchors['3'])+'</td><td>'+esc(x.anchors['5'])+'</td></tr></table></div></details>'; }).join(''); });
  h+='</section>';
  return h;
}
function showInd(id){
  /* the inside-out score shows wherever the context is inside-out: an inside-out dashboard, or stage 2 or 3 of the journey */
  const useIO=S.ioDone&&(document.getElementById('drawer').classList.contains('on')?S.dashStage==='io':S.stage>=2);
  const o=D.ind[id], io=useIO?ioCell(id):null, x=D.defs[id];
  let h='<h3>'+esc(id)+' '+esc(o.name)+'</h3><p class="muted">'+esc(x.def)+'</p><p>Outside-in '+schip(o.score)+(io?' → after inside-out'+' '+schip(io.score):'')+' <span class="muted">'+esc(o.conf)+' confidence</span></p><p>'+codes(o.rationale)+'</p>'+(io?'<p><b>Inside-out'+':</b> '+codes(io.rat)+'</p>':'')+'<table class="dt"><tr><th>1 – Day 2</th><th>3 – Mixed</th><th>5 – Day 1</th></tr><tr><td>'+esc(x.anchors['1'])+'</td><td>'+esc(x.anchors['3'])+'</td><td>'+esc(x.anchors['5'])+'</td></tr></table><div style="margin-top:14px"><button class="btn" data-act="close">Close</button></div>';
  $('#modalBody').innerHTML=h; $('#modal').classList.add('on');
}
function showEv(c){
  const e=evOf(c); let h='<h3>'+esc(c)+'</h3>';
  if(!e) h+='<p class="muted">This item is not available: the source was not supplied in this run.</p>';
  else h+='<p><b>'+esc(e.doc)+'</b></p><p class="muted">'+esc(e.date||'')+(e.recent?' · RECENT':'')+'</p>'+(e.question?'<p><b>Question:</b> '+esc(e.question)+'</p>':'')+'<p>“'+esc(e.excerpt||'')+'”</p>'+(e.url?'<p class="muted">'+esc(e.url)+'</p>':'')+(e.used?'<p class="muted">Used in: '+esc(e.used)+'</p>':'');
  h+='<button class="btn" data-act="close">Close</button>'; $('#modalBody').innerHTML=h; $('#modal').classList.add('on');
}

function tExec(stage,m){ const parts=tReport(stage,m).split('<section class="sec">'); return parts.filter(p=>/^<div class="eb">(Executive summary|Scorecard)/.test(p)).map(p=>'<section class="sec">'+p).join(''); }
