import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCheck, FileDown, FileText, LoaderCircle, RotateCw, Timer } from 'lucide-react'

import * as api from '@/api'
import { ContractDocument } from '@/components/siteline/ContractDocument'
import { PriorityBadge } from '@/components/siteline/PriorityBadge'
import { useHashScroll } from '@/hooks/useHashScroll'
import { effectiveOutcome, isConfirmed, isWaiting } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { DocParagraph } from '@/types'

function BackLink() {
  return <Link to="/sites" className="link"><ArrowLeft aria-hidden className="size-4" /> Sites</Link>
}

export function ReviewPage() {
  const { agreementId } = useParams()
  const { decisions, agreement, loading, loadError, loadAgreement, confirmAll } = useDemo()
  // The whole contract; null while loading or when none was stored for this agreement
  const [doc, setDoc] = useState<{ id: string; paragraphs: DocParagraph[] | null } | null>(null)
  const current = agreement?.id === agreementId

  useEffect(() => {
    if (agreementId && agreement?.id !== agreementId) void loadAgreement(agreementId)
  }, [agreementId, agreement?.id, loadAgreement])

  useEffect(() => {
    if (!agreementId) return
    let live = true
    api.getDocument(agreementId).then(
      (r) => live && setDoc({ id: agreementId, paragraphs: r.paragraphs }),
      () => live && setDoc({ id: agreementId, paragraphs: null }),
    )
    return () => {
      live = false
    }
  }, [agreementId])

  const escalations = decisions.filter((d) => effectiveOutcome(d) === 'escalate')
  const answered = escalations.filter((d) => d.approval.state === 'answered').length
  const needsHuman = decisions.filter((d) => (d.outcome === 'human_review' || d.outcome === 'novel') && !d.override).length
  const docReady = doc?.id === agreementId
  const confirmedCount = decisions.filter(isConfirmed).length
  const toConfirm = decisions.filter((d) => !isWaiting(d) && !isConfirmed(d))
  const bulk = toConfirm.filter((d) => !d.precedent).length

  useHashScroll(current && !loading && docReady && decisions.length > 0)

  if (loadError && !loading) {
    return (
      <div className="wrap pb-12">
        <BackLink />
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

  if (loading || !current || !docReady) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        <LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading the agreement…
      </div>
    )
  }

  if (!agreement || decisions.length === 0) {
    return (
      <div className="wrap pb-12">
        <BackLink />
        <div className="tile mx-auto mt-6 max-w-2xl text-center">
          <FileText aria-hidden className="mx-auto size-8 text-faint" />
          <h1 className="mt-4 text-[28px]">No decision list yet</h1>
          <p className="mt-3 text-muted">
            {agreement
              ? `Site ${agreement.siteNumber} (${agreement.siteName}) is in the portfolio, but its redline hasn’t been triaged in Siteline.`
              : 'Upload a redline to triage it. The Site 07 demo file takes a few seconds.'}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link to="/upload" className="btn btn-primary">Upload redline</Link>
            <Link to="/sites" className="btn btn-secondary">Back to sites</Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="wrap pb-12">
      <BackLink />

      <section className="hello pt-2 pb-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <span className="eyebrow">Agreement review · {decisions.length} changes</span>
            <h1>Site {agreement.siteNumber} · {agreement.siteName}</h1>
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 !text-sm">
              {agreement.fileName && <span><FileText aria-hidden className="mr-1 inline size-4" />{agreement.fileName}</span>}
              {agreement.triageSeconds !== undefined && (
                <span className="tabular"><Timer aria-hidden className="mr-1 inline size-4" />Triaged in {agreement.triageSeconds} s</span>
              )}
              {agreement.parser && <span>Parsed {agreement.parser === 'daytona' ? 'in a Daytona sandbox' : 'locally'}</span>}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button type="button" className="btn btn-secondary" disabled={bulk === 0} onClick={() => void confirmAll(agreement.id)}>
              <CheckCheck aria-hidden className="size-4" /> Confirm all suggested ({bulk})
            </button>
            {toConfirm.length > 0 ? (
              <span className="btn btn-primary" aria-disabled="true" title="Every suggestion needs a person’s confirmation first">
                <FileDown aria-hidden className="size-4" /> Export counter-proposal
              </span>
            ) : (
              <Link to={`/review/${agreement.id}/export`} className="btn btn-primary">
                <FileDown aria-hidden className="size-4" /> Export counter-proposal
              </Link>
            )}
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line pb-3 text-sm text-muted" aria-live="polite">
        {agreement.priority && <PriorityBadge priority={agreement.priority} />}
        {agreement.daysWaiting !== undefined && (
          <span>Redline waiting <span className="font-semibold text-ink tabular">{agreement.daysWaiting}</span> day{agreement.daysWaiting === 1 ? '' : 's'}</span>
        )}
        <span><span className="font-semibold text-ink tabular">{answered}/{escalations.length}</span> escalations answered</span>
        <span><span className="font-semibold text-ink tabular">{needsHuman}</span> need a human decision</span>
        <span>
          <span className="font-semibold text-ink tabular">{confirmedCount} of {decisions.length}</span> signed off
          {toConfirm.length > 0 && ` · ${toConfirm.length} to confirm before export`}
        </span>
      </div>

      <div className="mt-4">
        <ContractDocument key={agreement.id} paragraphs={doc?.paragraphs ?? null} decisions={decisions} />
      </div>
    </div>
  )
}
