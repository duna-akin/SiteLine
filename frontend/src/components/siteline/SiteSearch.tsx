import { useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'

import { agreementPath } from '@/lib/sites'
import { cn } from '@/lib/utils'
import type { Agreement, InboundEmail } from '@/types'

interface Hit {
  key: string
  label: string
  detail: string
  to: string
}

const MAX_HITS = 6

function hitsFor(query: string, agreements: Agreement[], emails: InboundEmail[]): Hit[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  const has = (...parts: (string | undefined)[]) => parts.some((p) => p?.toLowerCase().includes(q))
  const sites = agreements
    .filter((a) => has(`site ${a.siteNumber}`, a.siteNumber, a.siteName, a.city, a.fileName))
    .map((a) => ({ key: `a-${a.id}`, label: `Site ${a.siteNumber} · ${a.siteName}`, detail: a.fileName ?? a.city, to: agreementPath(a) }))
  const files = emails
    .filter((e) => has(e.subject, e.attachment, e.siteName, e.from))
    .map((e) => ({
      key: `e-${e.id}`,
      label: e.subject,
      detail: `${e.attachment} · ${e.from}`,
      to: e.triaged && e.agreementId ? `/review/${e.agreementId}` : `/inbound#email-${e.id}`,
    }))
  return [...sites, ...files].slice(0, MAX_HITS)
}

/** "Find a site or file": a client-side filter over loaded agreements and inbound emails. */
export function SiteSearch({ agreements, emails, className, autoFocus, onNavigate }: {
  agreements: Agreement[]
  emails: InboundEmail[]
  className?: string
  autoFocus?: boolean
  onNavigate?: () => void
}) {
  const navigate = useNavigate()
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const hits = useMemo(() => hitsFor(query, agreements, emails), [query, agreements, emails])
  const showList = open && query.trim().length > 0

  function go(hit: Hit | undefined) {
    if (!hit) return
    setQuery('')
    setOpen(false)
    input.current?.blur()
    navigate(hit.to)
    onNavigate?.()
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, hits.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      go(hits[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className={cn('relative', className)}>
      <label
        htmlFor={id}
        className="flex min-h-11 items-center gap-2 rounded-full bg-card px-4 text-[15px] text-muted shadow-[var(--shadow)] focus-within:outline-3 focus-within:outline-blue"
      >
        <Search aria-hidden className="size-4 shrink-0" />
        <span className="sr-only">Find a site or file</span>
        <input
          ref={input}
          id={id}
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={showList && hits[active] ? `${id}-${hits[active].key}` : undefined}
          autoComplete="off"
          autoFocus={autoFocus}
          placeholder="Find a site or file"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKey}
          className="w-full min-w-0 bg-transparent text-ink outline-none placeholder:text-muted"
        />
      </label>
      {showList && (
        <ul
          id={`${id}-list`}
          role="listbox"
          aria-label="Matching sites and files"
          className="absolute top-full right-0 left-0 z-50 mt-2 flex max-h-80 flex-col gap-1 overflow-y-auto rounded-[20px] bg-card p-2 shadow-[var(--shadow)] sm:min-w-80"
        >
          {hits.length === 0 && <li className="px-3 py-2 text-sm text-muted">No site or file matches “{query.trim()}”.</li>}
          {hits.map((h, i) => (
            <li
              key={h.key}
              id={`${id}-${h.key}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => go(h)}
              onMouseEnter={() => setActive(i)}
              className={cn('cursor-pointer rounded-[14px] px-3 py-2', i === active && 'bg-bg')}
            >
              <span className="block truncate text-sm font-extrabold">{h.label}</span>
              <span className="block truncate text-xs text-muted">{h.detail}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
