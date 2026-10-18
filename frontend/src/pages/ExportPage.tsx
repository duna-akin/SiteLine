import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, BadgeCheck, Download, FileText, LoaderCircle, RotateCw, TriangleAlert } from 'lucide-react'

import * as api from '@/api'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { cn } from '@/lib/utils'
import { SPONSOR, approvers, replyMeaning } from '@/mocks/playbook'
import { effectiveOutcome, isConfirmed, isWaiting } from '@/state/decision'
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
  const who = `the ${approvers[d.owner].title.toLowerCase()}`
  const hold = d.counterText ?? d.original
  const note = d.override ? ` Override: ${d.override.reason}` : ''
  if (outcome === 'accept') return { d, counter: null, comment: `Accepted under ${d.ruleId}.${note}`, pending: false }
  if (outcome === 'counter') {
    return { d, counter: hold, comment: `${d.counterText != null ? 'Playbook fallback' : 'Standard held'} (${d.ruleId}).${note}`, pending: false }
  }
  if (outcome === 'escalate') {
    if (d.approval.state !== 'answered') return { d, counter: null, comment: `Pending approval from ${who}.${note}`, pending: true }
    const r = d.approval.reply
    const counter = r === 1 ? null : r === 2 ? (d.fallbackText ?? hold) : hold
    return { d, counter, comment: `${who[0].toUpperCase()}${who.slice(1)} replied ${r} (${replyMeaning[r].toLowerCase()}).${note}`, pending: false }
  }
  return { d, counter: null, comment: 'Held for contract manager review. Override it to accept, counter or escalate before sending.', pending: true }
}

export function ExportPage() {
  const { agreementId } = useParams()
  const { decisions, agreement, loading, loadError, loadAgreement, notify } = useDemo()
  const [busy, setBusy] = useState(false)
  const current = agreement?.id === agreementId
  useEffect(() => {
    if (agreementId && agreement?.id !== agreementId) void loadAgreement(agreementId)
  }, [agreementId, agreement?.id, loadAgreement])

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

  const back = (
    <Link to={`/review/${agreementId}`} className="link"><ArrowLeft aria-hidden className="size-4" /> Back to review</Link>
  )

  if (loadError && !loading) {
    return (
      <div className="wrap pb-12">
        {back}
        <div className="tile mx-auto mt-6 max-w-xl text-center" role="alert">
          <h1 className="text-[26px]">Couldn’t load this agreement</h1>
          <p className="mt-3 text-muted">{loadError}</p>
          <button type="button" className="btn btn-primary mt-5" onClick={() => agreementId && void loadAgreement(agreementId)}>
            <RotateCw aria-hidden className="size-4" /> Try again
          </button>
        </div>
      </div>
    )
  }

  // Until this agreement has loaded, the store may still hold the previous one: show nothing of it.
  if (loading || !current) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading the counter-proposal…
      </div>
    )
  }

  const entries = decisions.map(toEntry)
  const pending = entries.filter((e) => e.pending).length
  const unconfirmed = decisions.filter((d) => !isWaiting(d) && !isConfirmed(d)).length
  const executed = agreement?.status === 'executed'

  return (
    <div className="wrap pb-12">
      {back}
      <section className="hello pt-2 pb-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="eyebrow">Export · Site {agreement?.siteNumber}</span>
            <h1>Counter-proposal</h1>
            <p>Word file with tracked changes and one comment per decision.</p>
            {unconfirmed > 0 && (
              <p role="status" className="!text-sm font-medium !text-elevated">
                {unconfirmed} suggestion{unconfirmed === 1 ? '' : 's'} not yet confirmed by a person.{' '}
                <Link to={`/review/${agreementId}`} className="text-accent hover:underline">Confirm them in review</Link> before exporting.
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2.5">
            <button type="button" className="btn btn-primary" onClick={download} disabled={busy || decisions.length === 0 || unconfirmed > 0}>
              {busy ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Download aria-hidden className="size-4" />}
              Download .docx
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={confirm}
              disabled={busy || decisions.length === 0 || pending > 0 || unconfirmed > 0 || executed}
              title={pending > 0 ? 'Resolve every pending item first' : unconfirmed > 0 ? 'Confirm every suggestion first' : undefined}
            >
              <BadgeCheck aria-hidden className="size-4" />
              {executed ? 'Agreement confirmed' : 'Confirm agreement'}
            </button>
            {agreement?.finalDocumentKey && (
              <a href={api.sourceUrl(agreement.finalDocumentKey)} className="btn btn-secondary">
                <FileText aria-hidden className="size-4" /> Download final document
              </a>
            )}
          </div>
        </div>
      </section>

      {decisions.length === 0 ? (
        <div className="tile p-8 text-center">
          <p className="text-muted">Nothing to export yet.</p>
          <Link to="/upload" className="btn btn-primary mt-4">Triage a redline</Link>
        </div>
      ) : (
        <>
          {pending > 0 && (
            <p role="status" className="mb-6 flex items-start gap-2 rounded-[6px] border border-line border-l-[3px] border-l-elevated bg-surface px-4 py-3 text-sm">
              <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-elevated" />
              {pending} item{pending > 1 ? 's are' : ' is'} still pending. They export with the site’s tracked change left as received, plus a comment.
            </p>
          )}

          <article aria-label="Counter-proposal preview" className="tile mx-auto max-w-[960px] p-5 shadow-[0_1px_3px_rgba(33,33,33,.06)] sm:px-14 sm:py-12">
            <header className="border-b border-ink-2 pb-5 text-center">
              <p className="eyebrow">{SPONSOR.name} · Protocol {SPONSOR.protocol}</p>
              <h2 className="mt-3 text-[22px] sm:text-[26px]">Clinical Trial Agreement</h2>
              <p className="mt-1 font-serif text-[15px] text-ink-2 italic">Sponsor counter-proposal</p>
              <p className="mt-2 text-sm text-muted">Site {agreement?.siteNumber}, {agreement?.siteName}{agreement?.fileName ? ` · responding to ${agreement.fileName}` : ''}</p>
            </header>
            <ol className="mt-8 flex flex-col divide-y divide-line">
              {entries.map(({ d, counter, comment, pending: isPending }) => (
                <li key={d.id} className="grid gap-4 py-5 first:pt-0 last:pb-0 md:grid-cols-[minmax(0,1fr)_260px] md:gap-8">
                  <div>
                    <p className="font-serif text-[16px] font-semibold">{d.section}</p>
                    <p className="mt-1.5 font-serif text-[15.5px] leading-relaxed text-ink-2">
                      {counter !== null && counter !== d.revised ? (
                        <>
                          {d.revised && <del className="text-high decoration-high">{d.revised}</del>}{' '}
                          {counter ? (
                            <ins className="text-accent underline decoration-accent underline-offset-[3px]">{counter}</ins>
                          ) : (
                            <span className="font-sans text-sm text-muted italic">(sponsor deletes the inserted text)</span>
                          )}
                        </>
                      ) : (
                        <span>{d.revised || <del className="text-high decoration-high">{d.original}</del>}</span>
                      )}
                    </p>
                  </div>
                  <aside className={cn('border-l-2 py-0.5 pl-3 text-[13.5px]', isPending ? 'border-elevated' : 'border-line-strong')}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="eyebrow !text-[10.5px]">Siteline comment</span>
                      <OutcomeBadge outcome={effectiveOutcome(d)} size="sm" />
                    </div>
                    <p className="mt-1 text-ink-2">{comment}</p>
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
