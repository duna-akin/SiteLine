import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Check, ChevronDown, ChevronLeft, ChevronRight, MessageSquare, X } from 'lucide-react'

import { DecisionDetail } from '@/components/siteline/DecisionDetail'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { outcomeBg, outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import { effectiveOutcome, isConfirmed, isWaiting } from '@/state/decision'
import type { Decision, DocParagraph, Segment } from '@/types'

// Redline convention: struck-through deletions, underlined insertions
const del = 'text-high line-through decoration-high'
const ins = 'text-accent underline decoration-accent underline-offset-[3px]'
const body = 'font-serif text-[15.5px] leading-relaxed text-ink'
const anchor = (d: Decision) => `change-${d.id}`

/** Segments as the site marked them up: struck deletions and underlined insertions in place. */
function MarkedUp({ segments, author }: { segments: Segment[]; author?: string }) {
  return segments.map((s, i) => {
    const by = s.author ?? author
    if (s.type === 'del') return <del key={i} className={del} title={by && `Deleted by ${by}`}>{s.text}</del>
    if (s.type === 'ins') {
      // A replacement's new words sit right after the struck ones; keep the two apart.
      const afterDel = segments[i - 1]?.type === 'del'
      return <ins key={i} className={afterDel ? `${ins} ml-1` : ins} title={by && `Inserted by ${by}`}>{s.text}</ins>
    }
    return <span key={i}>{s.text}</span>
  })
}

// Decisions saved before segments were kept: show the whole old text struck and the new underlined
const fromChange = (d: Decision): Segment[] => [
  { type: 'del' as const, text: d.original },
  { type: 'ins' as const, text: d.revised },
].filter((s) => s.text)

const plainText = (p: DocParagraph) => p.segments.map((s) => s.text).join('')

/** An unchanged paragraph, styled by its Word style. */
function Plain({ p }: { p: DocParagraph }) {
  const text = <MarkedUp segments={p.segments} />
  if (p.style === 'Title') return <h2 className="mb-4 text-center text-[28px]">{text}</h2>
  if (p.heading && p.style === 'Heading1') return <h3 className="mt-8 mb-2 text-[20px]">{text}</h3>
  if (p.heading) return <h4 className="mt-5 mb-1 font-serif text-[16px] font-semibold">{text}</h4>
  return <p className={cn(body, 'mb-3')}>{text}</p>
}

/** What still needs a person on this change, if anything. */
function Status({ d }: { d: Decision }) {
  const o = effectiveOutcome(d)
  if (o === 'escalate' && isWaiting(d)) return <span className="pill s-high">Awaiting approver</span>
  if (isWaiting(d)) return null // Human review: the tag already says a person decides
  if (!isConfirmed(d)) return <span className="pill s-elevated">To confirm</span>
  return <span className="inline-flex items-center gap-1 text-xs text-muted"><Check aria-hidden className="size-3.5" /> Signed off</span>
}

const PANEL_ID = 'decision-panel'

/** A paragraph the site changed: tinted by Siteline's outcome; clicking it opens the decision
 * beside the contract (under the paragraph on narrow screens). */
function Redlined({ d, open, onToggle }: { d: Decision; open: boolean; onToggle: () => void }) {
  const o = effectiveOutcome(d)
  return (
    <div id={anchor(d)} className="mb-3 scroll-mt-24">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={PANEL_ID}
        onClick={onToggle}
        className={cn(
          '-mx-3 block w-[calc(100%+1.5rem)] rounded-[4px] border-l-[3px] px-3 py-2 text-left transition-shadow',
          open ? 'shadow-[inset_0_0_0_2px_var(--ink-2)]' : 'hover:shadow-[inset_0_0_0_1px_var(--line-strong)]',
        )}
        style={{ borderLeftColor: outcomeVar[o], background: outcomeBg[o] }}
      >
        <span className={cn(body, 'block')}>
          <MarkedUp segments={d.segments?.length ? d.segments : fromChange(d)} author={d.author} />
        </span>
        <span className="mt-1.5 flex flex-wrap items-center gap-2 font-sans">
          <OutcomeBadge outcome={o} size="sm" />
          <Status d={d} />
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted">
            {open ? 'Hide decision' : 'Show decision'}
            <ChevronDown aria-hidden className={cn('size-4 transition-transform', open ? 'rotate-180' : 'lg:-rotate-90')} />
          </span>
        </span>
      </button>
      {d.siteComment && (
        <p className="mt-1.5 flex gap-2 font-sans text-sm">
          <MessageSquare aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" />
          <span><span className="font-semibold">{d.author}:</span> {d.siteComment}</span>
        </p>
      )}
      {open && <div className="lg:hidden"><DecisionDetail d={d} className="mt-2 mb-4" /></div>}
    </div>
  )
}

/** The open decision, beside the contract and in view while it scrolls. */
function SidePanel({ d, order, select }: { d: Decision | null; order: Decision[]; select: (d: Decision | null) => void }) {
  if (!d) {
    return (
      <div className="panel p-5 text-sm text-muted">
        Choose a redlined paragraph to see Siteline’s decision, the rule behind it and any precedent.
      </div>
    )
  }
  const i = order.findIndex((x) => x.id === d.id)
  const step = (by: number) => order[i + by] && select(order[i + by])
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate font-serif text-[17px]">{d.section}</h2>
        <span className="text-xs text-muted tabular">{i + 1} of {order.length}</span>
        <button type="button" className="btn btn-secondary btn-sm px-1.5" disabled={i <= 0} onClick={() => step(-1)} aria-label="Previous change">
          <ChevronLeft aria-hidden className="size-4" />
        </button>
        <button type="button" className="btn btn-secondary btn-sm px-1.5" disabled={i >= order.length - 1} onClick={() => step(1)} aria-label="Next change">
          <ChevronRight aria-hidden className="size-4" />
        </button>
        <button type="button" className="btn btn-secondary btn-sm px-1.5" onClick={() => select(null)} aria-label="Close decision">
          <X aria-hidden className="size-4" />
        </button>
      </div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <OutcomeBadge outcome={effectiveOutcome(d)} size="sm" />
        <Status d={d} />
      </div>
      <DecisionDetail key={d.id} d={d} />
    </div>
  )
}

/** Counts per outcome; each one jumps to the next redline with that outcome below the current view. */
function OutcomeBar({ decisions, jump }: { decisions: Decision[]; jump: (d: Decision) => void }) {
  function next(o: string) {
    const hits = decisions.filter((d) => effectiveOutcome(d) === o)
    const below = hits.find((d) => (document.getElementById(anchor(d))?.getBoundingClientRect().top ?? 0) > 110)
    const target = below ?? hits[0]
    if (target) jump(target)
  }
  return (
    <div className="sticky top-0 z-10 -mx-1 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line bg-page/95 px-1 py-2.5 text-sm backdrop-blur" role="group" aria-label="Jump to the next change by outcome">
      <span className="text-muted">{decisions.length} changes · jump to</span>
      {outcomeOrder.map((o) => {
        const n = decisions.filter((d) => effectiveOutcome(d) === o).length
        const Icon = outcomeIcon[o]
        return (
          <button key={o} type="button" disabled={n === 0} onClick={() => next(o)}
            className="inline-flex min-h-8 items-center gap-1.5 rounded-[4px] px-1.5 font-medium hover:bg-subtle disabled:opacity-40"
            style={{ color: outcomeVar[o] }}>
            <Icon aria-hidden className="size-3.5" /> {outcomeLabel[o]} <span className="tabular text-ink">{n}</span>
          </button>
        )
      })}
      <span className="ml-auto hidden text-xs text-muted sm:inline">
        <del className={del}>Struck</del> removed by the site · <ins className={ins}>underlined</ins> added
      </span>
    </div>
  )
}

/**
 * The whole agreement as the site sent it back, with each redlined paragraph tagged by Siteline's
 * outcome. Without a stored document (older agreements) it shows the redlined paragraphs alone.
 */
export function ContractDocument({ paragraphs, decisions }: { paragraphs: DocParagraph[] | null; decisions: Decision[] }) {
  const { hash } = useLocation()
  const [selectedId, setSelectedId] = useState<string | null>(
    () => decisions.find((d) => `#${anchor(d)}` === decodeURIComponent(hash))?.id ?? null,
  )
  const order = [...decisions].sort((a, b) => a.index - b.index)
  const selected = decisions.find((d) => d.id === selectedId) ?? null

  const select = (d: Decision | null) => {
    setSelectedId(d?.id ?? null)
    if (!d) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(anchor(d))?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' })
  }

  const byParagraph = new Map(decisions.map((d) => [d.paragraph, d]))
  const redlined = (d: Decision) => (
    <Redlined key={d.id} d={d} open={d.id === selectedId} onToggle={() => setSelectedId(d.id === selectedId ? null : d.id)} />
  )

  return (
    <>
      <OutcomeBar decisions={order} jump={select} />
      <div className="mt-4 grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
        <article aria-label="Agreement" className="panel px-6 py-8 sm:px-12 sm:py-12">
          {paragraphs
            ? paragraphs.map((p) => {
                const d = byParagraph.get(p.index)
                if (d) return redlined(d)
                return plainText(p).trim() ? <Plain key={p.index} p={p} /> : null
              })
            : (
              <>
                <p className="mb-6 font-sans text-sm text-muted">The full text wasn’t kept for this agreement, so only the redlined paragraphs are shown.</p>
                {order.map((d) => (
                  <div key={d.id}>
                    <h4 className="mt-5 mb-1 font-serif text-[16px] font-semibold">{d.section}</h4>
                    {redlined(d)}
                  </div>
                ))}
              </>
            )}
        </article>
        <aside id={PANEL_ID} aria-label="Decision" aria-live="polite"
          className="sticky top-16 hidden max-h-[calc(100vh-5rem)] overflow-y-auto overscroll-contain lg:block">
          <SidePanel d={selected} order={order} select={select} />
        </aside>
      </div>
    </>
  )
}
