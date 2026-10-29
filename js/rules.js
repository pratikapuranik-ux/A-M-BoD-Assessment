/* Port of the skill's scripts/grade.py: builds a run object from the app state and validates the scoring rules
   (evidence classes, 1/5 evidence thresholds, silence caps, scoped pairs, Part D inside-out rules, coverage). */
function evidenceItems(){
  const ev={};
  Object.keys(D.ev).forEach(k=>{ const e=D.ev[k]; ev[k]={document:e.doc,evidence_class:e.cls,source_origin:e.origin,date:e.date,url:e.url||'',excerpt:e.excerpt,recent:!!e.recent,simulated:false}; if(e.search) ev[k].search_log=e.search; });
  const iev=D.io?D.io.ev:{};
  Object.keys(iev).forEach(k=>{ const e=iev[k]; ev[k]={document:e.doc,evidence_class:e.cls,source_origin:e.origin,date:e.date,url:'',excerpt:e.excerpt,recent:true,simulated:false}; });
  return ev;
}
function buildRun(stage){
  const io=stage==='io';
  const mk=(name,tk,role,get)=>({name:name,ticker:tk,role:role,indicators:IDS.reduce((o,i)=>{ o[i]=get(i); return o; },{})});
  const comp=mk(COFULL,TK,'company',i=>{ const c=D.ind[i]; const cell={board:{score:c.score,confidence:c.conf,evidence:c.ev,rationale:c.rationale}}; if(io){ const x=ioCell(i); cell.board_io={score:x.score,confidence:x.conf,evidence:x.ev,rationale:x.rat}; if(x.carried) cell.board_io.carried_forward=true; } return cell; });
  const peers=PEERFULL.map((n,p)=>mk(n,'','peer',i=>({board:{score:D.peers[p].ind[i].score,confidence:i==='4.3'?'Low':'Medium',evidence:D.peers[p].ind[i].ev,rationale:D.peers[p].ind[i].rationale}})));
  return {run:{stage:io?'inside_out':'outside_in',mode:S.mode,rule_version:FW.rule_version,period:S.period},subjects:[comp].concat(peers),evidence:evidenceItems(),
    actions:(io?D.io.actions:D.actions).map(a=>({heading:a.heading,description:a.description,target_by:a.target})),
    prior_actions_status:io?priorActionsList().map(a=>({status:a.status})):[],history:S.history.map(h=>({period:h.period}))};
}
const IND_SCOPED=()=>FW.scoped_pairs;
function validateCell(name,iid,lens,cell,evidence,problems,warnings){
  const where=iid+'/'+lens, STRONG=FW.strong_classes, WEAK=['searched_record','silence'], CAPPED=Object.assign({},FW.silence_capped,FW.searched_record_capped);
  if(!cell||cell.score==null){ if(FW.na_causes.indexOf((cell||{}).na_cause)<0) problems.push([name,where,'not assessable: na_cause must be one of '+FW.na_causes.join(', ')]); return; }
  const s=cell.score; if([1,2,3,4,5].indexOf(s)<0){ problems.push([name,where,'score is not an integer 1-5']); return; }
  const ev=cell.evidence||[], missing=ev.filter(e=>!evidence[e]);
  if(missing.length){ problems.push([name,where,'evidence ids not in evidence list: '+missing.join(', ')]); return; }
  const items=ev.map(e=>evidence[e]), classes=items.map(it=>it.evidence_class||'direct');
  if(classes.some(c=>FW.evidence_classes.indexOf(c)<0)) problems.push([name,where,'unknown evidence_class']);
  if(lens==='board_io'){
    const iocl=classes.filter(c=>c==='inside_out'||c==='self_assessment');
    if(!iocl.length&&!cell.carried_forward) problems.push([name,where,'post inside-out score must cite at least one inside_out or self_assessment item, or set carried_forward with the outside-in score unchanged']);
    if(classes.length&&classes.every(c=>c==='self_assessment')&&cell.confidence==='High') problems.push([name,where,'self-assessment-only cell cannot be High confidence (Part D)']);
  } else if(classes.some(c=>c==='inside_out'||c==='self_assessment')) problems.push([name,where,'outside-in cell may not cite inside_out or self_assessment evidence']);
  const docs=new Set(items.map((it,k)=>it.document||ev[k])), strong=classes.some(c=>STRONG.indexOf(c)>=0||c==='inside_out');
  if((s===1||s===5)&&!strong&&(ev.length<2||docs.size<2)) problems.push([name,where,'score '+s+' needs >=2 items from >=2 documents or one strong item']);
  if([2,3,4].indexOf(s)>=0&&ev.length<1) problems.push([name,where,'score '+s+' needs >=1 evidence item']);
  if((s===2||s===4)&&!(cell.rationale||'').trim()) problems.push([name,where,'score '+s+' requires a rationale naming the parts of both anchors met']);
  if(!(cell.rationale||'').trim()) warnings.push([name,where,'rationale is empty']);
  const onlyWeak=classes.length&&classes.every(c=>WEAK.indexOf(c)>=0);
  if(onlyWeak){ if(CAPPED[iid]!==undefined&&s>CAPPED[iid]) problems.push([name,where,'only silence/searched-record evidence: score capped at '+CAPPED[iid]]); else if(CAPPED[iid]===undefined&&FW.silence_full.indexOf(iid)<0) problems.push([name,where,'silence/searched-record evidence is not scorable for this indicator']); if(cell.confidence!=='Low') problems.push([name,where,'silence/searched-record-only cell must be Low confidence']); }
  items.forEach(it=>{ if(it.evidence_class==='searched_record'&&!it.search_log) problems.push([name,where,'searched_record item needs search_log']); });
  const conf=cell.confidence;
  if(['High','Medium','Low'].indexOf(conf)<0) problems.push([name,where,'confidence must be High, Medium or Low']);
  else if(conf==='High'){ const direct=classes.filter(c=>['direct','strong_direct','board_act','inside_out'].indexOf(c)>=0).length; if(!(direct>=2||strong)) warnings.push([name,where,'High confidence needs >=2 direct items or one strong item']); }
}
function validateRun(run){
  const problems=[],warnings=[],ev=run.evidence,meta=run.run;
  if(FW.stages&&Object.keys(FW.stages).indexOf(meta.stage)<0) problems.push(['run','run.stage','must be one of '+Object.keys(FW.stages).join(', ')]);
  if(!FW.run_modes[meta.mode]) problems.push(['run','run.mode','unknown run mode']);
  if(String(meta.rule_version)!==String(FW.rule_version)) problems.push(['run','run.rule_version','must be '+FW.rule_version]);
  if(!meta.period||String(meta.period).indexOf('-Q')<0) problems.push(['run','run.period','must be YYYY-Qn']);
  const peers=run.subjects.filter(s=>s.role==='peer'); if(peers.length<2||peers.length>FW.max_peers) problems.push(['run','peers','peer set should be 2-'+FW.max_peers]);
  run.actions.forEach(a=>{ if(!a.heading||!a.description) problems.push(['run','actions','each action needs heading and description']); if(!a.target_by) warnings.push(['run','action','no target_by']); });
  if(run.actions.length>5) problems.push(['run','actions','maximum five actions']);
  run.actions.forEach(a=>{ if(/\b(A&M|Alvarez|Marsal)\b/i.test((a.heading||'')+' '+(a.description||''))) problems.push(['run','actions','actions must not reference A&M services']); });
  run.prior_actions_status.forEach(p=>{ if(FW.action_statuses.indexOf(p.status)<0) problems.push(['run','prior_actions_status','invalid status']); });
  run.subjects.forEach(s=>{ if(s.role==='peer'&&Object.keys(s.indicators).some(i=>s.indicators[i].board_io)) problems.push([s.name,'peer','peers are never assessed with inside-out information']); });
  run.subjects.forEach(s=>{ const lenses=s.role==='company'&&meta.stage==='inside_out'?['board','board_io']:['board'];
    IDS.forEach(i=>lenses.forEach(l=>validateCell(s.name,i,l,(s.indicators[i]||{})[l],ev,problems,warnings)));
    FW.scoped_pairs.forEach(pr=>lenses.forEach(l=>{ const ea=new Set((((s.indicators[pr[0]]||{})[l])||{}).evidence||[]), eb=(((s.indicators[pr[1]]||{})[l])||{}).evidence||[]; const both=eb.filter(x=>ea.has(x)); if(both.length) problems.push([s.name,pr[0]+'/'+pr[1]+' ('+l+')','evidence '+both.join(', ')+' primary in both indicators of a scoped pair']); })); });
  run.history.forEach(h=>{ if(h.period===meta.period) problems.push(['run','history','history contains the current period']); });
  return {problems:problems,warnings:warnings};
}
/* Internal quality check (run by the tests); not shown to directors */
function ruleCheck(stage){ const r=validateRun(buildRun(stage)); languageWarnings().forEach(w=>r.warnings.push(['self-assessment','Q'+w.q,w.msg])); return r; }
