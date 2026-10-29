// Helper for test_dashboard.py: executes the generated dashboard page in jsdom and prints a JSON report.
// usage: node dashboard_dom_check.js <jsdom-module-dir> <html-file>
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require(path.join(process.argv[2], "node_modules", "jsdom"));
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push(String(e && e.stack || e)));
vc.on("error", (e) => errors.push(String(e)));
const dom = new JSDOM(fs.readFileSync(process.argv[3], "utf8"), { runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc });
const w = dom.window, d = w.document;
w.addEventListener("error", (e) => errors.push(String(e.message)));
const out = { errors };
out.kickers = [...d.querySelectorAll(".kicker")].map((k) => k.textContent.trim());
out.h1 = d.getElementById("title").textContent;
out.execOpen = d.getElementById("exec").open;
out.dimRows = d.querySelectorAll("#scorecard tr.row").length;
out.peerRows = d.querySelectorAll("#peers tr.row").length;
out.peerTable = !!d.querySelector("#peers table");
out.peerHeader = [...d.querySelectorAll("#peers thead th")].map((t) => t.textContent.trim());
out.reconRows = d.querySelectorAll("#recon tbody tr").length;
out.reconText = d.getElementById("recon").textContent;
out.execText = d.getElementById("exec").textContent;
out.actionsText = d.getElementById("actions").textContent;
out.coverageLine = d.getElementById("sccov").textContent;
// every evidence code in visible text should be a button
const bare = [];
for (const id of ["summary", "scorecard", "peers", "recon", "actions"]) {
  const clone = d.getElementById(id).cloneNode(true);
  clone.querySelectorAll("button.ec").forEach((b) => b.remove());
  const m = clone.textContent.match(/\[(?:[EXBKLN]|SA|IO)\d{2,3}\]/g);
  if (m) bare.push(...m);
}
out.bareCodes = bare;
out.chips = d.querySelectorAll("button.ec").length;
// dimension toggle
const btn = d.querySelector('#scorecard tr.row button.tg');
btn.click();
const open = d.querySelector("#scorecard .detail.open");
out.panelOpen = !!open;
out.panelText = open ? open.textContent : "";
out.panelRows = open ? open.querySelector("table").tBodies[0].rows.length : 0;
// evidence chip opens modal
const chip = d.querySelector("button.ec");
if (chip) { chip.click(); out.modalOpen = d.getElementById("modal").classList.contains("open"); out.modalText = d.getElementById("modalBox").textContent.slice(0, 80); }
// definition modal
const q = d.querySelector("button.info.ind");
q.click(); out.defModal = d.getElementById("modalBox").textContent.includes("Day 2");
// peer detail row
const prow = d.querySelector("#peers tr.row");
prow.click(); out.peerDetailOpen = !!d.querySelector("#peers .detail.open");
// visible text (scripts excluded) and the self-assessment evidence modal, for the anonymity / heading checks
const clone2 = d.body.cloneNode(true); clone2.querySelectorAll("script").forEach((s) => s.remove());
out.pageText = clone2.textContent;
const saId = w.eval("Object.keys(RUN.evidence)").find((k) => /^SA\d+$/.test(k));
if (saId) { w.showEv([saId], "t"); out.saModal = d.getElementById("modalBox").textContent; }
out.sectionTitles = [...d.querySelectorAll("details > summary")].map((s) => s.textContent.trim());
out.coverageText = d.getElementById("coverage").textContent;
out.appendixText = d.getElementById("appx").textContent;
out.guardText = d.getElementById("guard").textContent;
out.scorecardText = d.getElementById("scorecard").textContent;
console.log(JSON.stringify(out));
process.exit(0);
