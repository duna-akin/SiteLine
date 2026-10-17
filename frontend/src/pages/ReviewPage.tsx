import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCheck, FileDown, FileText, LoaderCircle, RotateCw, Timer } from 'lucide-react'

import { ApproverPhone } from '@/components/siteline/ApproverPhone'
import { DecisionCard } from '@/components/siteline/DecisionCard'
import { PriorityBadge } from '@/components/siteline/PriorityBadge'
import { outcomeBg, outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { Confetti, type ConfettiRef } from '@/components/ui/confetti'
import { useHashScroll } from '@/hooks/useHashScroll'
import { token } from '@/lib/tokens'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import { effectiveOutcome, isConfirmed, isWaiting } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { Outcome } from '@/types'

function BackLink() {
  return <Link to="/sites" className="link"><ArrowLeft aria-hidden className="size-4" /> Sites</Link>
}

export function ReviewPage() {
  const { agreementId } = useParams()
  const { decisions, agreement, loading, loadError, loadAgreement, confirmAll } = useDemo()
  const [filter, setFilter] = useState<Outcome | 'all'>('all')
  const confetti = useRef<ConfettiRef>(null)
  const celebrated = useRef(false)
  const current = agreement?.id === agreementId

  useEffect(() => {
    if (agreementId && agreement?.id !== agreementId) void loadAgreement(agreementId)
  }, [agreementId, agreement?.id, loadAgreement])

  const escalations = useMemo(() => decisions.filter((d) => effectiveOutcome(d) === 'escalate'), [decisions])
  const answered = escalations.filter((d) => d.approval.state === 'answered').length
  const needsHuman = decisions.filter((d) => (d.outcome === 'human_review' || d.outcome === 'novel') && !d.override).length
  const viaPhoton = escalations.some((d) => d.approval.state !== 'none' && d.approval.delivery === 'photon')
  const shown = filter === 'all' ? decisions : decisions.filter((d) => effectiveOutcome(d) === filter)
  const confirmedCount = decisions.filter(isConfirmed).length
  const toConfirm = decisions.filter((d) => !isWaiting(d) && !isConfirmed(d))
  const bulk = toConfirm.filter((d) => !d.precedent).length

  useHashScroll(current && !loading && decisions.length > 0)

  useEffect(() => {
    if (escalations.length === 0 || answered < escalations.length || celebrated.current) return
    celebrated.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    void confetti.current?.fire({
      particleCount: 140,
      spread: 90,
      origin: { y: 0.3 },
      colors: ['--tangerine', '--marker', '--blue', '--radar-ok', '--rose-ink'].map(token),
    })
  }, [answered, escalations.length])

  if (loadError && !loading) {
    return (
      <div className="wrap pb-12">
        <BackLink />
        <div className="tile mx-auto mt-6 max-w-xl text-center" role="alert">
          <h1 className="text-3xl">Couldn’t load this agreement</h1>
          <p className="mt-3 text-muted">{loadError}</p>
          <button type="button" className="btn btn-orange mt-5" onClick={() => agreementId && void loadAgreement(agreementId)}>
            <RotateCw aria-hidden className="size-4" /> Try again
          </button>
        </div>
      </div>
    )
  }

  if (loading || !current) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading decisions…
      </div>
    )
  }

  if (!agreement || decisions.length === 0) {
    return (
      <div className="wrap pb-12">
        <BackLink />
        <div className="tile mx-auto mt-6 max-w-2xl text-center">
          <FileText aria-hidden className="mx-auto size-10 text-tangerine-ink" />
          <h1 className="mt-4 text-4xl">No decision list yet</h1>
          <p className="mt-3 text-muted">
            {agreement
              ? `Site ${agreement.siteNumber} (${agreement.siteName}) is in the portfolio, but its redline hasn’t been triaged in Siteline.`
              : 'Upload a redline to triage it. The Site 07 demo file takes a few seconds.'}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to="/upload" className="btn btn-orange">Upload redline</Link>
            <Link to="/sites" className="btn btn-soft">Back to sites</Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="wrap pb-12">
      <Confetti ref={confetti} manualstart className="pointer-events-none fixed inset-0 z-50 size-full" />
      <BackLink />

      <section className="hello pt-2 pb-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <h1>Site {agreement.siteNumber} · {agreement.siteName}</h1>
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 !text-sm">
              {agreement.fileName && <span><FileText aria-hidden className="mr-1 inline size-4" />{agreement.fileName}</span>}
              {agreement.triageSeconds !== undefined && (
                <span className="tabular"><Timer aria-hidden className="mr-1 inline size-4" />Triaged in {agreement.triageSeconds} s</span>
              )}
              <span>{decisions.length} changes</span>
              {agreement.parser && <span>Parsed {agreement.parser === 'daytona' ? 'in a Daytona sandbox' : 'locally'}</span>}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button type="button" className="btn btn-soft" disabled={bulk === 0} onClick={() => void confirmAll(agreement.id)}>
              <CheckCheck aria-hidden className="size-4" /> Confirm all suggested ({bulk})
            </button>
            {toConfirm.length > 0 ? (
              <span className="btn btn-orange" aria-disabled="true" title="Every suggestion needs a person’s confirmation first">
                <FileDown aria-hidden className="size-4" /> Export counter-proposal
              </span>
            ) : (
              <Link to={`/review/${agreement.id}/export`} className="btn btn-orange">
                <FileDown aria-hidden className="size-4" /> Export counter-proposal
              </Link>
            )}
          </div>
        </div>
      </section>

      {agreement.priority && (
        <div className="tile mb-[18px] bg-butter py-5">
          <PriorityBadge priority={agreement.priority} detail className="max-w-3xl" />
          {agreement.daysWaiting !== undefined && (
            <p className="mt-1 text-xs text-muted">
              Redline waiting {agreement.daysWaiting} day{agreement.daysWaiting === 1 ? '' : 's'}.{' '}
              <Link to="/playbook#priority" className="font-extrabold text-blue hover:underline">Priority settings</Link>
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6" role="group" aria-label="Filter by outcome">
        <button
          type="button"
          aria-pressed={filter === 'all'}
          onClick={() => setFilter('all')}
          className={cn('panel min-h-11 p-4 text-left transition-shadow', filter === 'all' && 'shadow-[inset_0_0_0_3px_var(--ink)]')}
        >
          <span className="eyebrow">All</span>
          <span className="mt-1 block font-display text-3xl font-semibold tabular">{decisions.length}</span>
        </button>
        {outcomeOrder.map((o) => {
          const Icon = outcomeIcon[o]
          const n = decisions.filter((d) => effectiveOutcome(d) === o).length
          return (
            <button
              key={o}
              type="button"
              aria-pressed={filter === o}
              onClick={() => setFilter(filter === o ? 'all' : o)}
              className="min-h-11 rounded-[20px] p-4 text-left transition-shadow"
              style={{ background: outcomeBg[o], color: outcomeVar[o], boxShadow: filter === o ? `inset 0 0 0 3px ${outcomeVar[o]}` : undefined }}
            >
              <span className="flex items-center gap-1.5 text-[13px] font-extrabold"><Icon aria-hidden className="size-3.5" /> {outcomeLabel[o]}</span>
              <span className="mt-1 block font-display text-3xl font-semibold text-ink tabular">{n}</span>
            </button>
          )
        })}
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted" aria-live="polite">
        <span><span className="font-extrabold text-ink tabular">{answered}/{escalations.length}</span> escalations answered by phone{viaPhoton ? ' (live Photon texts)' : ''}</span>
        <span><span className="font-extrabold text-ink tabular">{needsHuman}</span> need a human decision</span>
        <span>
          <span className="font-extrabold text-ink tabular">{confirmedCount} of {decisions.length}</span> confirmed by a person
          {toConfirm.length > 0 && ` · ${toConfirm.length} suggestion${toConfirm.length === 1 ? '' : 's'} to confirm before export`}
        </span>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-[18px] lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="order-2 flex flex-col gap-4 lg:order-1">
          {shown.length === 0 && <p className="tile text-muted">No changes with this outcome.</p>}
          {shown.map((d) => <DecisionCard key={d.id} d={d} />)}
        </div>
        <aside className="order-1 lg:order-2">
          <div className="lg:sticky lg:top-6">
            <ApproverPhone escalations={escalations} />
          </div>
        </aside>
      </div>
    </div>
  )
}
