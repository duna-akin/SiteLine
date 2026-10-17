import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Download, LoaderCircle, TriangleAlert } from 'lucide-react'

import * as api from '@/api'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { BlurFade } from '@/components/ui/blur-fade'
import { SPONSOR, approvers, replyMeaning } from '@/mocks/playbook'
import { SITE07 } from '@/mocks/site07'
import { effectiveOutcome } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { Decision } from '@/types'

interface Entry {
  d: Decision
  /** Text Siteline sends back; null means the site's language stands. */
  counter: string | null
  comment: string
  pending: boolean
}

function toEntry(d: Decision): Entry {
  const outcome = effectiveOutcome(d)
  const who = approvers[d.owner].name
  if (d.override) {
    return {
      d,
      counter: outcome === 'accept' ? null : d.counterText ?? d.original ?? null,
      comment: `Contract manager override: ${d.override.reason}`,
      pending: false,
    }
  }
  if (d.outcome === 'escalate') {
    if (d.approval.state !== 'answered') return { d, counter: null, comment: `Pending approval from ${who}.`, pending: true }
    return {
      d,
      counter: d.approval.reply === 1 ? null : d.counterText ?? d.original,
      comment: `${who} replied ${d.approval.reply} (${replyMeaning[d.approval.reply].toLowerCase()}).`,
      pending: false,
    }
  }
  if (outcome === 'human_review' || outcome === 'novel') {
    return { d, counter: null, comment: 'Held for contract manager review. Resolve with an override before sending.', pending: true }
  }
  if (outcome === 'fallback') return { d, counter: d.counterText ?? null, comment: `Playbook fallback (${d.ruleId}).`, pending: false }
  return { d, counter: null, comment: `Accepted under ${d.ruleId}.`, pending: false }
}

export function ExportPage() {
  const { decisions, notify } = useDemo()
  const [busy, setBusy] = useState(false)
  const entries = decisions.map(toEntry)
  const pending = entries.filter((e) => e.pending).length

  async function download() {
    setBusy(true)
    const res = await api.exportCounterProposal(SITE07.agreementId)
    setBusy(false)
    notify(`Export stub: ${res.fileName} would download here`)
  }

  return (
    <div className="wrap py-10 sm:py-14">
      <Link to="/review/site-07" className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-muted hover:text-text">
        <ArrowLeft aria-hidden className="size-4" /> Back to review
      </Link>
      <BlurFade>
        <p className="eyebrow mt-4">Step 3 · Export</p>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-4xl sm:text-5xl">Counter-proposal</h1>
            <p className="mt-2 text-muted">Word file with tracked changes and one comment per decision.</p>
          </div>
          <button type="button" className="btn btn-primary" onClick={download} disabled={busy || decisions.length === 0}>
            {busy ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Download aria-hidden className="size-4" />}
            Download .docx
          </button>
        </div>
      </BlurFade>

      {decisions.length === 0 ? (
        <div className="panel mt-8 p-8 text-center">
          <p className="text-muted">Nothing to export yet.</p>
          <Link to="/upload" className="btn btn-primary mt-4">Triage Site 07</Link>
        </div>
      ) : (
        <>
          {pending > 0 && (
            <p role="status" className="mt-6 flex items-start gap-2 rounded-2xl border border-butter/50 bg-butter/10 px-4 py-3 text-sm">
              <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-butter" />
              {pending} item{pending > 1 ? 's are' : ' is'} still pending. They export as comments, not as changes.
            </p>
          )}

          <article
            aria-label="Counter-proposal preview"
            className="mt-6 rounded-[6px] bg-cream p-5 text-ink shadow-[0_30px_80px_-30px_var(--magenta)] sm:p-10"
          >
            <header className="border-b border-ink/15 pb-5">
              <p className="text-xs font-bold tracking-[0.16em] text-ink/70 uppercase">{SPONSOR.name} · Protocol {SPONSOR.protocol}</p>
              <h2 className="mt-2 text-2xl text-ink sm:text-3xl">Clinical Trial Agreement · Sponsor counter-proposal</h2>
              <p className="mt-1 text-sm text-ink/70">Site {SITE07.siteNumber}, {SITE07.siteName} · responding to {SITE07.fileName}</p>
            </header>
            <ol className="mt-6 flex flex-col gap-6">
              {entries.map(({ d, counter, comment, pending: isPending }) => (
                <li key={d.id} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_240px]">
                  <div>
                    <p className="font-bold">{d.section}</p>
                    <p className="mt-1 leading-relaxed">
                      {counter !== null ? (
                        <>
                          {d.revised && <del className="text-ink/60 decoration-red decoration-2">{d.revised}</del>}{' '}
                          <ins className="text-blue underline decoration-blue decoration-2 underline-offset-4">{counter}</ins>
                        </>
                      ) : (
                        <span>{d.revised || <del className="text-ink/60 decoration-red decoration-2">{d.original}</del>}</span>
                      )}
                    </p>
                  </div>
                  <aside className="rounded-md border-l-4 bg-ink/5 px-3 py-2 text-sm" style={{ borderColor: isPending ? 'var(--butter)' : 'var(--blue)' }}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-ink/70">Siteline comment</span>
                      <span className="rounded-full bg-ink"><OutcomeBadge outcome={effectiveOutcome(d)} size="sm" /></span>
                    </div>
                    <p className="mt-1">{comment}</p>
                  </aside>
                </li>
              ))}
            </ol>
          </article>
        </>
      )}
    </div>
  )
}
