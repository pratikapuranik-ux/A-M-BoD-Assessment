/* Run with: node tests/engine.test.js   (Node 18+). Loads the browser scripts into a sandbox and checks the grading
   engine, rule checks and guardrails. The Chevron view in tests/fixtures is test data only; the app ships without it. */
const test = require('node:test'), assert = require('node:assert'), fs = require('fs'), path = require('path'), vm = require('vm');
const root = path.join(__dirname, '..');
const ctx = vm.createContext({ console, TextDecoder, DOMParser: class {}, document: { querySelector: () => null } });
['tests/fixtures/example_view.js', 'js/data/framework.js', 'js/state.js', 'js/engine.js', 'js/rules.js'].forEach(f => vm.runInContext(fs.readFileSync(path.join(root, f), 'utf8'), ctx, { filename: f }));
const run = code => { const v = vm.runInContext(code, ctx); return v && typeof v === 'object' ? JSON.parse(JSON.stringify(v)) : v; };
const grades = lens => run(`(()=>{const m=M(); const L=m.${lens}; return {dims:DIMS.map(d=>L.dims[d].grade).join(''),overall:L.overall.grade}})()`);

test('outside-in grades match the fixture report', () => {
  assert.deepStrictEqual(grades('oi'), { dims: 'DBBCCB', overall: 'C' });
  assert.deepStrictEqual(run('M().peers.map(p=>p.c.overall.grade).join("")'), 'CD'); // ExxonMobil C, BP D (2.5 rounds down)
  assert.strictEqual(run('M().oi.assessed'), 22);
});
test('midpoints round down: average 2.5 is a D, 3.5 is a C', () => {
  assert.strictEqual(run('(()=>{const sc={}; IDS.forEach(i=>sc[i]=DIM_OF[i]<="3"?3:2); sc["1.1"]=3; const c=compute(sc,0.5); return c.overall.grade})()'), 'D');
});
test('inside-out result: both grades kept, company moves to B', () => {
  assert.deepStrictEqual(grades('io'), { dims: 'BCBBDA', overall: 'B' });
  assert.strictEqual(grades('oi').overall, 'C');
  assert.strictEqual(run('M().io.assessed'), 22);
});
test('coverage thresholds: half outside-in, two-thirds inside-out', () => {
  assert.strictEqual(run('(()=>{const sc={}; ["1.1","1.2"].forEach(i=>sc[i]=3); return compute(sc,0.5).dims["1"].reported})()'), true);
  assert.strictEqual(run('(()=>{const sc={"1.1":3}; return compute(sc,0.5).dims["1"].reported})()'), false);
});
test('two-thirds inside-out: 2 of 3 is reported, 1 of 3 and 2 of 4 are not', () => {
  const rep = (ids, d, thr) => run(`(()=>{const sc={}; ${JSON.stringify(ids)}.forEach(i=>sc[i]=3); return compute(sc,${thr}).dims["${d}"].reported})()`);
  assert.strictEqual(rep(['4.1', '4.2'], '4', 'THR.io'), true);
  assert.strictEqual(rep(['4.1', '4.2'], '4', '0.67'), true);   // the framework's rounded 0.67 means two-thirds
  assert.strictEqual(rep(['4.1'], '4', 'THR.io'), false);
  assert.strictEqual(rep(['1.1', '1.2'], '1', 'THR.io'), false);
  assert.strictEqual(rep(['1.1', '1.2', '1.3'], '1', 'THR.io'), true);
  assert.strictEqual(run('(()=>{const v=JSON.parse(JSON.stringify(D)); v.io.cells={}; ["4.3"].forEach(i=>v.ind[i].score=null); const keep=D; setData(v); const r=M().io.dims["4"].reported; setData(keep); return r})()'), true);
});
test('missing inside-out cells or evidence do not throw', () => {
  assert.strictEqual(run('(()=>{const keep=D, v=JSON.parse(JSON.stringify(D)); delete v.io.cells; delete v.io.ev; setData(v); const r=[ioCell("1.1").carried, evOf("IO01")]; setData(keep); return JSON.stringify(r)})()'), '[true,null]');
});
test('rule check passes for both stages', () => {
  ['oi', 'io'].forEach(s => { const r = run(`(()=>{const r=ruleCheck("${s}"); return [r.problems.length,r.warnings.length]})()`); assert.deepStrictEqual(r, [0, 0], s); });
});
test('rule check catches violations (grade.py port)', () => {
  const n = code => run(`(()=>{const r=buildRun("oi"); ${code}; return validateRun(r).problems.map(p=>p[2]).join("|")})()`);
  assert.match(n('r.subjects[0].indicators["1.1"].board.score=5;r.subjects[0].indicators["1.1"].board.evidence=["E01"]'), /score 5 needs/);
  assert.match(n('r.actions[0].description+=" Alvarez & Marsal can help"'), /must not reference A&M/);
  assert.match(n('r.subjects[1].indicators["1.1"].board_io={score:3,evidence:["E01"],confidence:"Low",rationale:"x"}'), /never assessed with inside-out/);
  assert.match(n('r.subjects[0].indicators["2.3"].board={score:null}'), /na_cause/);
  assert.match(n('r.subjects[0].indicators["3.4"].board.evidence=r.subjects[0].indicators["5.1"].board.evidence.slice()'), /scoped pair/);
});
test('prior run files become trend history; wrong rule version is rejected', () => {
  const prior = JSON.parse(fs.readFileSync(path.join(root, 'skill/example_runs/prior_2026-Q3_simulated_run.json'), 'utf8'));
  delete prior.run.simulated; ctx.__p = prior; const e = run('historyFromRun(__p)');
  assert.strictEqual(e.period, '2026-Q3'); assert.strictEqual(e.overall.grade, 'C');
  prior.run.rule_version = '1.1'; ctx.__p = prior; assert.throws(() => run('historyFromRun(__p)'), /rule version/);
  prior.run.rule_version = '1.2'; prior.run.simulated = true; ctx.__p = prior; assert.throws(() => run('historyFromRun(__p)'), /simulated/);
});
test('guardrails: individuals, legal conclusions, investment advice', () => {
  assert.ok(run('guardrailScan("Mr Smith was incompetent").length')>=2);
  assert.ok(run('guardrailScan("The board breached its fiduciary duty").length')>=1);
  assert.ok(run('guardrailScan("Analysts see the shares as undervalued").length')>=1);
  assert.strictEqual(run('guardrailScan("The board asked for unfiltered customer evidence").length'), 0);
});
