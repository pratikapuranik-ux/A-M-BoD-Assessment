import { useEffect, useState, type DragEvent } from 'react'
import { api } from '../../api/client'
import { sizeOk } from '../../lib/actions'
import { FILE_ACCEPT } from '../../lib/constants'
import { listJoin } from '../../lib/journey'
import { useInsideOut, type Picked } from '../../store/insideOut'
import { AddFiles, Chip, toast } from '../../components/ui'

const OK = new Set(FILE_ACCEPT.split(','))
const JUNK = new Set(['.ds_store', 'thumbs.db', 'desktop.ini'])
const extOf = (n: string) => { const i = n.lastIndexOf('.'); return i < 0 ? '' : n.slice(i).toLowerCase() }
const isZip = (n: string) => n.toLowerCase().endsWith('.zip')
const baseOf = (p: string) => p.slice(p.lastIndexOf('/') + 1)
const pathOf = (f: Picked) => f.path || f.name
const folderOf = (f: Picked) => { const p = pathOf(f); const i = p.lastIndexOf('/'); return i < 0 ? '' : p.slice(0, i) }
const usable = (path: string) => { const b = baseOf(path); return OK.has(extOf(b)) && !JUNK.has(b.toLowerCase()) && !b.startsWith('~$') && !b.startsWith('._') }
const mb = (n: number) => (n >= 2 ** 20 ? (n / 2 ** 20).toFixed(n >= 10 * 2 ** 20 ? 0 : 1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB')

type Entry = { isFile: boolean; isDirectory: boolean; name: string; fullPath: string; file?: (ok: (f: File) => void, no: (e: unknown) => void) => void; createReader?: () => { readEntries: (ok: (e: Entry[]) => void, no: (e: unknown) => void) => void } }

/** Every file under what was dropped (a folder is walked, with its sub-folders), with its path. */
async function walk(items: DataTransferItemList): Promise<{ file: File; path: string }[]> {
  const out: { file: File; path: string }[] = []
  const visit = async (e: Entry) => {
    if (e.isFile && e.file) {
      const file = await new Promise<File>((ok, no) => e.file!(ok, no))
      out.push({ file, path: e.fullPath.replace(/^\/+/, '') })
    } else if (e.isDirectory && e.createReader) {
      const r = e.createReader()
      for (;;) {  // a directory is read in batches until it returns none
        const batch = await new Promise<Entry[]>((ok, no) => r.readEntries(ok, no))
        if (!batch.length) break
        for (const c of batch) await visit(c)
      }
    }
  }
  const entries = Array.from(items).filter((i) => i.kind === 'file').map((i) => (i as DataTransferItem & { webkitGetAsEntry?: () => Entry | null }).webkitGetAsEntry?.() ?? null)
  for (const e of entries) if (e) await visit(e)
  return out
}

/** The files the director supplies on the company and its peers: pick files, pick or drop a whole folder, or a zip. Each folder is
 *  matched to the company or a peer by its name (the server does the matching, so a zip is treated the same), and the match can be
 *  changed here before anything is sent. */
export default function OwnDocuments() {
  const A = useInsideOut((s) => s.add)
  const patch = useInsideOut((s) => s.patchAdd)
  const [over, setOver] = useState(false)
  const [reading, setReading] = useState(false)
  const subjects = [A.company.trim() || 'The company', ...A.peers.map((p, i) => p.name.trim() || `Peer ${i + 1}`)]

  const add = (picked: { file: File; path?: string }[]) => {
    const skipped = picked.filter((p) => !usable(p.path || p.file.name)).length
    const fit = sizeOk(picked.filter((p) => usable(p.path || p.file.name)).map((p) => p.file))
    const keep = picked.filter((p) => fit.includes(p.file))
    const files = [...useInsideOut.getState().add.files]
    for (const p of keep) {
      const path = p.path && p.path.includes('/') ? p.path : undefined
      if (!files.some((x) => pathOf(x) === (path || p.file.name) && x.file.size === p.file.size)) files.push({ name: p.file.name, file: p.file, path })
    }
    patch({ files })
    if (skipped) toast(`${skipped} file${skipped === 1 ? '' : 's'} skipped: not a supported type.`)
  }
  const onFiles = (fl: FileList | null) => add(Array.from(fl || []).map((f) => ({ file: f, path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || undefined })))
  const onDrop = async (e: DragEvent) => {
    e.preventDefault(); setOver(false)
    setReading(true)
    try {
      const found = await walk(e.dataTransfer.items)
      add(found.length ? found : Array.from(e.dataTransfer.files).map((f) => ({ file: f })))
    } catch (err) { toast('Could not read the dropped folder: ' + (err as Error).message) }
    finally { setReading(false) }
  }

  // ask the server which subject each folder belongs to; what the director chose by hand is left alone
  const names = A.files.filter((f) => !isZip(f.name)).map(pathOf).join('\n')
  const roster = JSON.stringify([A.company, A.ticker, A.peers])
  useEffect(() => {
    const todo = useInsideOut.getState().add.files.filter((f) => !f.manual && !isZip(f.name))
    if (!todo.length) return
    const t = setTimeout(async () => {
      try {
        const r = await api<{ subjects: number[] }>('/documents/assign', {
          method: 'POST',
          body: JSON.stringify({ company: { name: A.company, ticker: A.ticker }, peers: A.peers.filter((p) => p.name.trim()).map((p) => ({ name: p.name, ticker: p.ticker })), names: todo.map(pathOf) }),
        })
        const by = new Map(todo.map((f, i) => [f, r.subjects[i]]))
        const files = useInsideOut.getState().add.files.map((f) => (by.has(f) && !f.manual ? { ...f, subject: by.get(f) } : f))
        useInsideOut.getState().patchAdd({ files })
      } catch { /* the server matches by folder anyway when it reads the files */ }
    }, 350)
    return () => clearTimeout(t)
  }, [names, roster]) // eslint-disable-line react-hooks/exhaustive-deps

  const groups = new Map<string, Picked[]>()
  for (const f of A.files) {
    const k = isZip(f.name) ? '\u0000zip' : folderOf(f)
    groups.set(k, [...(groups.get(k) || []), f])
  }
  const setGroup = (fs: Picked[], subject: number) => patch({ files: A.files.map((f) => (fs.includes(f) ? { ...f, subject, manual: true } : f)) })
  const removeAll = (fs: Picked[]) => patch({ files: A.files.filter((f) => !fs.includes(f)) })
  const used = new Set(A.files.filter((f) => !isZip(f.name)).map((f) => f.subject ?? 0))
  const peerNamed = A.peers.filter((p) => p.name.trim()).length

  return (
    <>
      <div
        className={'dropzone' + (over ? ' over' : '')}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={(e) => void onDrop(e)}
        role="group" aria-label="Drop files or a folder here"
      >
        <p><b>Drag a folder or files here</b>, or choose them:</p>
        <div className="frow">
          <AddFiles label="Choose files" icon="doc" accept={FILE_ACCEPT} ariaLabel="Your own documents" onFiles={onFiles} />
          <AddFiles label="Choose a folder" icon="zip" folder ariaLabel="A folder of documents" onFiles={onFiles} />
        </div>
        {reading && <p className="muted">Reading the folder…</p>}
      </div>

      {A.files.length > 0 && (
        <div className="docgroups">
          <p className="muted">{A.files.length} file{A.files.length === 1 ? '' : 's'} ({mb(A.files.reduce((n, f) => n + f.file.size, 0))}). Each folder is matched to the company or a peer by its name; change it if it is wrong. Files outside any matching folder go to the company; a folder named after some other company is marked Not used and is not sent.</p>
          {[...groups.entries()].map(([k, fs]) => {
            const zip = k === '\u0000zip'
            const cur = fs[0].subject ?? 0
            return (
              <div className="docgroup" key={k}>
                <div className="docgroup-head">
                  <b>{zip ? 'Zip files' : k || 'Files not in a folder'}</b>
                  <span className="muted">{fs.length} file{fs.length === 1 ? '' : 's'}, {mb(fs.reduce((n, f) => n + f.file.size, 0))}</span>
                  {zip
                    ? <span className="muted">folders inside a zip are matched by name too</span>
                    : <select value={cur} aria-label={`Who ${k || 'these files'} are about`} onChange={(e) => setGroup(fs, Number(e.target.value))}>
                        {subjects.map((s, i) => <option key={i} value={i}>{i === 0 ? `${s} (the company)` : `Peer: ${s}`}</option>)}
                        <option value={-1}>Not used (not one of these companies)</option>
                      </select>}
                  <button type="button" className="linkbtn" onClick={() => removeAll(fs)} aria-label={`Remove ${zip ? 'the zip files' : k || 'these files'}`}>Remove</button>
                </div>
                <details><summary className="muted">Show files</summary>
                  <div className="chips">{fs.map((f) => <Chip key={pathOf(f) + f.file.size} onRemove={() => patch({ files: A.files.filter((x) => x !== f) })} label={`Remove ${f.name}`}>{f.name}</Chip>)}</div>
                </details>
              </div>
            )
          })}
          {peerNamed > 0 && used.size === 1 && used.has(0) && A.files.some((f) => !isZip(f.name)) && (
            <p className="muted">All of these are set to the company. To give a peer its own documents, put them in a folder named after the peer, or choose the peer above.</p>
          )}
          {A.files.some((f) => isZip(f.name)) && <p className="muted">{listJoin(A.files.filter((f) => isZip(f.name)).map((f) => f.name))}: read when the assessment starts.</p>}
        </div>
      )}
    </>
  )
}
