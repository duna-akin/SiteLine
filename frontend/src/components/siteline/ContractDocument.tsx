import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Check, ChevronDown, MessageSquare } from 'lucide-react'

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
  if (isWaiting(d)) return <span className="pill s-high">Needs your decision</span>
  if (!isConfirmed(d)) return <span className="pill s-elevated">To confirm</span>
  return <span className="inline-flex items-center gap-1 text-xs text-muted"><Check aria-hidden className="size-3.5" /> Signed off</span>
}

/** A paragraph the site changed: tinted by Siteline's outcome; clicking it unfolds the decision. */
function Redlined({ d, open, onToggle }: { d: Decision; open: boolean; onToggle: () => void }) {
  const o = effectiveOutcome(d)
  const detailId = `${anchor(d)}-detail`
  return (
    <div id={anchor(d)} className="mb-3 scroll-mt-24">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={onToggle}
        className="-mx-3 block w-[calc(100%+1.5rem)] rounded-[4px] border-l-[3px] px-3 py-2 text-left transition-shadow hover:shadow-[inset_0_0_0_1px_var(--line-strong)]"
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
            <ChevronDown aria-hidden className={cn('size-4 transition-transform', open && 'rotate-180')} />
          </span>
        </span>
      </button>
      {d.siteComment && (
        <p className="mt-1.5 flex gap-2 font-sans text-sm">
          <MessageSquare aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" />
          <span><span className="font-semibold">{d.author}:</span> {d.siteComment}</span>
        </p>
      )}
      {open && <div id={detailId}><DecisionDetail d={d} /></div>}
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
  const linked = decisions.find((d) => `#${anchor(d)}` === decodeURIComponent(hash))
  const [open, setOpen] = useState<Set<string>>(() => new Set(linked ? [linked.id] : []))

  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s)
      if (!n.delete(id)) n.add(id)
      return n
    })
  const jump = (d: Decision) => {
    setOpen((s) => new Set(s).add(d.id))
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(anchor(d))?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }

  const byParagraph = new Map(decisions.map((d) => [d.paragraph, d]))
  const redlined = (d: Decision) => <Redlined key={d.id} d={d} open={open.has(d.id)} onToggle={() => toggle(d.id)} />

  return (
    <>
      <OutcomeBar decisions={[...decisions].sort((a, b) => a.index - b.index)} jump={jump} />
      <article aria-label="Agreement" className="panel mx-auto mt-4 max-w-[52rem] px-6 py-8 sm:px-12 sm:py-12">
        {paragraphs
          ? paragraphs.map((p) => {
              const d = byParagraph.get(p.index)
              if (d) return redlined(d)
              return plainText(p).trim() ? <Plain key={p.index} p={p} /> : null
            })
          : (
            <>
              <p className="mb-6 font-sans text-sm text-muted">The full text wasn’t kept for this agreement, so only the redlined paragraphs are shown.</p>
              {[...decisions].sort((a, b) => a.index - b.index).map((d) => (
                <div key={d.id}>
                  <h4 className="mt-5 mb-1 font-serif text-[16px] font-semibold">{d.section}</h4>
                  {redlined(d)}
                </div>
              ))}
            </>
          )}
      </article>
    </>
  )
}
