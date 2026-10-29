/* Anonymous board self-assessment: the invitations card on the inside-out page, and the page an invited director
   opens from a personal link (?take=<token>), which shows only the questions, never the assessment itself. */
const TAKE=new URLSearchParams(location.search).get('take');

/* ---------- invitations (inside-out page) ---------- */
/* the server's count (responses received) plus returned questionnaires not yet uploaded */
function surveyNow(){ const v=Object.assign({invites:[],responses:0,min:3},S.survey||{}); return {v:v,n:(v.count!=null?v.count:v.responses)+S.qFiles.length}; }
const NUMW=['no','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty'];
const numWord=n=>NUMW[n]||String(n);
function mailtoFor(x){
  const body='You are invited to take part in an anonymous board self-assessment for '+COFULL+' ('+S.period+').\n\n'+
   'There are '+numWord(D.q.length)+' short questions about how the board works; it takes about 15 minutes. Your answers are pooled with those of other directors and are never attributed to you.\n\n'+
   'Open your personal link to begin:\n'+x.link+'\n\nThe link is personal to you; please do not forward it.';
  return 'mailto:'+encodeURIComponent(x.email)+'?subject='+encodeURIComponent('Board self-assessment: '+COFULL)+'&body='+encodeURIComponent(body);
}
function surveyCard(){
  const sv=surveyNow(), v=sv.v, n=sv.n, need=Math.max(0,v.min-n);
  return '<div class="card acc" id="survey"><h3>3. Board self-assessment</h3>'+
   '<p class="muted">Invite directors to answer '+numWord(D.q.length)+' short questions about how the board works. Each person receives a personal link. Answers are pooled and never attributed to anyone.</p>'+
   (v.local?'<p class="muted">These links open only on this computer. To invite directors on other devices, host the app and set BOARD_PUBLIC_URL.</p>':'')+
   '<div class="svmeter"><div class="meter"><i style="width:'+Math.min(100,n/(v.min||1)*100)+'%"></i></div><span><b>'+n+' of '+esc(v.min)+'</b> responses'+(need?' · '+need+' more needed before the inside-out view can be prepared':' · enough to prepare the inside-out view')+'</span></div>'+
   '<label for="svemails">Invite by email</label><div class="svadd"><input type="text" id="svemails" placeholder="name@company.com, another@company.com" aria-label="Email addresses"><button class="btn" data-act="svinvite"'+(API.on?'':' disabled')+'>'+ico('plus',16)+'Add invitations</button></div><div class="muted err" id="svmsg"></div>'+
   (v.invites.length?'<div class="scroll"><table class="tbl svt"><tr><th>Invited</th><th>Status</th><th>Personal link</th><th></th></tr>'+v.invites.map(x=>'<tr><td>'+esc(x.email)+'</td><td>'+(x.responded?'<span class="st-on_track">Responded</span>':'<span class="muted">Invited '+esc(x.created)+'</span>')+'</td>'+
     '<td><code class="svlink">'+esc(x.link)+'</code></td><td class="ra"><div class="row nowrap"><button class="btn sec sm" data-act="svcopy" data-l="'+esc(x.link)+'">Copy link</button><a class="btn sec sm" href="'+esc(mailtoFor(x))+'">'+ico('mail',15)+'Email</a>'+
     (x.responded?'':'<button class="btn sec sm" data-act="svrm" data-t="'+esc(x.token)+'" aria-label="Withdraw the invitation to '+esc(x.email)+'">×</button>')+'</div></td></tr>').join('')+'</table></div>'+
     '<p class="ks">“Responded” shows only that someone has answered, never what they said: answers are stored separately, in random order, with no link to the invitation.</p>':'')+
   '<h4 class="svh">Paper returns</h4><p class="muted">Directors can also complete the Word questionnaire. Each returned file counts as one anonymous response.</p><div class="row">'+dlBtn('quest','Questionnaire (Word)','doc')+'</div>'+
   '<div class="frow"><input type="file" id="qfile" accept=".docx" multiple aria-label="Returned questionnaires"></div>'+(S.qFiles.length?'<div class="chips">'+S.qFiles.map((f,k)=>'<div class="chip">'+esc(f.name)+' <span class="muted">'+f.n+' answers</span><button data-act="rmq" data-i="'+k+'" aria-label="Remove '+esc(f.name)+'">×</button></div>').join('')+'</div>':'')+'</div>';
}
/* The server says whether the inside-out view can be prepared (can_generate, with its reason). Returned questionnaires
   are uploaded when the run starts, so a shortfall in the count alone is made up by those waiting here. */
function canGenerateIO(){
  if(ioBusy()) return false;
  const sv=surveyNow(), v=sv.v, base=API.on&&API.research.enabled&&sv.n>=v.min;
  if(typeof v.can_generate!=='boolean') return base;
  return v.can_generate||(S.qFiles.length>0&&(v.count!=null?v.count:v.responses)<v.min&&base);
}
function ioWhy(){ const v=S.survey||{}; return canGenerateIO()||ioBusy()?'':(v.reason||''); }
function updSurvey(){
  const c=$('#survey'); if(!c) return; const inp=$('#svemails'), val=inp?inp.value:'', foc=document.activeElement===inp;
  c.outerHTML=surveyCard(); const i2=$('#svemails'); if(i2){ i2.value=val; if(foc) i2.focus(); }
  const b=$('#start2btn'); if(b) b.disabled=!canGenerateIO();
  const w=$('#iowhy'); if(w) w.textContent=ioWhy();
}
async function loadSurvey(){
  if(!API.on||!S.company) return; const id=S.company;
  try{ const v=await api('/companies/'+encodeURIComponent(id)+'/survey'); if(id===S.company){ S.survey=v; updSurvey(); } }catch(e){}
}
/* responses arrive while the page is open (useful in a demo): refresh the count every few seconds */
setInterval(()=>{ if(!TAKE&&S.page==='journey'&&S.stage===2&&S.sub==='input'&&!document.hidden) loadSurvey(); },6000);
async function inviteEmails(){
  const raw=($('#svemails')||{}).value||'', emails=raw.split(/[\s,;]+/).map(x=>x.trim()).filter(Boolean), m=$('#svmsg');
  if(!emails.length){ if(m) m.textContent='Enter at least one email address.'; return; }
  const bad=emails.filter(e=>!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)); if(bad.length){ if(m) m.textContent='Not an email address: '+bad.join(', '); return; }
  try{ S.survey=await post('/companies/'+encodeURIComponent(S.company)+'/survey/invite',{emails:emails}); const i=$('#svemails'); if(i) i.value=''; updSurvey(); toast(emails.length+(emails.length===1?' invitation':' invitations')+' ready. Send each one with Email, or copy its link.'); }
  catch(e){ if(m) m.textContent=e.message; }
}
async function uninvite(token){
  try{ S.survey=await api('/companies/'+encodeURIComponent(S.company)+'/survey/invite/'+encodeURIComponent(token),{method:'DELETE'}); updSurvey(); }catch(e){ toast(e.message); }
}
/* returned Word questionnaires become anonymous responses when the inside-out run starts */
/* each file leaves the list as soon as it is stored, so a retry never posts it twice; a duplicate or empty return is dropped */
async function sendPaperReturns(cid){
  const drop=f=>{ const k=S.qFiles.indexOf(f); if(k>=0) S.qFiles.splice(k,1); };
  for(const f of S.qFiles.slice()){
    const answers={}; f.answers.forEach((x,i)=>answers[i+1]=x||'');
    try{ const v=await post('/companies/'+encodeURIComponent(cid)+'/survey/responses',{answers:answers,ratings:f.ratings}); drop(f); if(v&&S.company===cid) S.survey=v; }
    catch(e){
      if(e.status===409&&/already/i.test(e.message)){ drop(f); toast(f.name+' has already been added, so it was not counted again.'); }
      else if(e.status===400&&/empty|at least one/i.test(e.message)){ drop(f); toast(f.name+' has no answers, so it was not added.'); }
      else throw e;
    }
  }
}
document.addEventListener('click',e=>{
  const t=e.target.closest('[data-act]'); if(!t||t.disabled) return; const a=t.dataset.act;
  if(a==='svinvite') inviteEmails();
  else if(a==='svrm') uninvite(t.dataset.t);
  else if(a==='svcopy'){ const l=t.dataset.l; (navigator.clipboard?navigator.clipboard.writeText(l):Promise.reject()).then(()=>toast('Link copied. Paste it into a browser to open the assessment.'),()=>window.prompt('Copy this link:',l)); }
});
document.addEventListener('keydown',e=>{ if(e.key==='Enter'&&e.target&&e.target.id==='svemails'){ e.preventDefault(); inviteEmails(); } });

/* ---------- the respondent's page ---------- */
const R={form:null,step:'intro',answers:{},ratings:{},err:'',warned:false,busy:false};
async function startRespond(){
  document.title='Board self-assessment';
  try{ R.form=await api('/survey/'+encodeURIComponent(TAKE)); if(R.form.responded) R.step='done'; }
  catch(e){ R.step='error'; R.err=e.message; }
  drawRespond();
}
const ANON=()=>'<div class="anon"><div class="anonh">'+'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>'+'<b>Your response is anonymous</b></div><ul>'+
 '<li>'+((R.form&&R.form.min||3)>=3?'Your answers are pooled with those of at least two other directors before anyone reads them. ':'Your answers are pooled with other directors’ responses. ')+'They are never attributed to you, and nothing in the results can be traced back to you or to this invitation.</li>'+
 '<li>The questions are about how the board works as a body, not about any individual. Please describe practices and examples rather than naming colleagues.</li></ul></div>';
function drawRespond(){
  const f=R.form, top='<header class="tb"><div class="wrap tbi"><div class="brandrow">'+LOGO_W+'<span class="bdiv"></span><span class="bname">Board Assessment</span></div></div></header>';
  let b='';
  if(R.step==='error') b='<div class="card rcard"><h2>This link cannot be used</h2><p class="muted">'+esc(R.err)+'</p><p class="muted m0">If you think this is a mistake, ask the person who invited you for a new link.</p></div>';
  else if(R.step==='done') b='<div class="card rcard"><div class="peb">Board self-assessment</div><h2>Thank you</h2><p>Your response has been received. It will be pooled with other directors’ responses and is not attributed to you.</p><p class="muted m0">You can close this page.</p></div>';
  else if(R.step==='intro') b='<div class="card rcard"><div class="peb">Board self-assessment</div><h1>Take the assessment</h1><p class="sub2">'+esc(f.company)+(f.period?' · '+esc(f.period):'')+'</p>'+ANON()+
    '<p class="muted">'+(s=>s[0].toUpperCase()+s.slice(1))(numWord(f.questions.length))+' questions across six themes · about 15 minutes</p><button class="btn lg" data-act="rstart">Take the assessment'+ico('arrow',16)+'</button></div>';
  else {
    const dims=[]; f.questions.forEach(q=>{ if(dims.indexOf(q.dimension)<0) dims.push(q.dimension); });
    b='<div class="rhead"><div class="peb">Board self-assessment · '+esc(f.company)+'</div><h1>How the board works</h1><p class="muted m0">Anonymous. Answer as many questions as you can; you can leave a question blank.</p></div>'+
     dims.map(d=>{ const qs=f.questions.filter(q=>q.dimension===d);
       return '<div class="card"><h3>'+esc(d)+'. '+esc(qs[0].dimension_name)+'</h3>'+qs.map(q=>'<div class="q"><label for="ra'+esc(q.n)+'" class="ql">'+esc(q.n)+'. '+esc(q.text)+'</label><textarea id="ra'+esc(q.n)+'" data-ra="'+esc(q.n)+'">'+esc(R.answers[q.n]||'')+'</textarea></div>').join('')+
        '<div class="ql">Overall, how would you describe the board on this theme?</div><div class="radios">'+[[1,'Mostly Day 2'],[3,'Mixed'],[5,'Mostly Day 1']].map(o=>'<label class="pl"><input type="radio" name="rr'+esc(d)+'" data-rr="'+esc(d)+'" value="'+o[0]+'"'+(R.ratings[d]==o[0]?' checked':'')+'> '+o[1]+'</label>').join('')+'</div></div>'; }).join('')+
     '<div id="rwarn"></div><div class="muted err" id="rmsg">'+esc(R.err)+'</div><div class="row sb"><span class="muted">Your response is anonymous.</span><button class="btn lg" data-act="rsubmit"'+(R.busy?' disabled':'')+'>Submit my response'+ico('arrow',16)+'</button></div>';
  }
  $('#app').innerHTML=top+'<main class="mainc"><div class="wrap rsp">'+b+'</div></main><footer class="afoot2"><div class="wrap">'+DRAFT+'</div></footer>';
}
async function submitRespond(){
  const filled=Object.keys(R.answers).filter(k=>(R.answers[k]||'').trim());
  if(!filled.length){ R.err='Please answer at least one question.'; drawRespond(); return; }
  const warn=[]; filled.forEach(k=>guardrailScan(R.answers[k]).forEach(m=>warn.push('Question '+k+': '+m)));
  if(warn.length&&!R.warned){ R.warned=true; R.err=''; drawRespond(); $('#rwarn').innerHTML='<div class="notice"><b>Before you submit.</b> To keep the assessment about the board as a body:<ul>'+warn.map(w=>'<li>'+esc(w)+'</li>').join('')+'</ul>You can edit your answers, or submit them as they are.</div>'; $('#rwarn').scrollIntoView({behavior:'smooth',block:'center'}); return; }
  R.busy=true; R.err=''; drawRespond();
  try{ await post('/survey/'+encodeURIComponent(TAKE),{answers:R.answers,ratings:R.ratings}); R.step='done'; }
  catch(e){ R.err=e.message; if(/already been received/.test(e.message)) R.step='done'; }
  R.busy=false; drawRespond(); window.scrollTo(0,0);
}
document.addEventListener('click',e=>{ if(!TAKE) return; const t=e.target.closest('[data-act]'); if(!t||t.disabled) return;
  if(t.dataset.act==='rstart'){ R.step='form'; drawRespond(); window.scrollTo(0,0); } else if(t.dataset.act==='rsubmit') submitRespond(); });
document.addEventListener('input',e=>{ if(TAKE&&e.target.dataset.ra){ R.answers[e.target.dataset.ra]=e.target.value; R.warned=false; } });
document.addEventListener('change',e=>{ if(TAKE&&e.target.dataset.rr) R.ratings[e.target.dataset.rr]=+e.target.value; });
