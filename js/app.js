/* Landing, home, Briefcase, two-stage journey and event handling. */
const IC={home:'<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',clip:'<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 12h6M9 16h4"/>',doc:'<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',check:'<path d="m5 12 5 5 9-10"/>',upload:'<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',arrow:'<path d="M5 12h14M13 6l6 6-6 6"/>',dl:'<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',brief:'<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"/>',plus:'<path d="M12 5v14M5 12h14"/>',web:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',zip:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M12 3v12M10 7h4M10 11h4"/>',dash:'<rect x="3" y="3" width="8" height="10" rx="1.5"/><rect x="13" y="3" width="8" height="6" rx="1.5"/><rect x="13" y="11" width="8" height="10" rx="1.5"/><rect x="3" y="15" width="8" height="6" rx="1.5"/>',mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',bld:'<path d="M4 21V5l8-2v18M12 8l8 2v11M8 8h.01M8 12h.01M8 16h.01M16 13h.01M16 17h.01M3 21h18"/>'};
function ico(n,sz){ return '<svg class="ic" width="'+(sz||18)+'" height="'+(sz||18)+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+IC[n]+'</svg>'; }
function toast(msg){ const e=document.createElement('div'); e.className='toast'; e.textContent=msg; document.body.appendChild(e); setTimeout(()=>e.remove(),2800); }
const TODAY=new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
const greeting=()=>{ const h=new Date().getHours(); return h<12?'Good morning':h<18?'Good afternoon':'Good evening'; };
const nameFromEmail=e=>e.split('@')[0].split(/[._-]+/).filter(Boolean).map(w=>w[0].toUpperCase()+w.slice(1)).join(' ');
/* Deliverables are built and served by the backend per company (D.files: key -> download URL) */
function hasFile(k){ return !!(D.files&&D.files[k]); }
function dl(key){
  const url=D.files&&D.files[key];
  if(!url){ toast('This file is not available yet.'); return; }
  const a=document.createElement('a'); a.href=url; a.download=''; document.body.appendChild(a); a.click(); a.remove(); toast('Downloading…');
}
function dlBtn(k,label,icon,cls){ return hasFile(k)?'<button class="btn '+(cls||'sec')+'" data-act="dl" data-k="'+k+'">'+ico(icon||'dl',16)+label+'</button>':''; }
function head(t,s,right,eyebrow){ return '<div class="rh"><div>'+(eyebrow?'<div class="peb">'+eyebrow+'</div>':'')+'<h1>'+t+'</h1>'+(s?'<p class="sub">'+s+'</p>':'')+'</div>'+(right?'<div class="row">'+right+'</div>':'')+'</div>'; }
function initials(n){ return n.split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase(); }
/* A&M vertical logo (non-shadow version, per the brand guideline), drawn as vector so it stays crisp at any size */
const LOGO='<svg class="amlogo" viewBox="0 0 470 410" role="img" aria-label="Alvarez &amp; Marsal"><path fill="#002B49" d="M5 405 230 5h63v400h-43V90L73 405z"/><path fill="#5E8AB4" d="M198 405V195l40-68v278zM305 127l40 68v210h-40z"/><g fill="#002B49" font-family="Arial,Helvetica,sans-serif" font-size="84" text-anchor="middle"><text x="410" y="265">A</text><text x="410" y="335">&amp;</text><text x="410" y="405">M</text></g></svg>';
const LOGO_W=LOGO.replace(/#002B49/g,'#FFFFFF');   /* on navy: white mark and letters, slate bars */
const DSHORT={'1':'Customer','2':'Proxies','3':'Trends','4':'Velocity','5':'Building','6':'Liquidity'};
const coLabel=c=>(c.name||'')+(c.ticker?' ('+c.ticker+')':'');

/* ---------- landing ---------- */
function viewLanding(){
  const dimsHtml=DIMS.map(d=>'<div class="lcard rv"><div class="lnum">'+d+'</div><h3>'+esc(DIMN[d])+'</h3><ul>'+IDS.filter(i=>DIM_OF[i]===d).map(i=>'<li><b>'+i+'</b> '+esc(indName(i))+'</li>').join('')+'</ul></div>').join('');
  const an=D.defs['1.1'].anchors;
  return '<div class="land"><header class="lnav"><div class="wrap lnavi"><div class="brandrow">'+LOGO_W+'<span class="bdiv"></span><span class="bname">Board Assessment</span></div></div></header>'+
  '<section class="hero"><div class="wrap hgrid"><div><div class="eb">Day 1 / Day 2 board assessment</div><h1>Is your board Day 1 or Day 2?</h1><p class="hl">An evidence-based grade for a listed company’s board, from A to F, on six dimensions and 22 indicators, benchmarked against named peers. Public information first; board documents and your own view when you want to go deeper.</p><div class="row" style="margin-top:26px"><button class="btn inv lg" data-act="scrollm">See the methodology'+ico('arrow',16)+'</button></div>'+
  '<div class="hstats"><div><b>6</b><span>dimensions</span></div><div><b>22</b><span>indicators</span></div><div><b>A–F</b><span>grade against peers</span></div></div></div>'+
  '<div class="login" id="loginbox"><h3>Sign in</h3><p class="muted">Prepared privately for the requesting director.</p><label for="em">Email</label><input type="email" id="em" autocomplete="username"><label for="pw">Password</label><input type="password" id="pw" autocomplete="current-password"><div class="muted err" id="loginMsg"></div><button class="btn lg block" data-act="login">Sign in'+ico('arrow',16)+'</button></div></div></section>'+
  '<section class="lsec" id="method"><div class="wrap"><div class="eb rv">The method</div><h2 class="lh rv">Three steps, one readout</h2><div class="l2">'+
   [['1','Outside-in','From public information only. We read filings, proxies, earnings calls, announcements and regulator records for the company and every peer, and grade the board A–F, with trend against earlier quarters and five proposed actions.'],['2','Inside-out','Add what only the board can see: minutes, agendas, board packs, treasury and audit reports, plus an anonymous self-assessment by the directors. Grades update only where that material settles an indicator.'],['3','Board actions','The five actions proposed outside-in are tested against the board’s own material and refined into the five that matter most, each with measures and a target date.']].map(x=>'<div class="lcard rv"><div class="lnum">'+x[0]+'</div><h3>'+x[1]+'</h3><p>'+x[2]+'</p></div>').join('')+'</div></div></section>'+
  '<section class="lsec alt"><div class="wrap"><div class="eb rv">The lens</div><h2 class="lh rv">Day 1 boards stay obsessed with the customer. Day 2 boards slowly stop.</h2><p class="rv big">'+esc(D.read[0])+'</p><p class="rv">'+esc(D.read[1])+'</p></div></section>'+
  '<section class="lsec"><div class="wrap"><div class="eb rv">What is assessed</div><h2 class="lh rv">Six dimensions, 22 indicators</h2><div class="l3">'+dimsHtml+'</div></div></section>'+
  '<section class="lsec alt"><div class="wrap"><div class="eb rv">How scoring works</div><h2 class="lh rv">Every indicator is scored against written anchors</h2><p class="rv">Each indicator is scored 1 (Day 2), 3 (Mixed) or 5 (Day 1); 2 and 4 are used only where evidence sits between two anchors. Example: indicator 1.1, customer evidence in board and management attention.</p><div class="scroll rv"><table class="dt"><tr><th>1 – Day 2</th><th>3 – Mixed</th><th>5 – Day 1</th></tr><tr><td>'+esc(an['1'])+'</td><td>'+esc(an['3'])+'</td><td>'+esc(an['5'])+'</td></tr></table></div>'+
   '<h3 class="sh rv">From scores to grades</h3><div class="grades rv">'+D.scale.map((b,i)=>'<div class="gband"><span class="g g'+b.grade+'">'+b.grade+'</span><b>'+esc(b.label)+'</b><small>'+(b.min>0?b.min.toFixed(2)+(i===0?' – 5.00':' – '+(D.scale[i-1].min-0.01).toFixed(2)):'below 2.00')+'</small></div>').join('')+'</div></div></section>'+
  '<section class="lsec"><div class="wrap"><div class="eb rv">Evidence rules</div><h2 class="lh rv">What stands behind a grade</h2><div class="l3">'+[0,1,2,3,4,10].map(k=>'<div class="lcard rv"><p>'+esc(D.method[k].replace(/^\d+\s+/,''))+'</p></div>').join('')+'</div></div></section>'+
  '<section class="lsec alt"><div class="wrap"><div class="eb rv">Deliverables</div><h2 class="lh rv">Outputs from the assessment</h2><div class="l2">'+[['dash','Board dashboard','Grades, peer position, trend, the 22 indicators and the board’s actions on one screen, in the app or as a file.'],['doc','Detailed report','Executive summary, scorecard, evidence for every indicator, peer comparison, actions and appendices, in the app and in Word.']].map(x=>'<div class="lcard rv"><div class="lic">'+ico(x[0],22)+'</div><h3>'+x[1]+'</h3><p>'+x[2]+'</p></div>').join('')+'</div><div class="row" style="margin-top:26px"><button class="btn lg" data-act="tologin">Sign in to start'+ico('arrow',16)+'</button></div></div></section>'+
  '<footer class="lfoot"><div class="wrap"><img class="wordmark" src="assets/logo-wordmark.png" alt="Alvarez &amp; Marsal"><div class="draftbox"><b>DRAFT ONLY</b><p>'+DRAFT+'</p></div></div></footer></div>';
}
/* ---------- shell ---------- */
function topbar(){
  return '<header class="tb"><div class="wrap tbi"><button class="brandrow" data-act="home" aria-label="Home">'+LOGO_W+'<span class="bdiv"></span><span class="bname">Board Assessment</span></button><nav class="tnav"><button class="'+(S.page==='home'?'on':'')+'" data-act="home">Home</button><button class="'+(S.page==='journey'?'on':'')+'" data-act="newassess">Assessment</button><button class="'+(S.page==='briefcase'?'on':'')+'" data-act="briefcase">Briefcase</button></nav><div class="tr"><button class="bell" data-act="home" title="Actions" aria-label="Actions">'+ico('clip',19)+'<b>'+actions().length+'</b></button><div class="uchip2"><div class="av">'+esc(initials(S.name))+'</div><div><span>'+esc(S.name)+'</span><small>'+esc(S.email)+'</small></div></div><button class="btn ghost sm" data-act="logout">Sign out</button></div></div></header>';
}
/* Open items for the director, each with the step that resolves it */
function actions(){
  const a=[];
  if(!S.company){ if(API.on) a.push({ic:'plus',c:'o',t:'Add the first company',d:'Research a listed company’s board from public information, or add it from assessment files prepared by the A&M team.',w:'To start',act:'addco',b:'Add a company'}); return a; }
  if(S.final) a.push({ic:'check',c:'g',t:'Review the board’s five actions',d:'The '+S.period+' board assessment of '+CO+' is complete and saved to your Briefcase.',w:'Ready',act:'openactions',b:'Open board actions'});
  else if(S.oiDone) a.push({ic:'upload',c:'o',t:'Add board material to complete the assessment',d:'Board documents and the directors’ anonymous self-assessment refine the grades and the board’s five actions.',w:'Inside-out',act:'newassess',b:'Continue'});
  else a.push({ic:'clip',c:'o',t:'Complete the '+S.period+' assessment of '+CO,d:'Outside-in from public information, then inside-out with your board’s own material.',w:'Outside-in',act:'newassess',b:'Start'});
  const behind=S.final?priorActionsList().filter(x=>x.status==='behind'||x.status==='not_started').length:0;
  if(behind) a.push({ic:'clip',c:'o',t:behind+' of last quarter’s actions need attention',d:'Behind plan or not started. Your readout sets out what happened and how to get back on track.',w:'Next board meeting',act:'openfinal',b:'Review'});
  else if(!S.final&&D.prior&&D.prior.actions&&D.prior.actions.length) a.push({ic:'brief',c:'',t:'Check progress on last quarter’s actions',d:'The '+D.prior.period+' readout set '+D.prior.actions.length+' board actions. Their status is reviewed in the inside-out stage.',w:'Before inside-out',act:'briefcase',b:'Open Briefcase'});
  return a;
}
function draw(top){
  const y=window.scrollY, root=$('#app');
  if(S.page==='landing') root.innerHTML=viewLanding();
  else { const pages={home:pHome,briefcase:pBriefcase,journey:pJourney}; root.innerHTML=topbar()+'<main class="mainc">'+pages[S.page]()+'</main><footer class="afoot2"><div class="wrap">'+DRAFT+'</div></footer>'; }
  if(S.page==='journey'&&S.stage===2&&S.sub==='input') loadSurvey();
  observe(); watchDash(); window.scrollTo(0,top?0:y);
}
/* The bar's Dashboard shortcut appears only once the grade card (which has its own dashboard button) is scrolled away */
let dashWatch=null;
function watchDash(){
  if(dashWatch){ dashWatch.disconnect(); dashWatch=null; }
  const b=$('.jdash'), card=$('.gcard'); if(!b||!card||!('IntersectionObserver' in window)) return;
  b.classList.add('hide'); dashWatch=new IntersectionObserver(es=>es.forEach(e=>b.classList.toggle('hide',e.isIntersecting)),{rootMargin:'-150px 0px 0px 0px'}); dashWatch.observe(card);
}
function observe(){ const els=document.querySelectorAll('.rv'); if(!els.length) return; if(!('IntersectionObserver' in window)){ els.forEach(e=>e.classList.add('in')); return; } const io=new IntersectionObserver(es=>es.forEach(e=>{ if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); } }),{threshold:.12}); els.forEach(e=>io.observe(e)); }
/* page band: navy title area that the first cards overlap */
function band(inner){ return '<section class="band"><div class="wrap">'+inner+'</div></section><div class="wrap pagec">'; }
/* ---------- home ---------- */
function pHome(){
  const ac=actions(), cs=API.companies, done=cs.filter(c=>c.stages&&c.stages.outside_in).length, cur=companyOf();
  let h=band(head(greeting()+(S.name?', '+esc(S.name.split(' ')[0]):''),'Your board assessments, readouts and open actions in one place.','<button class="btn inv" data-act="freshassess">'+ico('plus',16)+'New assessment</button>',TODAY)+
   '<div class="kpis kband">'+kpiTile('Companies on file',cs.length,done+' with an outside-in assessment')+kpiTile('Current assessment',S.company?esc(cur.short||CO):'–',S.company?esc(S.period)+' · '+(S.final?'complete':S.oiDone?'inside-out pending':'not started'):'No company yet')+kpiTile('Final readouts',cs.filter(c=>c.stages&&c.stages.inside_out).length,'Inside-out complete')+kpiTile('Open actions',ac.length,'For your attention')+'</div>');
  h+='<div class="card"><div class="row sb chead"><h3 class="m0">Actions</h3><span class="cnt">'+ac.length+' open</span></div>'+ac.map(n=>'<div class="li"><div class="ib '+n.c+'">'+ico(n.ic)+'</div><div class="lb"><b>'+esc(n.t)+'</b><div class="muted">'+esc(n.d)+'</div></div><div class="lr"><small>'+esc(n.w)+'</small><button class="btn sec sm" data-act="'+n.act+'">'+esc(n.b)+'</button></div></div>').join('')+'</div>';
  h+='<div class="card"><div class="row sb chead"><h3 class="m0">Companies</h3>'+(API.on?'<button class="btn sec sm" data-act="addco">'+ico('plus',14)+'Add a company</button>':'')+'</div>'+(cs.length?'<div class="scroll"><table class="tbl port"><tr><th>Company</th><th>Peers</th><th>Period</th><th>Outside-in</th><th>After inside-out</th><th></th></tr>'+
   cs.map(c=>{ const g=c.grades||{}; return '<tr><td><b>'+esc(c.name)+'</b><div class="muted">'+esc(c.ticker||'')+(c.source==='research'?' · researched':c.source==='imported'?' · imported':'')+'</div></td><td>'+esc((c.peers||[]).join(', '))+'</td><td>'+esc(c.period||'')+'</td><td>'+(g.oi?gchip(g.oi)+' <span class="muted">'+esc((c.labels||{}).oi||'')+'</span>':'<span class="muted">–</span>')+'</td><td>'+(g.io?gchip(g.io):'<span class="muted">Not yet</span>')+'</td><td class="ra"><button class="btn sm'+(c.id===S.company?'':' sec')+'" data-act="pickco" data-id="'+esc(c.id)+'">'+(c.id===S.company?'Continue':'Open')+'</button></td></tr>'; }).join('')+'</table></div>':'<p class="muted m0">'+(API.on?'No companies yet. Add a listed company to research its board from public information, or import assessment files prepared by the A&amp;M team.':'No companies are available. Companies are held by the assessment service, which is not connected; your A&amp;M engagement team can give you access.')+'</p>')+'</div>';
  return h+'</div>';
}
function kpiTile(l,v,s){ return '<div class="kpi"><div class="kl">'+l+'</div><div class="kv2v">'+v+'</div><div class="ks">'+s+'</div></div>'; }
function briefItems(){
  const out=[];
  API.companies.forEach(c=>{
    const g=c.grades||{}, f=c.files||{};
    if(c.stages&&c.stages.outside_in) out.push({id:c.id,title:c.name+' · '+c.period,meta:(g.oi?'Outside-in '+g.oi:'')+(g.io?' · after inside-out '+g.io:' · inside-out not yet run'),grade:g.io||g.oi||'NA',
      files:[['io_docx','Report (Word)','doc'],['io_html','Dashboard (HTML)','web'],['oi_docx','Outside-in (Word)','doc']].filter(x=>f[x[0]])});
    if(c.prior_period&&f.prior_docx) out.push({id:c.id,title:c.name+' · '+c.prior_period,meta:'Earlier quarter, outside-in',grade:'NA',files:[['prior_docx','Report (Word)','doc']],prior:true});
  });
  return out;
}
function pBriefcase(){
  const it=briefItems();
  return band('<button class="bklink inv" data-act="home">'+ico('arrow',15)+'Back to Home</button>'+head('Briefcase','Every readout on file. Download the files, or reopen a readout and its dashboard.','<button class="btn inv" data-act="freshassess">'+ico('plus',16)+'New assessment</button>','Readouts'))+
  (it.length?it.map(x=>'<div class="card bcard"><div class="bcrow"><div class="bcl">'+(x.grade!=='NA'?'<span class="gsq g'+esc(x.grade)+'">'+esc(x.grade)+'</span>':'<span class="gsq gNA">'+ico('doc',18)+'</span>')+'<div><b class="bt2">'+esc(x.title)+'</b><div class="muted">'+esc(x.meta)+'</div></div></div><div class="row">'+
   x.files.map(f=>'<a class="btn sec sm" href="'+esc(companyOf(x.id).files[f[0]])+'" download>'+ico(f[2],16)+f[1]+'</a>').join('')+(x.prior?'':'<button class="btn sm" data-act="openco" data-id="'+esc(x.id)+'">Open readout</button>')+'</div></div></div>').join(''):'<div class="card"><p class="muted m0">Nothing in the Briefcase yet.</p></div>')+'</div>';
}
/* ---------- journey (sticky context bar + stepper) ---------- */
function stepperJ(){
  const items=[[1,'Outside-in','Public information'],[2,'Inside-out','Board material and self-assessment'],[3,'Board actions','The five that matter most']];
  const done=n=>(n===1&&S.oiDone)||(n===2&&S.ioDone)||(n===3&&S.seen3);
  const dash=S.ioDone?'io':S.oiDone?'oi':'';
  return '<div class="jwrap"><div class="wrap jbar"><div class="jco"><span class="jic">'+ico('bld',18)+'</span><div><b>'+esc(COFULL||'New assessment')+'</b><span>'+(TK?esc(TK)+' · ':'')+esc(S.period)+'</span></div></div><div class="journey">'+items.map(it=>{ const n=it[0], cls=done(n)?'done':(S.stage===n?'on':''); const canGo=done(n)||n===S.stage||(n===2&&S.oiDone)||(n===3&&S.ioDone);
    return '<button class="jstep '+cls+'" '+(canGo?'data-act="jgo" data-n="'+n+'"':'disabled')+'><i>'+(done(n)?ico('check',14):n)+'</i><div><b>'+it[1]+'</b><span>'+it[2]+'</span></div></button>'; }).join('<div class="jline"></div>')+'</div>'+
    '<div class="jact">'+(dash?'<button class="btn sm jdash" data-act="dash" data-s="'+dash+'">'+ico('dash',15)+'Dashboard</button>':'')+'</div></div></div>';
}
function pJourney(){
  if(!S.company){ S.stage=1; S.sub='setup'; }
  let h=stepperJ()+'<div class="wrap jbody">'+backLink();
  if(S.stage===1) h+=({setup:stage1Setup,summary:stage1Summary}[S.sub]||stage1Setup)();
  else if(S.stage===2) h+=({input:stage2Input,live:stageLive,summary:stage2Summary}[S.sub]||stage2Input)();
  else h+=stage3();
  return h+'</div>';
}
function backLink(){
  const b=S.stage===3?['back2','Back to the inside-out readout']:S.stage===2?['back1','Back to the outside-in readout']:['home','Back to Home'];
  return '<button class="bklink" data-act="'+b[0]+'">'+ico('arrow',15)+b[1]+'</button>';
}
/* ---------- stage 1 ---------- */
function stage1Setup(){
  const A=S.add=S.add||newAdd(); if(A.tab==='file'&&!API.companies.length) A.tab='research';
  const tabs=[['research','New company']].concat(API.companies.length?[['file','Company on file']]:[]).concat(API.on?[['import','Import assessment files']]:[]);
  const busy=A.busy||!!A.job, go={research:['addresearch','Generate outside-in assessment'],file:['start1','Open outside-in assessment'],import:['addimport','Import and open']}[A.tab];
  const off=(A.tab==='research'&&!API.research.enabled)||(A.tab==='import'&&!API.on);
  return head('Outside-in assessment','Research a listed company and its peers from public information, or open a company already on file.','','Stage 1 of 3')+
  '<div class="card acc" id="coform"><h3>Company and peers</h3>'+(busy?'':'<div class="seg2">'+tabs.map(x=>'<button class="'+(A.tab===x[0]?'on':'')+'" data-act="addtab" data-t="'+x[0]+'">'+x[1]+'</button>').join('')+'</div>')+addFields()+
  (busy||A.tab==='import'?'':'<label class="pl"><input type="checkbox" id="listed"'+(S.listed?' checked':'')+'> I confirm the company and its peers are listed.</label>')+addErr()+
  (busy?'':'<details class="guard"><summary>Sources we rely on</summary><div class="dbody"><p><b>Used:</b> regulators and exchanges, company investor-relations sites, established news and trade press, proxy advisors, rating agencies and sell-side research, sector conference presentations, sustainability and integrated reports.</p><p><b>Not used:</b> social media posts by individuals, anonymous forums, unverified blogs and employee-review sites.</p></div></details>')+'</div>'+
  (busy||A.tab!=='research'?'':ownDocsCard())+(busy?'':priorCard(A.tab!=='file'||!S.company))+
  (busy?'':'<div class="row sb"><button class="btn sec" data-act="home">Cancel</button><button class="btn lg" data-act="'+go[0]+'"'+(off?' disabled':'')+'>'+go[1]+ico('arrow',16)+'</button></div>');
}
/* The team's own material on the company, read with the public research (company only, not the peers) */
function ownDocsCard(){ const fs=S.add.files||[];
  return '<div class="card acc"><h3>Your own documents (optional)</h3><p class="muted">Analyst notes, earlier work or other material on the company. Claude reads it alongside the public record, for the company only (not the peers), and cites anything it uses as a source marked “provided”. PDF, Word or text, up to 25 MB per file and 10 files.</p>'+
   '<div class="frow"><input type="file" id="oifiles" multiple accept=".pdf,.docx,.txt,.md" aria-label="Your own documents"></div>'+(fs.length?'<div class="chips">'+fs.map((f,i)=>'<div class="chip">'+esc(f.name)+'<button data-act="rmoifile" data-i="'+i+'" aria-label="Remove '+esc(f.name)+'">×</button></div>').join('')+'</div>':'')+'</div>'; }
/* Earlier assessments of this company on file; up to two can be compared with this quarter. fresh: a company not yet on file, so the list is empty */
function priorCard(fresh){
  const pr=fresh?[]:(D.priors||[]).filter(p=>p.period!==S.period).slice().sort((a,b)=>a.period<b.period?1:-1), n=fresh?0:S.priorSel.length;
  return '<div class="card acc"><h3>Earlier assessments (for trend)</h3>'+(pr.length?'<p class="muted">Choose up to two earlier assessments of '+esc(CO)+' to compare with this quarter.</p><div class="plist">'+
   pr.map(p=>{ const c=compute(p.scores,p.stage==='inside_out'?THR.io:THR.oi), on=S.priorSel.indexOf(p.period)>=0;
     return '<label class="pitem'+(on?' on':'')+(!on&&n>=2?' dis':'')+'"><input type="checkbox" data-act="psel" value="'+esc(p.period)+'"'+(on?' checked':'')+(!on&&n>=2?' disabled':'')+'><b>'+esc(p.period)+'</b><span class="muted">'+(p.stage==='inside_out'?'Outside-in and inside-out':'Outside-in')+'</span>'+gchip(c.overall.grade)+'</label>'; }).join('')+
   '</div><p class="ks">'+n+' of 2 selected</p>':'<p class="muted">Choose up to two earlier assessments to compare with this quarter.</p><div class="plist pempty">'+ico('clip',18)+'<span>No earlier assessments '+(fresh?'yet':'of '+esc(CO)+' yet')+'. Each completed assessment is listed here, so in a later quarter you can pick up to two to show the trend.</span></div><p class="ks">0 of 2 selected</p>')+'</div>';
}
function finish1(){ S.oiDone=true; S.stage=1; S.sub='summary'; buildHistory(); draw(true); }
function findingsList(stage){ return ((stage==='io'?D.findings_io:D.findings_oi)||[]).map(x=>'<li>'+codes(x)+'</li>').join(''); }
/* Grade summary card shown at the top of each stage's result */
function deliveryCard(stage,m){
  const io=stage==='io', L=io?m.io:m.oi, last=S.history.length?S.history[S.history.length-1]:null, g=L.overall.grade||'NA';
  return '<div class="card gcard"><div class="gcl"><div class="kl">Overall grade · '+(io?'after inside-out':'outside-in')+'</div><div class="kgrade big"><span class="gsq xl g'+g+'">'+(L.overall.grade||'–')+'</span><div><b>'+esc(L.overall.label)+'</b><div class="ks">'+(L.overall.avg!=null?L.overall.avg.toFixed(2)+' of 5.00':'')+'</div>'+
   (io?'<div class="ks">Outside-in '+gchip(m.oi.overall.grade)+' → '+gchip(m.io.overall.grade)+'</div>':'')+(last?'<div class="ks">'+arrow(m.oi.overall.grade,last.overall.grade)+' · '+esc(last.period)+'</div>':'')+'</div></div>'+
   '<div class="dimstrip">'+DIMS.map(d=>{ const x=L.dims[d]; return '<div title="'+esc(DIMN[d])+'"><span class="g g'+(x.grade||'NA')+'">'+(x.grade||'–')+'</span><small>'+DSHORT[d]+'</small></div>'; }).join('')+'</div>'+
   '<button class="btn block" data-act="dash" data-s="'+stage+'">'+ico('dash',16)+'Open the dashboard</button></div>'+
   '<div class="gcr"><div class="eb m0">Three headline findings</div><ol class="flist">'+findingsList(stage)+'</ol>'+
   (io&&priorActionsList().length?'<div class="eb">Progress on last quarter’s actions</div><div class="scroll"><table class="dt"><tr><th>Prior action</th><th>Status</th></tr>'+priorActionsList().map(a=>'<tr><td>'+esc(a.heading)+'</td><td><span class="st-'+esc(a.status)+'">'+esc(a.status.replace(/_/g,' '))+'</span></td></tr>').join('')+'</table></div>':'')+'</div></div>';
}
function reportTabs(stage,m){
  return '<div class="tabs">'+[['report','Report'],['detail','Dimension detail'],['peers','Peers'],['sources','Sources'],['method','Method']].map(x=>'<button class="tab'+(S.tab===x[0]?' on':'')+'" data-act="tab" data-t="'+x[0]+'">'+x[1]+'</button>').join('')+'</div><div class="paper" id="report">'+({report:tReport,detail:tDetail,peers:tPeers,sources:tSources,method:tMethod}[S.tab]||tReport)(stage,m)+'<div class="draft">'+DRAFT+'</div></div>';
}
function stage1Summary(){
  const m=M();
  return head('Outside-in readout',esc(COFULL)+' against '+esc(listJoin(PEERS))+' · public information only',planBtn('oi')+dlBtn('oi_docx','Report (Word)','doc'),'Stage 1 of 3 · complete')+deliveryCard('oi',m)+priorCard(false)+
  '<h2 class="sech">What the board could do next</h2><p class="muted">Five actions from the outside-in assessment. The inside-out stage tests them against the board’s own material and refines them into the final five.</p>'+D.actions.map(actCard).join('')+
  '<h2 class="sech">Detailed report</h2>'+reportTabs('oi',m)+
  '<div class="card dlcard nextcard"><div class="dltxt"><h3 class="m0">Next: inside-out</h3><p class="muted m0">Add board documents and invite directors to an anonymous self-assessment. Grades are refined where that material settles an indicator, and the five actions are refined with them.</p></div><div class="row"><button class="btn lg" data-act="to2">Continue to inside-out'+ico('arrow',16)+'</button></div></div>'+
  stickyNext('Next: add the board’s own material','to2','Continue to inside-out');
}
/* One action, as on the action plan: heading, target, what to do (with its evidence) and how progress is measured */
function actCard(a){ return '<div class="pact"><div class="pnum">'+esc(a.n)+'</div><div class="pbody"><div class="phead"><h3>'+esc(a.heading)+'</h3><span class="ptgt">Target '+esc(a.target||'–')+'</span></div><p>'+codes(a.description)+'</p>'+
  ((a.measures||[]).length?'<div class="kl">How progress is measured</div><ul class="pmeas">'+a.measures.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+'</div></div>'; }
/* A bar fixed to the bottom of the screen with the next step, so it is in reach however far the report is scrolled */
function stickyNext(text,act,label){ return '<div class="stickpad"></div><div class="stickynext"><div class="wrap"><span>'+text+'</span><button class="btn" data-act="'+act+'">'+label+ico('arrow',16)+'</button></div></div>'; }
function planBtn(stage){ const n=((stage==='io'?(D.io||{}).actions:D.actions)||[]).length; return '<button class="btn sec" data-act="plan" data-s="'+stage+'">'+ico('clip',16)+'Action plan <span class="bcnt">'+n+'</span></button>';
}
/* ---------- stage 2 ---------- */
function stage2Input(){
  const canRun=API.on&&API.research.enabled;
  let h=head('Inside-out: add what only the board can see','Board documents carry more weight than public sources. Grades change only where something you supply settles an indicator.','','Stage 2 of 3');
  if(ioFinal()) h+='<div class="notice ok"><b>An inside-out assessment for '+esc(S.period)+' is already on file.</b> Open it, or add new material below to run it again. <button class="btn sm" data-act="openio" style="margin-left:10px">Open the readout</button></div>';
  if(!canRun) h+='<div class="notice">Scoring of your own board documents is not available in this version. Your A&amp;M engagement team can run the inside-out stage with you.</div>';
  h+='<div class="card acc"><h3>What would move the assessment most</h3><p class="muted">Your material is used only for this company’s assessment, cited by document and date (never by person), and never used to assess a peer. Where public evidence is thin or inferred:</p><ul class="flist">'+((D.addl||[]).length?D.addl.map(x=>'<li>'+esc(x.replace(/^•\s*/,''))+'</li>').join(''):'<li>Board and committee minutes and board packs settle the most indicators.</li>')+'</ul><p class="muted m0">The first seven documents below settle the most indicators.</p></div>';
  h+='<div class="card acc"><h3>1. Board documents</h3>'+docMeter()+'<p class="ks">PDF, Word or text files, up to 25 MB each.</p><div class="scroll"><table class="tbl"><tr><th style="width:70px">Provided</th><th>Document</th><th>Indicators it informs</th><th>File</th></tr>';
  D.docs.forEach((d,i)=>{ const n=i+1,s=S.docs[n]=S.docs[n]||{on:false,files:[]}; h+='<tr><td><input type="checkbox" data-act="doc" data-n="'+n+'" aria-label="Provided"'+(s.on?' checked':'')+' disabled'+'></td><td>'+n+'. '+esc(d[0])+(n<=7?' <span class="chip">priority</span>':'')+'</td><td>'+String(d[1]||'').split(' ').filter(Boolean).map(x=>'<span class="chip">'+esc(x)+'</span>').join('')+'</td><td><input type="file" data-act="docfile" data-n="'+n+'" accept=".pdf,.docx,.txt,.md" multiple aria-label="Add files">'+(s.files.length?'<div class="chips">'+s.files.map((f,k)=>'<div class="chip">'+esc(f.name)+'<button data-act="rmdoc" data-n="'+n+'" data-i="'+k+'" aria-label="Remove '+esc(f.name)+'">×</button></div>').join('')+'</div>':'')+'</td></tr>'; });
  h+='</table></div></div>';
  h+='<div class="card acc"><h3>2. Other information</h3><p class="muted">Anything else that bears on how the board works: committee papers, advisor reports, investor correspondence. Listed in the report’s sources. Up to 25 MB per file.</p><div class="frow"><input type="file" id="otherfiles" multiple accept=".pdf,.docx,.txt,.md"></div><div class="chips">'+S.other.map((f,i)=>'<div class="chip">'+esc(f.name)+'<button data-act="rmother" data-i="'+i+'" aria-label="Remove">×</button></div>').join('')+'</div></div>';
  h+=surveyCard();
  h+='<div class="row sb"><button class="btn sec" data-act="back1">Back to outside-in readout</button><div class="row"><span class="muted err" id="ioMsg"></span><button class="btn lg" id="start2btn" data-act="start2"'+(canGenerateIO()?'':' disabled')+'>Generate inside-out assessment'+ico('arrow',16)+'</button></div></div><p class="ks iowhy" id="iowhy">'+esc(ioWhy())+'</p>';
  return h;
}
/* Live inside-out: documents and answers go to the backend, which scores them and returns the updated view */
function stageLive(){
  const j=S.job||{progress:0,message:'Uploading your material…',log:[]};
  return head('Reading the board’s own material','Each document and the pooled self-assessment answers are read against the indicators they bear on and the grades are re-checked against the scoring rules. This can take several minutes.','','Stage 2 of 3')+'<div class="card" id="livecard">'+jobView(j).replace('You can close this panel; the work continues in the background.','You can leave this page; the work continues in the background.')+'</div>';
}
function updLive(j){ const c=$('#livecard'); if(c&&S.sub==='live') c.innerHTML=jobView(j); }
/* companies with an inside-out run in flight from this page (uploading or being scored): one paid run at a time each */
const ioRuns=new Set();
const ioBusy=()=>ioRuns.has(S.company)||!!(S.job&&S.job.status!=='done'&&S.job.status!=='error');
async function startLiveIO(){
  S.stage=2; S.sub='live';
  if(ioBusy()){ draw(true); return; }
  /* the run belongs to this company: if another one is opened meanwhile, its result is only announced */
  const cid=S.company, co=COFULL, mine=()=>S.company===cid, enc=encodeURIComponent(cid);
  const docSlots=Object.keys(S.docs).map(n=>[+n,S.docs[n].files.slice()]), other=S.other.slice(), mode=S.mode;
  ioRuns.add(cid); S.job={status:'uploading',progress:0,message:'Uploading your material…',log:[]}; draw(true);
  const tick=x=>{ if(mine()){ S.job=x; updLive(x); } };
  try{
    const docs=[]; for(const [n,fs] of docSlots) for(const f of fs) docs.push({slot:n,name:f.name,mime:f.file.type,data_b64:await fileToB64(f.file)});
    for(const f of other) docs.push({slot:0,name:f.name,mime:f.file.type,data_b64:await fileToB64(f.file)});
    await sendPaperReturns(cid);  /* returned Word questionnaires join the anonymous responses */
    const r=await startJob('/companies/'+enc+'/inside-out',{mode:mode,documents:docs});
    await pollJob(r.job_id,tick);
    const v=await api('/companies/'+enc+'/view');
    ioRuns.delete(cid);
    if(!mine()){ refreshCompanies().catch(()=>{}); toast('Inside-out for '+co+' is ready.'); return; }
    const keep={history:S.history,priorSel:S.priorSel,mode:S.mode}; setData(v); Object.assign(S,keep);
    await refreshCompanies(); finish2();
  }catch(e){
    ioRuns.delete(cid);
    if(!mine()){ toast('Inside-out for '+co+' did not finish: '+e.message); return; }
    S.job=Object.assign({},S.job||{},{status:'error',error:e.message,log:(S.job&&S.job.log)||[]}); updLive(S.job);
  }
}
function finish2(){ S.ioDone=true; S.final=true; S.saved=true; try{ localStorage.setItem('d1d2:saved','1'); }catch(e){} S.stage=2; S.sub='summary'; S.tab='report'; draw(true); }
/* The inside-out result is the final readout: grades, dashboard, downloads and the full report in one place */
function stage2Summary(){
  const m=M();
  const grp=(t,sub,btns)=>btns?'<div class="card dgroup"><h3 class="m0">'+t+'</h3><p class="muted">'+sub+'</p><div class="col">'+btns+'</div></div>':'';
  let h=head('Your board assessment',esc(COFULL)+' · '+esc(S.period)+' · complete and saved to your Briefcase',planBtn('io')+'<button class="btn sec" data-act="briefcase">'+ico('brief',16)+'Briefcase</button>','Stage 2 of 3 · complete')+deliveryCard('io',m);
  const dls=grp('Board assessment','Both grades side by side, peer comparison, updated actions and sources.',dlBtn('io_docx','Report (Word)','doc','')+dlBtn('io_html','Dashboard (HTML)','web'))+
   grp('Outside-in view','The public-information report for the same period.',dlBtn('oi_docx','Report (Word)','doc')+dlBtn('oi_html','Dashboard (HTML)','web'))+
   grp('Supporting files','The earlier-quarter report and the director questionnaire.',dlBtn('prior_docx','Earlier quarter (Word)','doc')+dlBtn('quest','Questionnaire (Word)','doc'));
  if(dls) h+='<h2 class="sech">Download the readout</h2><div class="grid3">'+dls+'</div>';
  return h+'<h2 class="sech">Detailed report</h2>'+reportTabs('io',m)+
   '<div class="card dlcard nextcard"><div class="dltxt"><h3 class="m0">Next: the board’s five actions</h3><p class="muted m0">The outside-in actions, refined by what the board’s own material and the directors’ self-assessment showed.</p></div><div class="row"><button class="btn lg" data-act="to3">See the board’s five actions'+ico('arrow',16)+'</button></div></div>'+
   stickyNext('Next: the board’s five actions','to3','See the board’s five actions');
}
/* ---------- stage 3: the five actions, refined by the inside-out assessment ---------- */
function stage3(){
  S.seen3=true; const acts=D.io?D.io.actions:D.actions, pal=priorActionsList(), back=D.io&&D.io.back?D.io.back:[];
  let h=head('The board’s five actions',esc(COFULL)+' · '+esc(S.period)+' · refined by the inside-out assessment','<button class="btn sec" data-act="dash" data-s="io">'+ico('dash',16)+'Dashboard</button>'+dlBtn('io_docx','Report (Word)','doc'),'Stage 3 of 3 · summary');
  h+='<div class="card acc"><p class="m0">The outside-in assessment proposed five actions from public information. The inside-out assessment tested them against the board’s own documents and the directors’ anonymous self-assessment. These are the five that stand, in priority order, each tied to its evidence and with measures to track progress.</p></div>';
  h+=acts.map(actCard).join('');
  if(pal.length) h+='<h2 class="sech">Last quarter’s actions</h2><div class="card">'+pal.map(a=>{ const b=back.find(x=>x.id===a.id);
    return '<div class="dact st"><i class="sd st-'+esc(a.status)+'"></i><div><b>'+esc(a.heading)+'</b><div class="ks"><span class="st-'+esc(a.status)+'">'+esc(a.status.replace(/_/g,' '))+'</span>'+(a.note?' · '+codes(a.note):'')+'</div>'+
     (b?'<details class="pback"><summary>How to get back on track</summary><div class="dbody"><p><b>What happened.</b> '+esc(b.what)+'</p><p><b>Root cause.</b> '+esc(b.cause)+'</p><p><b>To prevent it recurring.</b> '+esc(b.prevent)+'</p></div></details>':'')+'</div></div>'; }).join('')+'</div>';
  h+='<details class="card orig"><summary>The outside-in proposals these were refined from</summary><div class="dbody">'+D.actions.map(a=>'<div class="dact"><span>'+esc(a.n)+'</span><div><b>'+esc(a.heading)+'</b><div class="ks">'+codes(a.description)+'</div></div></div>').join('')+'</div></details>';
  return h+'<div class="row sb"><button class="btn sec" data-act="back2">Back to the inside-out readout</button><button class="btn" data-act="briefcase">'+ico('brief',16)+'Briefcase</button></div>';
}
/* Reopen a readout from the Briefcase or the company list */
function openReadout(){
  S.page='journey'; S.oiDone=true; buildHistory();
  if(D.io){ S.ioDone=true; S.final=true; S.stage=2; S.sub='summary'; }
  else { S.stage=1; S.sub='summary'; }
  S.tab='report'; draw(true);
}
async function pickCompany(id,then){ if(id!==S.company||!S.oiDone){ try{ await selectCompany(id); }catch(e){ toast('Could not open the company: '+e.message); return; } } then(); }
/* ---------- events ---------- */
document.addEventListener('click',e=>{
  const t=e.target.closest('[data-act]'); if(!t||t.disabled) return; const a=t.dataset.act;
  if(a==='tologin'){ const b=$('#loginbox'); if(b){ b.scrollIntoView({behavior:'smooth',block:'center'}); const i=$('#em'); if(i) i.focus(); } }
  else if(a==='scrollm'){ const m=$('#method'); if(m) m.scrollIntoView({behavior:'smooth'}); }
  else if(a==='login'){ const em=(($('#em')||{}).value||'').trim(); if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)){ const m=$('#loginMsg'); if(m) m.textContent='Enter your email address.'; return; } S.email=em; S.name=nameFromEmail(em); S.page='home'; draw(true); }
  else if(a==='logout'){ signOut(); }
  else if(a==='home'){ closeDrawer(); S.page='home'; draw(true); }
  else if(a==='briefcase'){ closeDrawer(); S.page='briefcase'; draw(true); }
  else if(a==='newassess'){ closeDrawer(); S.page='journey'; if(!S.oiDone){ S.stage=1; S.sub='setup'; } else if(S.final){ S.stage=2; S.sub='summary'; } else if(S.stage!==2){ S.stage=1; S.sub='summary'; } draw(true); }
  else if(a==='freshassess'){ closeDrawer(); if(!addBusy()){ resetRun(); S.add=newAdd(); } S.page='journey'; S.stage=1; S.sub='setup'; draw(true); }
  else if(a==='openfinal'||a==='openio'){ openReadout(); }
  else if(a==='pickco'){ pickCompany(t.dataset.id,()=>{ if(!addBusy()) S.add=newAdd('file'); S.page='journey'; if(S.oiDone){ S.stage=S.ioDone?2:1; S.sub='summary'; } else { S.stage=1; S.sub='setup'; } draw(true); }); }
  else if(a==='openco'){ pickCompany(t.dataset.id,openReadout); }
  else if(a==='addco'){ closeDrawer(); if(!addBusy()) S.add=newAdd(); S.page='journey'; S.stage=1; S.sub='setup'; draw(true); }
  else if(a==='addtab'){ S.add.tab=t.dataset.t; S.add.err=''; draw(); }
  else if(a==='addpeer'){ S.add.peers.push({name:'',ticker:''}); draw(); }
  else if(a==='rmpeer'){ S.add.peers.splice(+t.dataset.i,1); draw(); }
  else if(a==='addresearch'){ if(!S.listed){ S.add.err='Please confirm the company and its peers are listed.'; draw(); return; } startResearch(); }
  else if(a==='addimport'){ startImport(); }
  else if(a==='rmoifile'){ S.add.files.splice(+t.dataset.i,1); redrawKeep(); }
  else if(a==='jobback'){ S.add.job=null; S.add.busy=false; draw(); }
  else if(a==='dash'){ openDash(t.dataset.s); }
  else if(a==='plan'){ openPlan(t.dataset.s); }
  else if(a==='dreport'){ const st=S.dashStage; closeDrawer(); S.tab='report'; if(S.page!=='journey'||(st==='io'?S.stage!==2:S.stage!==1)){ S.page='journey'; S.stage=st==='io'?2:1; S.sub='summary'; draw(true); } else draw(); const r=$('#report'); if(r) r.scrollIntoView({behavior:'smooth'}); }
  else if(a==='dclose'){ closeDrawer(); }
  else if(a==='jgo'){ const n=+t.dataset.n; S.stage=n; if(n===1) S.sub=S.oiDone?'summary':'setup'; else if(n===3) S.sub='summary'; else S.sub=ioBusy()?'live':S.ioDone?'summary':'input'; draw(true); }
  else if(a==='dl'){ dl(t.dataset.k); }
  else if(a==='rmother'){ S.other.splice(+t.dataset.i,1); redrawKeep(); }
  else if(a==='rmdoc'){ const d=S.docs[+t.dataset.n]; d.files.splice(+t.dataset.i,1); d.on=d.files.length>0; redrawKeep(); }
  else if(a==='rmq'){ S.qFiles.splice(+t.dataset.i,1); updSurvey(); }
  else if(a==='start1'){ if(!S.listed){ S.add.err='Please confirm the company and its peers are listed.'; draw(); return; } S.add.err=''; finish1(); }
  else if(a==='to2'){ S.stage=2; S.sub=ioBusy()?'live':S.ioDone?'summary':'input'; draw(true); }
  else if(a==='to3'){ S.stage=3; S.sub='summary'; draw(true); }
  else if(a==='back2'){ S.stage=2; S.sub='summary'; draw(true); }
  else if(a==='openactions'){ openReadout(); if(D.io){ S.stage=3; S.sub='summary'; draw(true); } }
  else if(a==='dtab'){ S.dtab=t.dataset.t; redrawDrawer(); }
  else if(a==='back1'){ S.stage=1; S.sub='summary'; draw(true); }
  else if(a==='clearsa'){ for(let i=1;i<=D.q.length;i++) S.answers[i]=''; S.ratings={}; draw(); }
  else if(a==='start2'){ const sv=surveyNow(); if(sv.n<sv.v.min){ $('#ioMsg').textContent='At least '+sv.v.min+' self-assessment responses are needed; '+sv.n+' so far.'; return; } startLiveIO(); }
  else if(a==='tab'){ S.tab=t.dataset.t; draw(); }
  else if(a==='srcf'){ S.srcf=t.dataset.f; draw(); }
  else if(a==='ind'){ showInd(t.dataset.i); }
  else if(a==='dimx'){ const d=t.dataset.d, k=S.rdim.indexOf(d); if(k>=0) S.rdim.splice(k,1); else S.rdim.push(d); t.classList.toggle('open',k<0); t.closest('table').querySelectorAll('tr.subr[data-d="'+d+'"]').forEach(r=>r.hidden=k>=0); }
  else if(a==='ev'){ showEv(t.dataset.c); }
  else if(a==='close'){ $('#modal').classList.remove('on'); }
});
/* a returned questionnaire counts as a response only once, and only if at least one question was answered */
async function loadQuestionnaires(files){
  for(const f of files){
    if(S.qFiles.some(q=>q.name===f.name&&q.size===f.size)){ toast(f.name+' is already in the list.'); continue; }
    try{ const r=await parseQuestionnaire(f), n=r.answers.filter(x=>(x||'').trim()).length;
      if(!n){ toast(f.name+' has no answers, so it was not added.'); continue; }
      S.qFiles.push({name:f.name,size:f.size,answers:r.answers,ratings:r.ratings,n:n}); }
    catch(err){ toast('Could not read '+f.name+': '+err.message); }
  }
  updSurvey();
}
function resetRun(){ S.oiDone=false; S.ioDone=false; S.final=false; S.job=null; S.docs={}; for(let i=1;i<=D.docs.length;i++) S.docs[i]={on:false,files:[]}; S.answers={}; for(let i=1;i<=D.q.length;i++) S.answers[i]=''; S.ratings={}; S.other=[]; S.qFiles=[]; S.survey=null; S.seen3=false; }
const addBusy=()=>!!(S.add&&(S.add.job||S.add.busy));
/* Sign-out: clear what this browser keeps and reload, which also ends any polling still running for the last user */
function signOut(){
  closeDrawer(); $('#modal').classList.remove('on');
  try{ ['d1d2:saved','d1d2:runs2'].forEach(k=>localStorage.removeItem(k)); }catch(e){}
  location.reload();
}
/* Redraw without losing what is typed in fields not held in state (e.g. the invitation emails) */
function redrawKeep(){
  const v={}, foc=document.activeElement&&document.activeElement.id;
  document.querySelectorAll('#app input[id]:not([type=file]):not([type=checkbox]):not([type=radio]),#app textarea[id]').forEach(e=>v[e.id]=e.value);
  draw(); Object.keys(v).forEach(k=>{ const e=document.getElementById(k); if(e) e.value=v[k]; }); if(foc&&v[foc]!=null){ const e=document.getElementById(foc); if(e) e.focus(); }
}
document.addEventListener('change',e=>{
  const t=e.target, a=t.dataset.act;
  if(t.id==='listed'){ S.listed=t.checked; if(S.listed&&S.add) S.add.err=''; }
  else if(t.id==='company'){ pickCompany(t.value,()=>draw()); }
  else if(a==='psel'){ const p=t.value, i=S.priorSel.indexOf(p); if(t.checked&&i<0&&S.priorSel.length<2) S.priorSel.push(p); else if(!t.checked&&i>=0) S.priorSel.splice(i,1); buildHistory(); draw(); }
  else if(a==='doc'){ const n=+t.dataset.n; S.docs[n].on=t.checked; updMeter(); }
  else if(a==='docfile'){ const d=S.docs[+t.dataset.n]; sizeOk(Array.from(t.files)).forEach(f=>d.files.push({name:f.name,file:f})); d.on=d.files.length>0; t.value=''; redrawKeep(); }
  else if(a==='sr'){ S.ratings[t.dataset.d]=+t.value; }
  else if(t.id==='oifiles'){ const A=S.add; sizeOk(Array.from(t.files)).forEach(f=>{ if(A.files.length>=10) return toast('At most 10 documents.'); if(!A.files.some(x=>x.name===f.name&&x.file.size===f.size)) A.files.push({name:f.name,file:f}); }); t.value=''; redrawKeep(); }
  else if(t.id==='otherfiles'){ sizeOk(Array.from(t.files)).forEach(f=>S.other.push({name:f.name,file:f})); t.value=''; redrawKeep(); }
  else if(t.id==='qfile'){ const fs=sizeOk(Array.from(t.files)); t.value=''; if(fs.length) loadQuestionnaires(fs); }
});
document.addEventListener('input',e=>{ const t=e.target; if(t.dataset.act==='qa') S.answers[+t.dataset.n]=t.value; else if(t.id==='srcq'){ S.srcq=t.value; $('#srclist').innerHTML=srcList(); } });
$('#modal').addEventListener('click',e=>{ if(e.target.id==='modal') $('#modal').classList.remove('on'); });
function docMeter(){ const n=Object.values(S.docs).filter(d=>d.on).length, of=D.docs.length||1;
  return '<div id="meter"><div class="meter"><i style="width:'+Math.min(100,n/of*100)+'%"></i></div><div class="muted">'+n+' of '+D.docs.length+' documents provided</div></div>'; }
function updMeter(){ const e=$('#meter'); if(e) e.outerHTML=docMeter(); }
try{ S.saved=localStorage.getItem('d1d2:saved')==='1'; }catch(e){}
if(TAKE) startRespond();
else { draw(true); apiInit().then(()=>{ if(S.page!=='landing') draw(); }); }
