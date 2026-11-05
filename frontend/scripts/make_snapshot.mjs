// Builds one self-contained, read-only HTML file of the app for a company already on file.
// Run from the frontend folder:  node scripts/make_snapshot.mjs <company-id>
// Needs the backend's Python environment (backend/.venv); reads the stored results and changes nothing.
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url)), web = resolve(here, '..'), root = resolve(web, '..')
const cid = process.argv[2]
if (!cid) { console.error('Usage: node scripts/make_snapshot.mjs <company-id>'); process.exit(2) }
const tmp = mkdtempSync(join(tmpdir(), 'am_snap_'))
const outFile = join(root, 'exports', 'AM_Board_Assessment_Snapshot.html')
try {
  const data = join(tmp, 'data.json')
  execFileSync(join(root, 'backend', '.venv', 'Scripts', 'python.exe'), ['scripts/export_snapshot.py', cid, data], { cwd: join(root, 'backend'), stdio: 'inherit', env: { ...process.env, PYTHONUTF8: '1' } })
  const dist = join(tmp, 'dist')
  execFileSync(process.execPath, [join(web, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '--outDir', dist, '--emptyOutDir', '--base', './'], { cwd: web, stdio: 'inherit', env: { ...process.env, VITE_SNAPSHOT: '1' } })

  let html = readFileSync(join(dist, 'index.html'), 'utf8')
  const asset = (p) => readFileSync(join(dist, p.replace(/^\.\//, '')), 'utf8')
  // inline the stylesheet and script (a closing tag inside them would end the block early)
  html = html.replace(/<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/, (_, p) => `<style>${asset(p).replace(/<\/style/gi, () => '<\\/style')}</style>`)
  let js = ''
  html = html.replace(/<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>/, (_, p) => { js = asset(p).replace(/<\/script/gi, () => '<\\/script'); return '' })
  const snap = readFileSync(data, 'utf8').replace(/<\//g, () => '<\\/')
  // function replacers: a string replacement would treat "$&" and "$'" inside the code or data as patterns and corrupt it
  html = html.replace('</head>', () => `<script>window.__SNAP__=${snap}</script></head>`).replace('</body>', () => `<script type="module">${js}</script></body>`)

  mkdirSync(dirname(outFile), { recursive: true })
  writeFileSync(outFile, html, 'utf8')
  console.log(`wrote ${outFile} (${(html.length / 1048576).toFixed(1)} MB)`)
} finally { rmSync(tmp, { recursive: true, force: true }) }
