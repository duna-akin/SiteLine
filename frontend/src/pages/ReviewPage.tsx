import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { FileDown, FileText, LoaderCircle, Timer } from 'lucide-react'

import { ApproverPhone } from '@/components/siteline/ApproverPhone'
import { DecisionCard } from '@/components/siteline/DecisionCard'
import { outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { BlurFade } from '@/components/ui/blur-fade'
import { Confetti, type ConfettiRef } from '@/components/ui/confetti'
import { NumberTicker } from '@/components/ui/number-ticker'
import { token } from '@/lib/tokens'
import { cn } from '@/lib/utils'
import { outcomeLabel, outcomeOrder } from '@/mocks/playbook'
import { effectiveOutcome } from '@/state/decision'
import type { Decision } from '@/types'
import { useDemo } from '@/state/demo'
import type { Outcome } from '@/types'

const effectiveOutcomeIs = (d: Decision, o: Outcome) => effectiveOutcome(d) === o

export function ReviewPage() {
  const { agreementId } = useParams()
  const { decisions, agreement, loading, loadError, loadAgreement } = useDemo()
  const [filter, setFilter] = useState<Outcome | 'all'>('all')
  const confetti = useRef<ConfettiRef>(null)
  const celebrated = useRef(false)

  useEffect(() => {
    if (agreementId && agreement?.id !== agreementId) void loadAgreement(agreementId)
  }, [agreementId, agreement?.id, loadAgreement])

  const escalations = useMemo(() => decisions.filter((d) => effectiveOutcomeIs(d, 'escalate')), [decisions])
  const answered = escalations.filter((d) => d.approval.state === 'answered').length
  const needsHuman = decisions.filter((d) => (d.outcome === 'human_review' || d.outcome === 'novel') && !d.override).length
  const viaPhoton = escalations.some((d) => d.approval.state !== 'none' && d.approval.delivery === 'photon')
  const shown = filter === 'all' ? decisions : decisions.filter((d) => effectiveOutcome(d) === filter)

  useEffect(() => {
    if (escalations.length === 0 || answered < escalations.length || celebrated.current) return
    celebrated.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    void confetti.current?.fire({
      particleCount: 140,
      spread: 90,
      origin: { y: 0.3 },
      colors: ['--yellow', '--magenta', '--mint', '--butter', '--blue-l'].map(token),
    })
  }, [answered, escalations.length])

  if (loading || (agreementId && !agreement && !loadError)) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading decisions…
      </div>
    )
  }

  if (!agreement || decisions.length === 0) {
    return (
      <div className="wrap py-16">
        <BlurFade className="panel mx-auto max-w-2xl p-8 text-center">
          <FileText aria-hidden className="mx-auto size-10 text-butter" />
          <h1 className="mt-4 text-4xl">No decision list yet</h1>
          <p className="mt-3 text-muted">
            {agreement
              ? `Site ${agreement.siteNumber} (${agreement.siteName}) is in the portfolio, but its redline hasn’t been triaged in Siteline.`
              : 'Upload a redline to triage it. The Site 07 demo file takes a few seconds.'}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to="/upload" className="btn btn-primary">Upload redline</Link>
            <Link to="/" className="btn btn-ghost">Back to inbox</Link>
          </div>
        </BlurFade>
      </div>
    )
  }

  return (
    <div className="wrap py-10 sm:py-14">
      <Confetti ref={confetti} manualstart className="pointer-events-none fixed inset-0 z-50 size-full" />

      <BlurFade>
        <p className="eyebrow">Step 2 · Review</p>
        <div className="mt-3 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl sm:text-5xl">
              Site {agreement.siteNumber} <span className="text-muted">·</span> <span className="text-yellow">{agreement.siteName}</span>
            </h1>
            <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
              {agreement.fileName && <span><FileText aria-hidden className="mr-1 inline size-4" />{agreement.fileName}</span>}
              {agreement.triageSeconds !== undefined && (
                <span className="tabular"><Timer aria-hidden className="mr-1 inline size-4" />Triaged in {agreement.triageSeconds} s</span>
              )}
              <span>{decisions.length} changes</span>
              {agreement.parser && <span>Parsed {agreement.parser === 'daytona' ? 'in a Daytona sandbox' : 'locally'}</span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to={`/review/${agreement.id}/export`} className="btn btn-primary">
              <FileDown aria-hidden className="size-4" /> Export counter-proposal
            </Link>
          </div>
        </div>
      </BlurFade>

      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" role="group" aria-label="Filter by outcome">
        <button
          type="button"
          aria-pressed={filter === 'all'}
          onClick={() => setFilter('all')}
          className={cn('panel min-h-11 p-4 text-left transition-colors', filter === 'all' && 'border-yellow')}
        >
          <span className="eyebrow">All</span>
          <span className="mt-1 block text-3xl font-bold tabular">
            <NumberTicker value={decisions.length} className="text-text" />
          </span>
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
              className="panel min-h-11 p-4 text-left transition-colors"
              style={filter === o ? { borderColor: outcomeVar[o] } : undefined}
            >
              <span className="eyebrow flex items-center gap-1.5">
                <Icon aria-hidden className="size-3.5" style={{ color: outcomeVar[o] }} /> {outcomeLabel[o]}
              </span>
              <span className="mt-1 block text-3xl font-bold tabular">
                {n === 0 ? <span className="text-text">0</span> : <NumberTicker value={n} className="text-text" />}
              </span>
            </button>
          )
        })}
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted" aria-live="polite">
        <span><span className="font-bold text-text tabular">{answered}/{escalations.length}</span> escalations answered by phone{viaPhoton ? ' (live Photon texts)' : ''}</span>
        <span><span className="font-bold text-text tabular">{needsHuman}</span> need a human decision</span>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="order-2 flex flex-col gap-4 lg:order-1">
          {shown.length === 0 && <p className="panel p-6 text-muted">No changes with this outcome.</p>}
          {shown.map((d, i) => (
            <BlurFade key={d.id} delay={Math.min(i, 8) * 0.04} inView>
              <DecisionCard d={d} />
            </BlurFade>
          ))}
        </div>
        <aside className="order-1 lg:order-2">
          <div className="lg:sticky lg:top-24">
            <ApproverPhone escalations={escalations} />
          </div>
        </aside>
      </div>
    </div>
  )
}
