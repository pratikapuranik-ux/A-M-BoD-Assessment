/** Reads a returned Word questionnaire (.docx) in the browser: a port of parse_questionnaire.py / engine.js. */

async function readZipEntry(buf: ArrayBuffer, name: string): Promise<string> {
  const dv = new DataView(buf), u8 = new Uint8Array(buf)
  let eocd = -1
  for (let i = buf.byteLength - 22; i >= 0; i--) { if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break } }
  if (eocd < 0) throw new Error('not a zip file')
  const n = dv.getUint16(eocd + 10, true)
  let p = dv.getUint32(eocd + 16, true)
  for (let k = 0; k < n; k++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break
    const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true)
    const nm = new TextDecoder().decode(u8.subarray(p + 46, p + 46 + nl))
    if (nm === name) {
      const lnl = dv.getUint16(off + 26, true), lel = dv.getUint16(off + 28, true), start = off + 30 + lnl + lel, data = u8.subarray(start, start + csize)
      if (method === 0) return new TextDecoder().decode(data)
      const ds = new DecompressionStream('deflate-raw'), w = ds.writable.getWriter()
      void w.write(data); void w.close()
      return await new Response(ds.readable).text()
    }
    p += 46 + nl + el + cl
  }
  throw new Error(name + ' not found')
}

/** questions: the view's `q` list, one [dimension, ...] entry per question. */
export async function parseQuestionnaire(file: File, questions: readonly (readonly string[])[]): Promise<{ answers: string[]; ratings: Record<string, number> }> {
  const xml = await readZipEntry(await file.arrayBuffer(), 'word/document.xml')
  const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  const doc = new DOMParser().parseFromString(xml, 'application/xml')
  const body = doc.getElementsByTagNameNS(W, 'body')[0]
  const tables = Array.from(body.children).filter((x) => x.localName === 'tbl').slice(1)
  const cellText = (tc: Element) => Array.from(tc.getElementsByTagNameNS(W, 'p')).map((p) => Array.from(p.getElementsByTagNameNS(W, 't')).map((t) => t.textContent).join('')).join('\n').trim()
  const answers: string[] = [], ratings: Record<string, number> = {}
  let qi = 0
  tables.forEach((t) => {
    const row = t.getElementsByTagNameNS(W, 'tr')[0]
    const cells = Array.from(row.children).filter((c) => c.localName === 'tc')
    if (cells.length === 1 && qi < questions.length) {
      let txt = cellText(cells[0]); if (txt.indexOf('Your answer:') === 0) txt = ''
      answers.push(txt); qi++
    } else if ((cells.length === 6 || cells.length === 4) && qi > 0) {
      const d = questions[qi - 1][0]
      const map: readonly (readonly [number, number])[] = cells.length === 6 ? [[1, 1], [2, 2], [3, 3], [4, 4], [5, 5]] : [[1, 1], [2, 3], [3, 5]]
      map.forEach(([ci, v]) => { if (cellText(cells[ci]).indexOf('\u2612') >= 0) ratings[d] = v })
    }
  })
  if (answers.length < questions.length) throw new Error(`expected ${questions.length} questions, found ${answers.length}`)
  return { answers, ratings }
}
