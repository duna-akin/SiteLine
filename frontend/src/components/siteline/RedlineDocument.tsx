import { useState } from 'react'
import { MessageSquare, Pencil, Undo2 } from 'lucide-react'

import { OverrideForm } from '@/components/siteline/DecisionCard'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { del, ins, RedlineDiff } from '@/components/siteline/RedlineDiff'
import { outcomeLabel } from '@/mocks/playbook'
import { effectiveOutcome } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { Decision } from '@/types'

/** Siteline couldn't settle these on its own, so a reviewer overrides them from here. */
const needsReviewer = (d: Decision) => d.outcome === 'human_review' || d.outcome === 'novel'

/** The paragraph exactly as the site marked it up: struck deletions and underlined insertions in place. */
function MarkedUpText({ d }: { d: Decision }) {
  if (!d.segments?.length) return <RedlineDiff change={d} />
  return (
    <p className="font-serif text-[15.5px] leading-relaxed text-ink">
      {d.segments.map((s, i) => {
        const by = s.author ?? d.author
        if (s.type === 'del') return <del key={i} className={del} title={`Deleted by ${by}`}>{s.text}</del>
        if (s.type === 'ins') {
          // A replacement's new words sit right after the struck ones; keep the two apart.
          const afterDel = d.segments![i - 1]?.type === 'del'
          return <ins key={i} className={afterDel ? `${ins} ml-1` : ins} title={`Inserted by ${by}`}>{s.text}</ins>
        }
        return <span key={i}>{s.text}</span>
      })}
    </p>
  )
}

function Paragraph({ d }: { d: Decision }) {
  const { clearOverride } = useDemo()
  const [editing, setEditing] = useState(false)
  const outcome = effectiveOutcome(d)

  return (
    <li className="border-t border-line pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="eyebrow font-sans">{d.section}</h4>
        <span className="flex flex-wrap items-center gap-1.5">
          {d.override && <span className="text-xs text-muted"><s>{outcomeLabel[d.outcome]}</s> →</span>}
          <OutcomeBadge outcome={outcome} size="sm" />
        </span>
      </div>
      <div className="mt-2">
        <MarkedUpText d={d} />
      </div>
      {d.siteComment && (
        <p className="mt-2 flex gap-2 text-sm">
          <MessageSquare aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" />
          <span><span className="font-semibold">{d.author}:</span> {d.siteComment}</span>
        </p>
      )}
      {needsReviewer(d) && (
        <>
          <p className="mt-2 text-xs text-muted">
            <code className="chip mr-1 text-xs">{d.ruleId}</code>
            {d.ruleText}
          </p>
          {d.override ? (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="min-w-0 flex-1"><span className="font-semibold">Overridden by you:</span> “{d.override.reason}”</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => void clearOverride(d.id)}>
                <Undo2 aria-hidden className="size-4" /> Undo override
              </button>
            </div>
          ) : editing ? (
            <OverrideForm d={d} onDone={() => setEditing(false)} />
          ) : (
            <button type="button" className="btn btn-secondary btn-sm mt-2" onClick={() => setEditing(true)}>
              <Pencil aria-hidden className="size-4" /> Override
            </button>
          )}
        </>
      )}
    </li>
  )
}

/** A site's redline as a document excerpt: each changed paragraph in order, with Siteline's outcome. */
export function RedlineDocument({ decisions }: { decisions: Decision[] }) {
  const paragraphs = [...decisions].sort((a, b) => a.index - b.index)
  return (
    <>
      <p className="mt-1 text-xs text-muted">
        <del className={del}>Struck</del> = removed by the site · <ins className={ins}>underlined</ins> = added by the site
      </p>
      <ol className="mt-3 space-y-4">
        {paragraphs.map((d) => <Paragraph key={d.id} d={d} />)}
      </ol>
    </>
  )
}
