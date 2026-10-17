import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { BookOpenCheck, FileUp, FlaskConical, Inbox, ListChecks, Menu, Radar, X, type LucideIcon } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { SponsorChip } from '@/components/siteline/SponsorChip'
import { StarField } from '@/components/siteline/StarField'
import { cn } from '@/lib/utils'
import { useDemo } from '@/state/demo'

const nav: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/', label: 'Inbox', icon: Inbox },
  { to: '/upload', label: 'Upload', icon: FileUp },
  { to: '/review/site-07', label: 'Review', icon: ListChecks },
  { to: '/portfolio', label: 'Radar', icon: Radar },
  { to: '/evals', label: 'Evals', icon: FlaskConical },
  { to: '/playbook', label: 'Playbook', icon: BookOpenCheck },
]

export function Wordmark() {
  return (
    <span className="inline-flex items-baseline gap-2">
      <span className="font-serif text-2xl leading-none text-yellow sm:text-[1.7rem]">Siteline</span>
      <span aria-hidden className="relative top-[-2px] size-2 rounded-full bg-magenta shadow-[0_0_12px_var(--magenta)]" />
    </span>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return nav.map(({ to, label, icon: Icon }) => (
    <NavLink
      key={to}
      to={to}
      end={to === '/'}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex min-h-11 items-center gap-2 rounded-full px-3.5 text-sm font-bold transition-colors duration-200',
          isActive ? 'bg-yellow text-ink' : 'text-muted hover:bg-space-2 hover:text-text',
        )
      }
    >
      <Icon aria-hidden className="size-4" />
      {label}
    </NavLink>
  ))
}

export function AppShell() {
  const [open, setOpen] = useState(false)
  const { toasts, dismissToast } = useDemo()
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)

  // Move focus to the new page for keyboard and screen-reader users.
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true })
    window.scrollTo({ top: 0 })
  }, [location.pathname])

  return (
    <div className="relative flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-yellow focus:px-4 focus:py-2 focus:text-ink">
        Skip to content
      </a>
      <StarField />

      <header className="sticky top-0 z-40 border-b border-line bg-space/80 backdrop-blur-md">
        <div className="wrap flex h-16 items-center justify-between gap-4">
          <NavLink to="/" aria-label="Siteline home" className="rounded-lg">
            <Wordmark />
          </NavLink>
          <nav aria-label="Primary" className="hidden items-center gap-1 lg:flex">
            <NavItems />
          </nav>
          <button
            type="button"
            className="btn btn-ghost size-11 p-0 lg:hidden"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
        <AnimatePresence>
          {open && (
            <motion.nav
              id="mobile-nav"
              aria-label="Primary"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8, transition: { duration: 0.14 } }}
              transition={{ duration: 0.2, ease: [0.2, 0.8, 0.2, 1] }}
              className="wrap grid grid-cols-2 gap-1 pb-4 lg:hidden"
            >
              <NavItems onNavigate={() => setOpen(false)} />
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main id="main" ref={mainRef} tabIndex={-1} className="flex-1 outline-none">
        <Outlet />
      </main>

      <footer className="mt-16 border-t border-line">
        <div className="wrap flex flex-col gap-4 py-8 text-sm text-muted md:flex-row md:items-center md:justify-between">
          <p>
            Fictional demo data. Clean room: public sources only, built this weekend for HackHarvard 2026.
          </p>
          <div className="flex flex-wrap gap-2">
            <SponsorChip sponsor="Photon" label="Photon 2.0 · approvals" />
            <SponsorChip sponsor="Daytona" label="Daytona · sandboxes" />
            <SponsorChip sponsor="Chalk" label="Chalk · Agent Evals" />
            <SponsorChip sponsor="Anthropic Claude" label="Claude · extraction" />
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
              className="pointer-events-auto max-w-md rounded-full border border-line bg-space-2 px-5 py-3 text-sm font-medium text-text shadow-[0_10px_40px_-10px_var(--magenta)]"
            >
              {t.text}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
