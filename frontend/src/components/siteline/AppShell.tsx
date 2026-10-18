import { Suspense, useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Menu, Search, Upload, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { SiteSearch } from '@/components/siteline/SiteSearch'
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
    <span className="flex items-center gap-2.5">
      <span aria-hidden className="grid size-8 place-items-center rounded-[6px] bg-ink-2 text-white">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M4 16a8 8 0 0 1 16 0" /><path d="M2 20h20" /><path d="M12 4v3" />
        </svg>
      </span>
      <span className="font-serif text-[21px] leading-none font-medium tracking-tight text-ink">Siteline</span>
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
          'relative inline-flex items-center gap-1.5 text-[14px] font-medium transition-colors duration-150',
          stacked
            ? cn('min-h-11 justify-between rounded-[6px] px-3', current ? 'bg-page text-ink' : 'text-muted hover:bg-page hover:text-ink')
            : cn(
                'h-16 flex-1 justify-center px-3 after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:transition-colors',
                current ? 'text-ink after:bg-accent' : 'text-muted after:bg-transparent hover:text-ink',
              ),
        )}
      >
        {t.label}
        {t.to === '/inbound' && newEmail && <span aria-label="new email waiting" className="size-1.5 rounded-full bg-accent" />}
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
  }, [location.pathname, location.hash])

  return (
    <div className="relative flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-[6px] focus:bg-ink focus:px-4 focus:py-2 focus:text-white">
        Skip to content
      </a>

      <header className="border-b border-line bg-surface">
        <div className="wrap flex h-16 items-center gap-6">
          <Link to="/" aria-label="Siteline home" className="shrink-0 rounded-[6px]">
            <Wordmark />
          </Link>
          <nav aria-label="Primary" className="hidden flex-1 items-center min-[1081px]:flex">
            <Tabs newEmail={newEmail} />
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <SiteSearch agreements={agreements ?? []} emails={emails ?? []} className="hidden w-56 sm:block lg:w-64" />
            <button
              type="button"
              className="btn btn-secondary size-10 p-0 sm:hidden"
              aria-label={searchOpen ? 'Close search' : 'Find a site or file'}
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen((v) => !v)}
            >
              {searchOpen ? <X aria-hidden className="size-4" /> : <Search aria-hidden className="size-4" />}
            </button>
            <Link to="/upload" className="btn btn-primary" onClick={() => setMenuOpen(false)}>
              <Upload aria-hidden className="size-4" />
              <span className="max-sm:sr-only">Upload redline</span>
            </Link>
            <button
              type="button"
              className="btn btn-secondary size-10 p-0 min-[1081px]:hidden"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((v) => !v)}
            >
              {menuOpen ? <X aria-hidden className="size-4" /> : <Menu aria-hidden className="size-4" />}
            </button>
          </div>
        </div>
        {searchOpen && (
          <div className="wrap pb-3 sm:hidden">
            <SiteSearch agreements={agreements ?? []} emails={emails ?? []} autoFocus onNavigate={() => setSearchOpen(false)} />
          </div>
        )}
        <AnimatePresence>
          {menuOpen && (
            <motion.nav
              id="mobile-nav"
              aria-label="Primary"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.12 } }}
              transition={{ duration: 0.15 }}
              className="wrap pb-3 min-[1081px]:hidden"
            >
              <div className="grid grid-cols-2 gap-1 border-t border-line pt-3 sm:grid-cols-5">
                <Tabs newEmail={newEmail} onNavigate={() => setMenuOpen(false)} stacked />
              </div>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main id="main" ref={mainRef} tabIndex={-1} className="flex-1 outline-none">
        {/* Pages load lazily; the header stays while one does */}
        <Suspense fallback={<div className="wrap py-16 text-muted" role="status">Loading…</div>}>
          <Outlet />
        </Suspense>
      </main>

      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.button
              key={t.id}
              type="button"
              onClick={() => dismissToast(t.id)}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, transition: { duration: 0.12 } }}
              transition={{ duration: 0.18 }}
              className="pointer-events-auto max-w-md rounded-[6px] bg-ink px-4 py-2.5 text-[13.5px] font-medium text-white shadow-[0_4px_16px_rgba(33,33,33,.18)]"
            >
              {t.text}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
