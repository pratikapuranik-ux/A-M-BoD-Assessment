import { type ReactNode } from 'react'
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useQueryClient } from '@tanstack/react-query'
import { AmLogo, Icon } from './Icon'
import { Button, Toaster, TipProvider, Tip } from './ui'
import JobRunner from './JobRunner'
import { useJourney } from '../lib/useJourney'
import { useSession } from '../store/session'
import { useInsideOut } from '../store/insideOut'
import { DRAFT } from '../lib/constants'
import { initials, PATHS } from '../lib/journey'

export function Brand({ to = '/home' }: { to?: string }) {
  return (
    <Link to={to} className="brandrow" aria-label="Home">
      <AmLogo white /><span className="bdiv" /><span className="bname">Board Assessment</span>
    </Link>
  )
}

export function DraftFooter() { return <footer className="afoot2"><div className="wrap">{DRAFT}</div></footer> }

function Topbar() {
  const nav = useNavigate()
  const loc = useLocation()
  const qc = useQueryClient()
  const { session, actions, oiDone, ioDone } = useJourney()
  const assess = ioDone ? PATHS.ioRead : oiDone ? PATHS.oi : PATHS.setup
  const links: [string, string, boolean][] = [
    ['Home', '/home', loc.pathname === '/home'],
    ['Assessment', assess, loc.pathname.startsWith('/journey')],
    ['Briefcase', '/briefcase', loc.pathname === '/briefcase'],
  ]
  /* Sign-out clears what this browser keeps and drops cached server data, which also ends any polling for the last user. */
  const signOut = () => {
    session.signOut(); useInsideOut.setState({ docs: {}, other: [], qFiles: [], addJob: null, ioRuns: {} }); useInsideOut.getState().resetAdd()
    qc.clear(); nav('/')
  }
  return (
    <header className="tb">
      <div className="wrap tbi">
        <Brand />
        <nav className="tnav" aria-label="Main">
          {links.map(([l, to, on]) => <Link key={l} to={to} className={on ? 'on' : ''} aria-current={on ? 'page' : undefined}>{l}</Link>)}
        </nav>
        <div className="tr">
          <Tip text="Actions"><Link to="/home" className="bell" aria-label={`Actions, ${actions.length} open`}><Icon name="clip" size={19} /><b>{actions.length}</b></Link></Tip>
          <div className="uchip2"><div className="av">{initials(session.name)}</div><div><span>{session.name}</span><small>{session.email}</small></div></div>
          <Button variant="ghost" size="sm" onClick={signOut}>Sign out</Button>
        </div>
      </div>
      <nav className="tnavm" aria-label="Main (compact)">
        {links.map(([l, to, on]) => <Link key={l} to={to} className={on ? 'on' : ''}>{l}</Link>)}
      </nav>
    </header>
  )
}

/** Signed-in frame: top bar, page transition, footer, toasts and the background job followers. */
export function AppShell() {
  const email = useSession((s) => s.email)
  const loc = useLocation()
  if (!email) return <Navigate to="/" replace state={{ from: loc.pathname }} />
  return (
    <TipProvider delayDuration={200}>
      <Topbar />
      <main className="mainc">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={loc.pathname.startsWith('/journey') ? '/journey' : loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <DraftFooter />
      <JobRunner />
      <Toaster />
    </TipProvider>
  )
}

/** Navy title area that the first cards overlap. */
export function Band({ children }: { children: ReactNode }) {
  return <><section className="band"><div className="wrap">{children}</div></section></>
}

export function BackLink({ to, children, inverse = false }: { to: string; children: ReactNode; inverse?: boolean }) {
  return <Link to={to} className={`bklink${inverse ? ' inv' : ''}`}><Icon name="arrow" size={15} />{children}</Link>
}

