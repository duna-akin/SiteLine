import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Menu, Search, Upload, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { SiteSearch } from '@/components/siteline/SiteSearch'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { cn } from '@/lib/utils'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'

/** Each tab and the paths it covers (Review and Export live under Sites, Upload under Inbound). */
const tabs: { to: string; label: string; match: (path: string) => boolean }[] = [
  { to: '/', label: 'Home', match: (p) => p === '/' },
  { to: '/inbound', label: 'Inbound', match: (p) => p.startsWith('/inbound') || p.startsWith('/upload') },
  { to: '/sites', label: 'Sites', match: (p) => p.startsWith('/sites') || p.startsWith('/review') },
  { to: '/data', label: 'Data', match: (p) => p.startsWith('/data') },
  { to: '/playbook', label: 'Playbook', match: (p) => p.startsWith('/playbook') },
]

export function Wordmark() {
  return (
    <span className="flex items-center gap-2 font-display text-[26px] leading-none font-bold">
      <span aria-hidden className="size-[22px] rounded-full bg-[radial-gradient(circle_at_35%_35%,var(--marker),var(--tangerine))] shadow-[0_0_0_4px_var(--peach)]" />
      siteline
    </span>
  )
}

function Tabs({ newEmail, onNavigate, stacked }: { newEmail: boolean; onNavigate?: () => void; stacked?: boolean }) {
  const { pathname } = useLocation()
  return tabs.map((t) => {
    const current = t.match(pathname)
    return (
      <NavLink
        key={t.to}
        to={t.to}
        onClick={onNavigate}
        aria-current={current ? 'page' : undefined}
        className={cn(
          'inline-flex min-h-10 items-center gap-1.5 rounded-full px-4 text-[15px] font-bold transition-colors duration-200',
          stacked && 'min-h-11 justify-between',
          current ? 'bg-ink text-[var(--on-ink)]' : 'text-muted hover:bg-bg hover:text-ink',
        )}
      >
        {t.label}
        {t.to === '/inbound' && newEmail && <span aria-label="new email waiting" className="size-2 rounded-full bg-tangerine" />}
      </NavLink>
    )
  })
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const { toasts, dismissToast } = useDemo()
  const { agreements, emails } = useDesk()
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const newEmail = (emails ?? []).some((e) => !e.triaged)

  // Move focus to the new page for keyboard and screen-reader users. A #hash link scrolls to
  // its target once the page has loaded it, so only plain navigation returns to the top.
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true })
    if (!location.hash) window.scrollTo({ top: 0 })
    setMenuOpen(false)
    setSearchOpen(false)
  }, [location.pathname, location.hash])

  return (
    <div className="relative flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-[var(--on-ink)]">
        Skip to content
      </a>

      <header className="py-[18px]">
        <div className="wrap flex items-center gap-4">
          <Link to="/" aria-label="Siteline home" className="rounded-lg">
            <Wordmark />
          </Link>
          <nav aria-label="Primary" className="ml-4 hidden gap-1 rounded-full bg-card p-[5px] shadow-[var(--shadow)] min-[1081px]:flex">
            <Tabs newEmail={newEmail} />
          </nav>
          <div className="ml-auto flex items-center gap-2.5">
            <SiteSearch agreements={agreements ?? []} emails={emails ?? []} className="hidden w-56 sm:block lg:w-64" />
            <button
              type="button"
              className="btn btn-soft size-11 p-0 sm:hidden"
              aria-label={searchOpen ? 'Close search' : 'Find a site or file'}
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen((v) => !v)}
            >
              {searchOpen ? <X aria-hidden className="size-5" /> : <Search aria-hidden className="size-5" />}
            </button>
            <Link to="/upload" className="btn btn-orange">
              <Upload aria-hidden className="size-4" />
              <span className="max-sm:sr-only">Upload</span>
            </Link>
            <button
              type="button"
              className="btn btn-soft size-11 p-0 min-[1081px]:hidden"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((v) => !v)}
            >
              {menuOpen ? <X aria-hidden className="size-5" /> : <Menu aria-hidden className="size-5" />}
            </button>
          </div>
        </div>
        {searchOpen && (
          <div className="wrap mt-3 sm:hidden">
            <SiteSearch agreements={agreements ?? []} emails={emails ?? []} autoFocus />
          </div>
        )}
        <AnimatePresence>
          {menuOpen && (
            <motion.nav
              id="mobile-nav"
              aria-label="Primary"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.14 } }}
              transition={{ duration: 0.2, ease: [0.2, 0.8, 0.2, 1] }}
              className="wrap mt-3 min-[1081px]:hidden"
            >
              <div className="grid grid-cols-2 gap-1 rounded-[24px] bg-card p-2 shadow-[var(--shadow)] sm:grid-cols-5">
                <Tabs newEmail={newEmail} onNavigate={() => setMenuOpen(false)} stacked />
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main id="main" ref={mainRef} tabIndex={-1} className="flex-1 outline-none">
        <Outlet />
      </main>

      <footer className="mt-12 border-t-2 border-line">
        <div className="wrap flex flex-col gap-4 py-8 text-sm text-muted md:flex-row md:items-center md:justify-between">
          <p>Fictional demo data. Clean room: public sources only, built this weekend for HackHarvard 2026.</p>
          <div className="flex flex-wrap gap-2">
            <SponsorChip sponsor="Photon" label="Photon 2.0 · approvals" />
            <SponsorChip sponsor="Daytona" label="Daytona · sandboxes" />
            <SponsorChip sponsor="Chalk" label="Chalk · Agent Evals" />
            <SponsorChip sponsor="Anthropic Claude" label="OpenAI · extraction" />
          </div>
        </div>
      </footer>

      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.button
              key={t.id}
              type="button"
              onClick={() => dismissToast(t.id)}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, transition: { duration: 0.15 } }}
              className="pointer-events-auto max-w-md rounded-full bg-ink px-5 py-3 text-sm font-bold text-[var(--on-ink)] shadow-[var(--shadow)]"
            >
              {t.text}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
