#!/usr/bin/env python3
"""
build_dashboard.py (v1.2, board-only) - render the dashboard as one self-contained HTML file.

Usage:
    python build_dashboard.py run.json output.html

Mirrors the report: header, executive summary (grade tiles, what moved, inside-vs-outside when inside-out,
key actions, metrics, peer position), scorecard and trend (with the what-changed tables), evidence by
indicator (rationale with evidence behind info icons; detailed view expands per dimension), peer comparison
(with per-row comparison summary and peer trend), actions and prior-action status, getting back on track,
additional information needed, coverage and limitations, evidence accordion (collapsed), methodology footer.
"""
import json, sys, os, html
from common import *

TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>__TITLE__</title>
<style>
:root{--navy:#002B49;--blue:#0085CA;--amber:#CF7F00;--teal:#00677F;--slate:#5E8AB4;--grey:#646464;--bg:#FFFFFF;--card:#FFFFFF;--ink:#1A1F2B;--muted:#646464;--line:#D9D9D9;--tint:#EEF7FD;--tint2:#DAF2FF;
 --gA:#00677F;--gB:#0085CA;--gC:#5E8AB4;--gD:#CF7F00;--gF:#A6192E;--gNA:#969696;--s1:#A6192E;--s2:#CF7F00;--s3:#5E8AB4;--s4:#0085CA;--s5:#00677F;
 box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14.5px/1.5 Arial,Helvetica,sans-serif}
.band{background:#fff;color:var(--navy);padding:24px 0 20px;border-top:5px solid var(--blue);border-bottom:1px solid var(--line)}h1{color:var(--navy)}.wrap{max-width:1180px;margin:0 auto;padding:0 18px}
.brand{font-size:.7rem;letter-spacing:.22em;text-transform:uppercase;color:var(--blue);margin-bottom:8px}h1{font-size:1.55rem;margin:0 0 6px;line-height:1.2}
.meta{font-size:.83rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:16px}.mode{display:inline-block;margin-top:12px;padding:4px 10px;border-left:3px solid var(--amber);background:var(--tint);font-size:.76rem}
main{padding:8px 0 60px}.kicker{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--blue);margin:30px 0 2px;font-weight:700}h2{font-size:1.15rem;margin:0 0 10px;color:var(--navy)}
.card{background:var(--card);border:1px solid var(--line);border-top:3px solid #002B49;padding:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.tile .lbl{font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}.tile .big{font-size:3.2rem;font-weight:700;line-height:1;margin:6px 0 2px}.tile .sub{font-weight:700}.tile p{margin:8px 0 0;color:var(--muted);font-size:.9rem}
.g{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:32px;padding:0 8px;color:#fff;font-weight:700}.gA{background:var(--gA)}.gB{background:var(--gB)}.gC{background:var(--gC)}.gD{background:var(--gD)}.gF{background:var(--gF)}.gNA{background:var(--gNA)}
.s{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;color:#fff;font-weight:700;font-size:.9rem}.s1{background:var(--s1)}.s2{background:var(--s2)}.s3{background:var(--s3)}.s4{background:var(--s4)}.s5{background:var(--s5)}.sNA{background:var(--gNA);font-size:.7rem}
.prov{font-size:.68rem;color:var(--amber);font-weight:700}.up{color:var(--teal);font-weight:700}.down{color:var(--s1);font-weight:700}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top;font-size:.9rem}th{font-size:.7rem;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.08em;background:var(--tint)}
.scroll{overflow-x:auto}.center{text-align:center}.small{font-size:.8rem;color:var(--muted)}.row{cursor:pointer}.row:hover{background:var(--tint)}
.detail{display:none;background:var(--tint);padding:12px 14px;margin:0 0 10px;border-left:3px solid var(--blue)}.detail.open{display:block}
.info{display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;border-radius:50%;background:var(--blue);color:#fff;font-size:.65rem;font-weight:700;margin:0 2px;cursor:pointer;border:0;vertical-align:middle}.info.ind{background:var(--grey)}
.ev{border-left:3px solid var(--blue);padding:8px 12px;margin:8px 0;background:var(--card)}.ev .src{font-weight:700;color:var(--navy)}.ev .exc{font-style:italic;margin:3px 0}.ev a{color:var(--blue);word-break:break-all}
.chip{display:inline-block;background:var(--tint2);padding:1px 7px;font-size:.7rem;margin:2px 3px 0 0}.recent{color:var(--amber);font-size:.68rem;font-weight:700}.sim{color:var(--amber);font-size:.68rem;font-weight:700;border:1px solid var(--amber);padding:0 4px}
.action{padding:10px 0;border-bottom:1px solid var(--line)}.action:last-child{border:0}.action h3{margin:0 0 4px;font-size:.98rem;color:var(--navy)}.action .m{font-size:.8rem;color:var(--muted)}
.st{display:inline-block;padding:2px 8px;color:#fff;font-weight:700;font-size:.72rem;text-transform:uppercase}.st-completed{background:var(--teal)}.st-on_track{background:var(--blue)}.st-behind{background:var(--amber)}.st-not_started{background:var(--s1)}.st-cancelled{background:var(--grey)}.st-no_public_evidence{background:var(--slate)}
.stat{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:10px}.stat div{background:var(--tint);padding:12px}.stat .n{font-size:1.4rem;font-weight:700;color:var(--navy)}.stat .l{font-size:.76rem;color:var(--muted)}
details.acc{background:var(--card);border:1px solid var(--line);border-top:3px solid #002B49}details.acc summary{cursor:pointer;padding:14px 18px;font-weight:700;color:var(--navy);list-style:none}details.acc summary::after{content:"▸";float:right;color:var(--blue)}details.acc[open] summary::after{content:"▾"}.accbody{padding:0 18px 18px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 10px}select,input{background:var(--card);color:var(--ink);border:1px solid var(--line);padding:6px 8px;font:inherit}
.modal{position:fixed;inset:0;background:rgba(0,43,73,.22);display:none;align-items:center;justify-content:center;padding:20px;z-index:50}.modal.open{display:flex}.modal .box{background:var(--card);color:var(--ink);max-width:760px;width:100%;max-height:85vh;overflow:auto;padding:22px;border-top:4px solid var(--amber)}.modal h3{margin:0 0 8px;color:var(--navy)}.modal .x{float:right;cursor:pointer;color:var(--muted);font-size:1.2rem}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:720px){.two{grid-template-columns:1fr}}.two h4{margin:0 0 6px;font-size:.85rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem}.draft{color:var(--amber);font-weight:700}
</style></head><body>
<div class="band"><div class="wrap"><div class="brand">Alvarez &amp; Marsal &nbsp;|&nbsp; Day 1 / Day 2 Board Assessment</div><h1 id="title"></h1><div class="meta" id="meta"></div><div class="mode" id="mode"></div></div></div>
<main><div class="wrap">
<div class="kicker">Executive summary</div><h2 id="headline"></h2>
<div class="grid" id="overall"></div>
<div class="card" style="margin-top:14px" id="summary"></div>
<div class="kicker">Scorecard and trend</div><h2>Grades by dimension</h2><div class="card scroll" id="scorecard"></div>
<div id="changes"></div>
<div class="kicker">Evidence behind each indicator</div><h2>Rationale per indicator; expand a dimension for the detailed view</h2><div class="card scroll" id="dims"></div>
<div class="kicker">Peer comparison</div><h2 id="peerh">How the board compares</h2><div class="card scroll" id="peers"></div>
<div class="kicker">Actions</div><h2 id="acth">What the board could do next</h2><div class="card" id="actions"></div>
<div id="bot"></div><div id="ain"></div>
<div class="kicker">Coverage</div><h2>Coverage and limitations</h2><div class="card" id="coverage"></div>
<div class="kicker">Sources</div><details class="acc"><summary>Full evidence list (open to see every source used)</summary><div class="accbody"><div class="filters"><select id="fDim"><option value="">All dimensions</option></select><select id="fOrigin"><option value="">All origins</option></select><select id="fInd"><option value="">All indicators</option></select><input id="fText" placeholder="Search evidence text"></div><div id="evList"></div></div></details>
<footer id="method"></footer></div></main>
<div class="modal" id="modal" onclick="if(event.target===this)this.classList.remove('open')"><div class="box" id="modalBox"></div></div>
<script>
const RUN=__RUN__, FW=__FW__; const DIMS=Object.keys(FW.dimensions).sort((a,b)=>a-b); const IND=FW.indicators; const INDBY=Object.fromEntries(IND.map(i=>[i.id,i]));
const stage=RUN.run.stage||'outside_in'; const io=stage==='inside_out'; const L=FW.stages[stage].lenses; const LL=FW.stages[stage].labels; const last=L[L.length-1];
const company=RUN.subjects.find(s=>s.role==='company'), peers=RUN.subjects.filter(s=>s.role==='peer'); const C=company.computed; const hist=RUN.history||[]; const prev=hist.length?hist[hist.length-1]:null;
const esc=s=>(s??'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const LV={A:5,B:4,C:3,D:2,F:1}; const gchip=g=>`<span class="g g${g||'NA'}">${g||'n/a'}</span>`; const schip=s=>`<span class="s s${s??'NA'}">${s??'n/a'}</span>`;
const delta=(n,o)=>(n&&o)?LV[n]-LV[o]:null; const dtxt=d=>d==null?'':d>0?`<span class="up">▲ ${d}</span>`:d<0?`<span class="down">▼ ${-d}</span>`:'<span class="small">=</span>';
const linkify=t=>esc(t).replace(/\[((?:[EXBKLN]|SA|IO)\d{2,3})\]/g,(m,id)=>`<button class="info" title="${esc((RUN.evidence[id]||{}).document||id)}" onclick="event.stopPropagation();showEv(['${id}'],'${id}')">i</button>`);
const prevGrade=(d)=>prev?((prev.stage==='inside_out'&&prev.dimensions[d].board_io)?prev.dimensions[d].board_io.grade:prev.dimensions[d].board.grade):null;
const prevOverall=()=>prev?((prev.stage==='inside_out'&&prev.overall.board_io)?prev.overall.board_io.grade:prev.overall.board.grade):null;

document.getElementById('title').textContent=`${company.name}: Day 1 / Day 2 Board Assessment${io?' — inside-out update':''}`;
document.getElementById('meta').innerHTML=[`Period ${esc(RUN.run.period)}`,`Run date ${esc(RUN.run.run_date)}`,`Peers: ${peers.map(p=>esc(p.name)).join(', ')}`,hist.length?`Trend vs ${hist.map(h=>h.period+(h.simulated?' (sim)':'')).join(', ')}`:'No prior report'].map(x=>`<span>${x}</span>`).join('');
document.getElementById('mode').innerHTML=`${esc(FW.run_modes[RUN.run.mode]||RUN.run.mode)} · ${io?'Public information plus board documents and self-assessment':'Outside-in, public information only'}${RUN.run.simulated?' · <span class="sim">SIMULATED</span>':''} · <span class="draft">DRAFT ONLY — requires review and approval by a qualified Alvarez and Marsal professional before use</span>`;
document.getElementById('headline').textContent=RUN.headline||'';
document.getElementById('overall').innerHTML=L.map(l=>{const o=C.overall[l]; const pv=prevOverall(); const d=delta(o.grade,pv);
 return `<div class="card tile"><div class="lbl">${LL[l]}</div><div class="big">${o.grade||'—'}</div><div class="sub">${esc(o.label)} ${o.provisional?'<span class="prov">PROVISIONAL</span>':''}</div><div class="small">${o.dimensions_reported} of 6 dimensions reported${pv?` · prior quarter ${pv} ${dtxt(d)}`:''}</div><p>${esc((RUN.overall_summary||{})[l]||'')}</p></div>`;}).join('');
(function(){let h=`<h4 style="margin:0 0 4px;font-size:.8rem;text-transform:uppercase;color:var(--muted)">What moved the rating</h4><p style="margin:0 0 12px">${linkify(RUN.what_moved||'')}</p>`;
 if(io&&RUN.inside_vs_outside){h+=`<div class="two"><div><h4>Better than the public evidence suggested</h4>${(RUN.inside_vs_outside.better||[]).map(x=>`<p>• ${linkify(x)}</p>`).join('')}</div><div><h4>Worse than the public evidence suggested</h4>${(RUN.inside_vs_outside.worse||[]).map(x=>`<p>• ${linkify(x)}</p>`).join('')}</div></div>`;}
 h+=`<h4 style="margin:12px 0 4px;font-size:.8rem;text-transform:uppercase;color:var(--muted)">Key actions</h4>`+(RUN.actions||[]).slice(0,5).map(a=>`<p style="margin:2px 0">▸ <b>${esc(a.heading)}.</b> ${esc((a.description||'').split('. ')[0])}.</p>`).join('');
 if((RUN.key_metrics||[]).length) h+=`<h4 style="margin:12px 0 4px;font-size:.8rem;text-transform:uppercase;color:var(--muted)">Metrics worth tracking</h4><div class="scroll"><table><thead><tr><th>Metric</th><th>Why it matters</th><th>Now</th></tr></thead><tbody>${RUN.key_metrics.map(m=>`<tr><td><b>${esc(m.metric)}</b></td><td>${esc(m.why)}</td><td>${esc(m.current||'')}</td></tr>`).join('')}</tbody></table></div>`;
 h+=`<h4 style="margin:12px 0 4px;font-size:.8rem;text-transform:uppercase;color:var(--muted)">Position relative to peers</h4><p>${esc(RUN.peer_position||'')}</p>`+(RUN.peer_summary_lines||[]).map(x=>`<p style="margin:2px 0">• ${esc(x)}</p>`).join('');
 document.getElementById('summary').innerHTML=h;})();
// scorecard
(function(){let h='<table><thead><tr><th>Dimension</th>'+hist.map(x=>`<th class="center">${x.period}${x.simulated?' (sim)':''}</th>`).join('')+L.map(l=>`<th class="center">${esc(RUN.run.period)} ${io?LL[l]:''}</th>`).join('')+'<th class="center">Change</th><th>Evidence in this run</th></tr></thead><tbody>';
 DIMS.forEach(d=>{const cur=C.dimensions[d][last].grade; const pv=prevGrade(d); let ch=dtxt(delta(cur,pv)); if(io&&!pv){ch='OI→IO '+dtxt(delta(C.dimensions[d].board_io.grade,C.dimensions[d].board.grade));}
  h+=`<tr><td><b>${d}. ${esc(FW.dimensions[d])}</b></td>`+hist.map(x=>`<td class="center">${gchip((x.stage==='inside_out'&&x.dimensions[d].board_io)?x.dimensions[d].board_io.grade:x.dimensions[d].board.grade)}</td>`).join('')+L.map(l=>`<td class="center">${gchip(C.dimensions[d][l].grade)}<div class="small">${C.dimensions[d][l].assessed}/${C.dimensions[d][l].of}</div></td>`).join('')+`<td class="center">${ch}</td><td class="small">${esc((RUN.scorecard_headline||{})[d]||'')}</td></tr>`;});
 h+=`<tr><td><b>Overall</b></td>`+hist.map(x=>`<td class="center">${gchip((x.stage==='inside_out'&&x.overall.board_io)?x.overall.board_io.grade:x.overall.board.grade)}</td>`).join('')+L.map(l=>`<td class="center">${gchip(C.overall[l].grade)}${C.overall[l].provisional?'<div class="prov">PROV.</div>':''}</td>`).join('')+`<td></td><td class="small">Rounded average of dimension letters (midpoints round down).</td></tr></tbody></table>`;
 h+=`<p class="small">${io?'Post inside-out grades use the board documents and self-assessment supplied; outside-in grades are shown unchanged for comparison.':'Grades rest on outside-in information; where an indicator is not assessable or scored on thin public evidence, board documents can arrive at a more accurate grade.'}</p>`;
 document.getElementById('scorecard').innerHTML=h;
 let ch='';
 if(prev){const rows=IND.filter(i=>{const c=(company.indicators[i.id]||{}).board||{}; const p=(prev.indicators[i.id]||{}).board; return c.score!=null&&p!=null&&c.score!==p;});
  if(rows.length){ch+=`<div class="kicker">What changed since ${prev.period}${prev.simulated?' (simulated prior)':''}</div><div class="card scroll"><table><thead><tr><th>Indicator</th><th class="center">Prior</th><th class="center">Now</th><th class="center">Δ</th><th>Evidence that moved the score</th></tr></thead><tbody>${rows.map(i=>{const c=company.indicators[i.id].board; const p=prev.indicators[i.id].board; return `<tr><td><b>${i.id}</b> ${esc(i.name)}</td><td class="center">${schip(p)}</td><td class="center">${schip(c.score)}</td><td class="center">${dtxt(c.score-p)}</td><td class="small">${linkify((RUN.change_notes||{})[i.id]||(c.rationale||'').split('. ')[0])}</td></tr>`;}).join('')}</tbody></table></div>`;}}
 if(io){const rows=IND.filter(i=>{const a=((company.indicators[i.id]||{}).board||{}).score, b=((company.indicators[i.id]||{}).board_io||{}).score; return b!=null&&a!==b;});
  if(rows.length){ch+=`<div class="kicker">Outside-in to post inside-out: indicators that moved</div><div class="card scroll"><table><thead><tr><th>Indicator</th><th class="center">OI</th><th class="center">IO</th><th class="center">Δ</th><th>Outside-in evidence, then what the board documents added</th></tr></thead><tbody>${rows.map(i=>{const a=company.indicators[i.id].board.score, b=company.indicators[i.id].board_io.score; return `<tr><td><b>${i.id}</b> ${esc(i.name)}</td><td class="center">${schip(a)}</td><td class="center">${schip(b)}</td><td class="center">${a==null?'<span class="up">new</span>':dtxt(b-a)}</td><td class="small">${linkify((RUN.io_change_notes||{})[i.id]||(company.indicators[i.id].board_io.rationale||''))}</td></tr>`;}).join('')}</tbody></table></div>`;}}
 document.getElementById('changes').innerHTML=ch;})();
// evidence by indicator with embedded detail
(function(){let h='<table><thead><tr><th>Dimension / indicator</th>'+L.map(l=>`<th class="center">${LL[l]}</th>`).join('')+'<th>Summary of the evidence</th></tr></thead><tbody>'; const summ=RUN.indicator_summary||{};
 DIMS.forEach(d=>{h+=`<tr class="row" onclick="toggle('dd${d}')"><td colspan="${L.length+2}" style="background:var(--tint)"><b>${d}. ${esc(FW.dimensions[d])}</b> &nbsp; ${L.map(l=>`${LL[l]} ${gchip(C.dimensions[d][l].grade)}`).join(' &nbsp; ')} <span class="small" style="float:right">detailed view ▾</span></td></tr>`;
  IND.filter(i=>i.dimension===d).forEach(i=>{const ind=company.indicators[i.id]||{}; h+=`<tr><td>${i.id} ${esc(i.name)} <button class="info ind" title="Definition and anchors" onclick="event.stopPropagation();showInd('${i.id}')">?</button></td>${L.map(l=>`<td class="center">${schip((ind[l]||{}).score)}</td>`).join('')}<td class="small">${linkify(summ[i.id]||((ind[last]||{}).rationale||'Not assessable.').split('. ')[0]+'.')}</td></tr>`;});
  h+=`<tr><td colspan="${L.length+2}" style="padding:0;border:0"><div class="detail" id="dd${d}"><p>${esc((company.assessment_text||{})[d]||'')}</p><div class="scroll"><table><thead><tr><th>Indicator</th>${L.map(l=>`<th class="center">${LL[l]}</th>`).join('')}<th>Rationale (evidence behind the icons)</th></tr></thead><tbody>`;
  IND.filter(i=>i.dimension===d).forEach(i=>{const ind=company.indicators[i.id]||{}; h+=`<tr><td><b>${i.id}</b> ${esc(i.name)}</td>${L.map(l=>{const c=ind[l]||{}; return `<td class="center">${schip(c.score)}<div class="small">${c.confidence||c.na_cause||''}</div></td>`;}).join('')}<td>${L.map(l=>{const c=ind[l]||{}; return `<div><b>${LL[l]}:</b> ${linkify(c.rationale||'')} ${(c.evidence||[]).length?`<button class="info" title="All evidence" onclick="event.stopPropagation();showEv(${JSON.stringify(c.evidence).replace(/"/g,'&quot;')},'${i.id} ${esc(i.name)} — ${LL[l]}')">i</button>`:''}</div>`;}).join('')}</td></tr>`;});
  const lim=(company.limitations||{})[d]; h+=`</tbody></table></div>${lim?`<p class="small"><b>Where this grade is limited:</b> ${esc(lim)}</p>`:''}</div></td></tr>`;});
 document.getElementById('dims').innerHTML=h+'</tbody></table>';})();
function toggle(id){document.getElementById(id).classList.toggle('open');} window.toggle=toggle;
function evHtml(eid){const e=RUN.evidence[eid]; if(!e) return `<div class="ev small">${esc(eid)} missing</div>`; return `<div class="ev"><span class="src">${esc(eid)} ${esc(e.document)}</span> <span class="small">${esc(e.date||'')} · ${esc(e.evidence_class||'direct')}${e.source_origin?' · '+esc(e.source_origin):''}</span> ${e.simulated?'<span class="sim">SIMULATED</span>':''} ${e.recent?'<span class="recent">RECENT</span>':''}${e.question?`<div class="small">Q: ${esc(e.question)}</div>`:''}${e.excerpt?`<div class="exc">${esc(e.excerpt)}</div>`:''}${e.search_log?`<div class="small">Search: ${esc(e.search_log)}</div>`:''}${e.url?`<div class="small"><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url)}</a></div>`:''}</div>`;}
function showEv(ids,title){document.getElementById('modalBox').innerHTML=`<span class="x" onclick="document.getElementById('modal').classList.remove('open')">×</span><h3>${esc(title)}</h3>`+ids.map(evHtml).join(''); document.getElementById('modal').classList.add('open');} window.showEv=showEv;
function showInd(id){const i=INDBY[id]; const ov=(FW.outside_in_overrides||{})[id]; const an=(ov&&!io)?ov.anchors:i.anchors; document.getElementById('modalBox').innerHTML=`<span class="x" onclick="document.getElementById('modal').classList.remove('open')">×</span><h3>${i.id} ${esc(i.name)}</h3><p>${esc(i.definition)}</p>${(ov&&!io)?'<p class="small">Outside-in anchors applied.</p>':''}<table><tr><th>1 – Day 2</th><td>${esc(an['1'])}</td></tr><tr><th>3 – Mixed</th><td>${esc(an['3'])}</td></tr><tr><th>5 – Day 1</th><td>${esc(an['5'])}</td></tr></table><p><b>Board prompt:</b> ${esc(i.board_lens)}</p><p class="small">Sources: ${esc(i.source_types)} · Public availability: ${esc((ov&&ov.availability)||i.availability)}</p>`; document.getElementById('modal').classList.add('open');} window.showInd=showInd;
// peers
(function(){if(io){document.getElementById('peerh').textContent='How the board compares (outside-in grades only)';}
 let h=(io?'<p class="small">Peers are compared on outside-in grades only; their inside-out information is not available. The company\'s outside-in grade is used.</p>':'')+'<table><thead><tr><th>Dimension</th><th class="center">'+esc(company.name)+'</th>'+peers.map(p=>`<th class="center">${esc(p.name)}</th>`).join('')+'<th>How the company compares</th></tr></thead><tbody>'; const rs=RUN.peer_row_summary||{};
 DIMS.forEach(d=>{h+=`<tr><td><b>${d}. ${esc(FW.dimensions[d])}</b></td><td class="center">${gchip(C.dimensions[d].board.grade)}</td>${peers.map(p=>`<td class="center">${gchip(p.computed.dimensions[d].board.grade)}</td>`).join('')}<td class="small">${esc(rs[d]||(RUN.comparative_evidence||{})[d]||'')}</td></tr>`;});
 h+=`<tr><td><b>Overall</b></td><td class="center">${gchip(C.overall.board.grade)}</td>${peers.map(p=>`<td class="center">${gchip(p.computed.overall.board.grade)}</td>`).join('')}<td class="small">${esc(RUN.peer_position||'')}</td></tr></tbody></table>`;
 if(prev&&prev.peers&&Object.keys(prev.peers).length){h+=`<div class="kicker" style="margin-top:14px">Peer trend: ${prev.period} to ${esc(RUN.run.period)} (overall)</div><table><thead><tr><th>Quarter</th>${peers.map(p=>`<th class="center">${esc(p.name)}</th>`).join('')}</tr></thead><tbody><tr><td>${prev.period}</td>${peers.map(p=>`<td class="center">${gchip((prev.peers[p.name]||{}).overall)}</td>`).join('')}</tr><tr><td>${esc(RUN.run.period)}</td>${peers.map(p=>`<td class="center">${gchip(p.computed.overall.board.grade)}</td>`).join('')}</tr></tbody></table>`;}
 h+=peers.map(p=>`<details style="margin-top:10px"><summary class="small" style="cursor:pointer">${esc(p.name)}: indicator view</summary><div class="scroll"><table><thead><tr><th>Indicator</th><th class="center">Score</th><th>Rationale</th></tr></thead><tbody>${IND.map(i=>{const c=(p.indicators[i.id]||{}).board||{}; return `<tr><td>${i.id} ${esc(i.name)}</td><td class="center">${schip(c.score)}</td><td class="small">${linkify(c.rationale||'')}</td></tr>`;}).join('')}</tbody></table></div></details>`).join('');
 document.getElementById('peers').innerHTML=h;})();
// actions
(function(){if(io) document.getElementById('acth').textContent='What the board could do next (updated after the inside-out review)';
 let h=(RUN.actions||[]).slice(0,5).map((a,k)=>`<div class="action"><h3>${String(k+1).padStart(2,'0')}&nbsp; ${esc(a.heading)}</h3><p>${linkify(a.description)}</p>${(a.measures||[]).length||a.target_by?`<div class="m">${(a.measures||[]).length?'Measures: '+a.measures.map(esc).join('; '):''}${a.target_by?' &nbsp; Target: '+esc(a.target_by):''}</div>`:''}</div>`).join('')||'<p class="small">No actions recorded.</p>';
 const pas=RUN.prior_actions_status||[];
 if(pas.length){h+=`<div class="kicker" style="margin-top:14px">Status of actions from ${prev?prev.period:'the prior report'}</div><div class="scroll"><table><thead><tr><th>Action</th><th>Status</th><th>Evidence and metrics</th></tr></thead><tbody>${pas.map(p=>`<tr><td><b>${esc(p.heading||p.id)}</b></td><td><span class="st st-${esc(p.status)}">${esc((p.status||'').replace(/_/g,' '))}</span></td><td class="small">${linkify(p.evidence_note||'')}${p.metrics_note?' Metrics: '+esc(p.metrics_note):''}</td></tr>`).join('')}</tbody></table></div>`;}
 else if(prev&&(prev.actions||[]).length&&!io){h+=`<p class="small" style="margin-top:12px">Actions from ${prev.period}: status cannot be established from public information; it will be asked for in the inside-out stage.</p>`;}
 document.getElementById('actions').innerHTML=h;
 const bot=RUN.back_on_track||[]; if(bot.length){document.getElementById('bot').innerHTML=`<div class="kicker">Getting back on track</div><h2>Actions behind or not started</h2><div class="card scroll"><table><thead><tr><th>Action</th><th>What happened</th><th>Impact</th><th>Root cause</th><th>Mechanism to prevent</th><th>Measures to track</th></tr></thead><tbody>${bot.map(b=>`<tr><td><b>${esc(b.heading||b.id)}</b></td><td class="small">${esc(b.what_happened)}</td><td class="small">${esc(b.impact)}</td><td class="small">${esc(b.root_cause)}</td><td class="small">${esc(b.prevention)}</td><td class="small">${esc(Array.isArray(b.measures)?b.measures.join('; '):b.measures)}</td></tr>`).join('')}</tbody></table></div>`;}
 const ain=RUN.additional_information_needed||[]; if(ain.length){document.getElementById('ain').innerHTML=`<div class="kicker">Additional information</div><h2>What would sharpen the assessment</h2><div class="card">${ain.map(x=>`<p>• ${esc(x)}</p>`).join('')}</div>`;}})();
// coverage
(function(){const cv=C.coverage[last]; const cov=RUN.coverage||{}; const na=IND.filter(i=>((company.indicators[i.id]||{})[last]||{}).score==null).map(i=>`${i.id}${((company.indicators[i.id]||{})[last]||{}).na_cause?' ('+company.indicators[i.id][last].na_cause+')':''}`); const sp=cv.not_assessable; const confs={High:0,Medium:0,Low:0}; IND.forEach(i=>{const c=(company.indicators[i.id]||{})[last]; if(c&&c.score!=null&&confs[c.confidence]!=null) confs[c.confidence]++;});
 const sim=Object.values(RUN.evidence).filter(e=>e.simulated).length;
 document.getElementById('coverage').innerHTML=`<div class="stat"><div><div class="n">${sp['disclosure-limited']||0}</div><div class="l">disclosure-limited (the company)</div></div><div><div class="n">${sp['retrieval-limited']||0}</div><div class="l">retrieval-limited (the run)</div></div><div><div class="n">${confs.High} · ${confs.Medium} · ${confs.Low}</div><div class="l">confidence High · Medium · Low</div></div>${sim?`<div><div class="n">${sim}</div><div class="l">simulated evidence items</div></div>`:''}</div><p><b>Not assessable:</b> ${na.length?na.map(esc).join(', '):'none'}</p><p><b>Documents unavailable:</b> ${(cov.documents_unavailable||[]).map(esc).join('; ')||'none'}</p><p><b>Consistency run:</b> ${esc(cov.consistency_result||'not yet run')}</p>${cov.notes?`<p class="small">${esc(cov.notes)}</p>`:''}`;})();
// evidence accordion
(function(){const fDim=document.getElementById('fDim'),fO=document.getElementById('fOrigin'),fInd=document.getElementById('fInd'),fText=document.getElementById('fText');
 DIMS.forEach(d=>fDim.insertAdjacentHTML('beforeend',`<option value="${d}">${d}. ${esc(FW.dimensions[d])}</option>`)); ['public','user_public','inside_out','self_assessment'].forEach(o=>fO.insertAdjacentHTML('beforeend',`<option value="${o}">${o.replace('_',' ')}</option>`)); IND.forEach(i=>fInd.insertAdjacentHTML('beforeend',`<option value="${i.id}">${i.id} ${esc(i.name)}</option>`));
 const uses={}; RUN.subjects.forEach(s=>IND.forEach(i=>['board','board_io'].forEach(l=>{const c=((s.indicators||{})[i.id]||{})[l]; (c?.evidence||[]).forEach(e=>{(uses[e]=uses[e]||[]).push({ind:i.id,dim:i.dimension,sub:s.name,l});});})));
 function render(){const q=fText.value.toLowerCase(); const list=Object.keys(RUN.evidence).filter(eid=>{const u=uses[eid]||[]; const e=RUN.evidence[eid]; const orig=e.source_origin||'public'; if(fDim.value&&!u.some(x=>x.dim===fDim.value)) return false; if(fO.value&&orig!==fO.value) return false; if(fInd.value&&!u.some(x=>x.ind===fInd.value)) return false; if(q&&!(`${e.document} ${e.excerpt} ${e.date}`.toLowerCase().includes(q))) return false; return true;});
  document.getElementById('evList').innerHTML=list.length?list.map(eid=>evHtml(eid)+`<div class="small" style="margin:-4px 0 10px 12px">Used in: ${(uses[eid]||[]).map(x=>`<span class="chip">${esc(x.sub===company.name?'':x.sub+' ')}${x.ind}${x.l==='board_io'?' (IO)':''}</span>`).join('')||'<span class="chip">context</span>'}</div>`).join(''):'<p class="small">No evidence matches the filters.</p>';}
 [fDim,fO,fInd].forEach(x=>x.onchange=render); fText.oninput=render; render();})();
document.getElementById('method').innerHTML=`Grade scale (average indicator score): ${FW.grade_scale.map(b=>`${b.grade} ${FW.grade_scale_ranges[b.grade]} ${b.label}`).join(' · ')}. Every indicator is scored once, for the board; management's observable actions are attributed to the board's oversight. Overall grades are the rounded average of dimension letters (midpoints round down); provisional when only three dimensions are reported. Rules v${FW.rule_version}. Framework based on Jeff Bezos's Day 1 / Day 2 concept.`;
</script></body></html>"""


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    run = json.load(open(sys.argv[1])); comp = company_of(run)
    if "computed" not in comp: print("Run grade.py first."); sys.exit(1)
    page = (TEMPLATE.replace("__TITLE__", html.escape(f"{comp['name']} - Day 1 / Day 2 Board Assessment")).replace("__RUN__", json.dumps(run).replace("</", "<\\/")).replace("__FW__", json.dumps(FW).replace("</", "<\\/")))
    open(sys.argv[2], "w").write(page); print(f"Dashboard written to {sys.argv[2]} ({len(page)//1024} KB)")


if __name__ == "__main__":
    main()
