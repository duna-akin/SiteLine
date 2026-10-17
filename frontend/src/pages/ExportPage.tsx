import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, BadgeCheck, Download, FileText, LoaderCircle, TriangleAlert } from 'lucide-react'

import * as api from '@/api'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { BlurFade } from '@/components/ui/blur-fade'
import { SPONSOR, approvers, replyMeaning } from '@/mocks/playbook'
import { effectiveOutcome } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { Decision } from '@/types'

interface Entry {
  d: Decision
  /** Text the sponsor sends back; null means the site's language stands. '' deletes it. */
  counter: string | null
  comment: string
  pending: boolean
}

/** Same rules as the backend export (backend/src/siteline/export.py: final_text). */
function toEntry(d: Decision): Entry {
  const outcome = effectiveOutcome(d)
  const who = approvers[d.owner].name
  const hold = d.counterText ?? d.original
  const note = d.override ? ` Override: ${d.override.reason}` : ''
  if (outcome === 'accept') return { d, counter: null, comment: `Accepted under ${d.ruleId}.${note}`, pending: false }
  if (outcome === 'fallback') {
    return { d, counter: hold, comment: `${d.counterText != null ? 'Playbook fallback' : 'Standard held'} (${d.ruleId}).${note}`, pending: false }
  }
  if (outcome === 'escalate') {
    if (d.approval.state !== 'answered') return { d, counter: null, comment: `Pending approval from ${who}.${note}`, pending: true }
    const r = d.approval.reply
    const counter = r === 1 ? null : r === 2 ? (d.fallbackText ?? hold) : hold
    return { d, counter, comment: `${who} replied ${r} (${replyMeaning[r].toLowerCase()}).${note}`, pending: false }
  }
  return { d, counter: null, comment: 'Held for contract manager review. Resolve with an override before sending.', pending: true }
}

export function ExportPage() {
  const { agreementId } = useParams()
  const { decisions, agreement, loadAgreement, notify } = useDemo()
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (agreementId && agreement?.id !== agreementId) void loadAgreement(agreementId)
  }, [agreementId, agreement?.id, loadAgreement])
  const entries = decisions.map(toEntry)
  const pending = entries.filter((e) => e.pending).length

  async function download() {
    if (!agreementId) return
    setBusy(true)
    try {
      const res = await api.exportCounterProposal(agreementId)
      notify(`Downloaded ${res.fileName}`)
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    if (!agreementId) return
    setBusy(true)
    try {
      const res = await api.completeAgreement(agreementId)
      notify(`Agreement confirmed · ${res.precedentsSaved} accepted term${res.precedentsSaved === 1 ? '' : 's'} saved as precedent`)
      await loadAgreement(agreementId)
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Confirm failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="wrap py-10 sm:py-14">
      <Link to={`/review/${agreementId}`} className="inline-flex min-h-11 items-center gap-2 text-sm font-bold text-muted hover:text-text">
        <ArrowLeft aria-hidden className="size-4" /> Back to review
      </Link>
      <BlurFade>
        <p className="eyebrow mt-4">Step 3 · Export</p>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-4xl sm:text-5xl">Counter-proposal</h1>
            <p className="mt-2 text-muted">Word file with tracked changes and one comment per decision.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary" onClick={download} disabled={busy || decisions.length === 0}>
              {busy ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Download aria-hidden className="size-4" />}
              Download .docx
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={confirm}
              disabled={busy || decisions.length === 0 || pending > 0 || agreement?.status === 'executed'}
              title={pending > 0 ? 'Resolve every pending item first' : undefined}
            >
              <BadgeCheck aria-hidden className="size-4" />
              {agreement?.status === 'executed' ? 'Agreement confirmed' : 'Confirm agreement'}
            </button>
            {agreement?.finalDocumentKey && (
              <a href={api.sourceUrl(agreement.finalDocumentKey)} className="btn btn-ghost">
                <FileText aria-hidden className="size-4" /> Download final document
              </a>
            )}
          </div>
        </div>
      </BlurFade>

      {decisions.length === 0 ? (
        <div className="panel mt-8 p-8 text-center">
          <p className="text-muted">Nothing to export yet.</p>
          <Link to="/upload" className="btn btn-primary mt-4">Triage a redline</Link>
        </div>
      ) : (
        <>
          {pending > 0 && (
            <p role="status" className="mt-6 flex items-start gap-2 rounded-2xl border border-butter/50 bg-butter/10 px-4 py-3 text-sm">
              <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-butter" />
              {pending} item{pending > 1 ? 's are' : ' is'} still pending. They export with the site’s tracked change left as received, plus a comment.
            </p>
          )}

          <article
            aria-label="Counter-proposal preview"
            className="mt-6 rounded-[6px] bg-cream p-5 text-ink shadow-[0_30px_80px_-30px_var(--magenta)] sm:p-10"
          >
            <header className="border-b border-ink/15 pb-5">
              <p className="text-xs font-bold tracking-[0.16em] text-ink/70 uppercase">{SPONSOR.name} · Protocol {SPONSOR.protocol}</p>
              <h2 className="mt-2 text-2xl text-ink sm:text-3xl">Clinical Trial Agreement · Sponsor counter-proposal</h2>
              <p className="mt-1 text-sm text-ink/70">Site {agreement?.siteNumber}, {agreement?.siteName}{agreement?.fileName ? ` · responding to ${agreement.fileName}` : ''}</p>
            </header>
            <ol className="mt-6 flex flex-col gap-6">
              {entries.map(({ d, counter, comment, pending: isPending }) => (
                <li key={d.id} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_240px]">
                  <div>
                    <p className="font-bold">{d.section}</p>
                    <p className="mt-1 leading-relaxed">
                      {counter !== null && counter !== d.revised ? (
                        <>
                          {d.revised && <del className="text-ink/60 decoration-red decoration-2">{d.revised}</del>}{' '}
                          {counter ? (
                            <ins className="text-blue underline decoration-blue decoration-2 underline-offset-4">{counter}</ins>
                          ) : (
                            <span className="text-sm text-ink/60 italic">(sponsor deletes the inserted text)</span>
                          )}
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
