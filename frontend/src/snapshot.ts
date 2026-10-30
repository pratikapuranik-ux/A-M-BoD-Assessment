/** Read-only snapshot mode (built with VITE_SNAPSHOT=1): every /api call is answered from data baked into the page, so the app opens from a file with no server. */
interface F { type: string; name: string; b64: string }
interface Snap { routes: Record<string, unknown>; files: Record<string, F>; taken: string }
declare global { interface Window { __SNAP__?: Snap } }

const snap = () => window.__SNAP__
const fileKey = (p: string) => /^\/api\/companies\/[^/]+\/files\/(\w+)/.exec(p.split('?')[0])?.[1]
const bytesOf = (f: F) => Uint8Array.from(atob(f.b64), (c) => c.charCodeAt(0))
const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'Content-Type': 'application/json' } })

/** The dashboard page behind an /api file URL, for the dialog's iframe (a page opened from a file cannot load /api/... itself). */
export function snapshotHtml(url: string): string | null {
  const k = fileKey(url), f = k ? snap()?.files[k] : undefined
  return f && f.type.startsWith('text/html') ? new TextDecoder().decode(bytesOf(f)) : null
}

// Open signed in on the company in the snapshot. This runs when the module loads: the app's session store reads
// storage the moment it is imported, so main.tsx imports this file before App.
try {
  const cid = (window.__SNAP__?.routes['/companies'] as { id: string }[] | undefined)?.[0]?.id
  if (cid && !sessionStorage.getItem('am-board-session'))
    sessionStorage.setItem('am-board-session', JSON.stringify({ state: { email: 'guest@anm.com', name: 'Guest', companyId: cid, mode: 'director_request', oiDone: true, seen3: false, priorSel: [] }, version: 0 }))
} catch { /* storage blocked: the app falls back to its sign-in page */ }

export function installSnapshot() {
  const s = snap()
  if (!s) return
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname + input.search : input.url
    if (!url.startsWith('/api')) return new Response(null, { status: 404 })
    const m = (init?.method || 'GET').toUpperCase(), path = url.split('?')[0].slice(4)
    if (m !== 'GET' && m !== 'HEAD') return json({ error: 'This is a read-only snapshot: nothing can be changed here.' }, 405)
    const k = fileKey(url)
    if (k) return s.files[k] ? new Response(m === 'HEAD' ? null : bytesOf(s.files[k]), { status: 200, headers: { 'Content-Type': s.files[k].type } }) : json({ error: 'Not in this snapshot' }, 404)
    return path in s.routes ? json(s.routes[path]) : json({ error: 'Not part of this snapshot' }, 404)
  }

  // downloads and "open in a new tab" point at /api files; serve them from the baked-in copies
  document.addEventListener('click', (e) => {
    const a = (e.target as Element | null)?.closest?.('a[href^="/api/"]') as HTMLAnchorElement | null
    const k = a ? fileKey(a.getAttribute('href') || '') : undefined, f = k ? s.files[k] : undefined
    if (!a || !f) return
    e.preventDefault()
    const u = URL.createObjectURL(new Blob([bytesOf(f)], { type: f.type }))
    if (a.hasAttribute('download') || !f.type.startsWith('text/html')) { const d = document.createElement('a'); d.href = u; d.download = f.name; d.click() }
    else window.open(u, '_blank')
  }, true)

  const bar = document.createElement('div')
  bar.textContent = `Read-only snapshot taken ${s.taken}. Nothing here can be changed or saved.`
  bar.setAttribute('style', 'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#002B49;color:#fff;font:600 13px system-ui,sans-serif;text-align:center;padding:6px 10px;pointer-events:none')
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(bar))
}
