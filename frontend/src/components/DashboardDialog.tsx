import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'

/** Near full-screen dialog showing the backend-generated HTML dashboard in an iframe. */
export default function DashboardDialog({ open, onOpenChange, title, url }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; url: string }) {
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading')
  const [loaded, setLoaded] = useState(false)

  /* check the file exists before mounting the iframe, so a 404 shows a message instead of a JSON error page */
  useEffect(() => {
    if (!open) return
    let dead = false
    setState('loading'); setLoaded(false)
    const probe = async () => {
      try {
        let r = await fetch(url, { method: 'HEAD' })
        if (r.status === 405 || r.status === 501) r = await fetch(url)
        if (!dead) setState(r.ok ? 'ok' : 'error')
      } catch {
        if (!dead) setState('error')
      }
    }
    void probe()
    return () => { dead = true }
  }, [open, url])

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dlg-overlay" />
        <Dialog.Content
          aria-describedby={undefined}
          style={{ position: 'fixed', zIndex: 61, top: '2vh', left: '2vw', width: '96vw', height: '96vh', display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 12, boxShadow: '0 20px 60px rgba(0,43,73,.35)', padding: 12 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', paddingBottom: 8 }}>
            <Dialog.Title style={{ margin: 0, color: 'var(--navy, #002B49)', fontSize: '1.1rem', flex: 1 }}>{title}</Dialog.Title>
            {state === 'ok' && <a href={url} target="_blank" rel="noopener" style={{ fontWeight: 700, color: '#0085CA' }}>Open in a new tab</a>}
            <Dialog.Close aria-label="Close" style={{ border: '1px solid #D9D9D9', background: '#fff', borderRadius: 8, width: 36, height: 36, fontSize: '1.3rem', lineHeight: 1, cursor: 'pointer' }}>×</Dialog.Close>
          </div>
          {state === 'loading' && <p className="muted" role="status">Loading the dashboard…</p>}
          {state === 'error' && <p role="alert" style={{ color: '#A6192E' }}>The dashboard file could not be loaded. It may not have been generated yet; try again after the assessment finishes.</p>}
          {state === 'ok' && (
            <>
              {!loaded && <p className="muted" role="status">Loading the dashboard…</p>}
              <iframe
                src={url}
                title={title}
                sandbox="allow-scripts allow-same-origin allow-popups allow-downloads"
                onLoad={() => setLoaded(true)}
                style={{ flex: 1, width: '100%', minHeight: '80vh', border: 0 }}
              />
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
