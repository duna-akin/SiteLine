import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, LoaderCircle, RotateCw } from 'lucide-react'

import { PriorityBadge } from '@/components/siteline/PriorityBadge'
import { byPriority, openSites, priorityPill, priorityShort, usd } from '@/components/siteline/priority-style'
import { RadarLegend, SiteRadar } from '@/components/siteline/SiteRadar'
import { RedlineDocument } from '@/components/siteline/RedlineDocument'
import { agreementPath, notTriaged } from '@/lib/sites'
import { cn } from '@/lib/utils'
import { clauseLabel } from '@/mocks/playbook'
import { statusLabel } from '@/mocks/portfolio'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'

const TARGET_DAYS = 90

function Stat({ value, label, tone }: { value: string; label: string; tone?: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone}>{value}</dd>
    </div>
  )
}

/** The selected site's redline, loaded into the same store the Review page uses so overrides stay in step. */
function SiteRedline({ id }: { id: string }) {
  const { agreement, decisions, loading, loadError, loadAgreement } = useDemo()
  const current = agreement?.id === id

  useEffect(() => {
    if (agreement?.id !== id) void loadAgreement(id)
  }, [id, agreement?.id, loadAgreement])

  const open = decisions.filter((d) => (d.outcome === 'human_review' || d.outcome === 'novel') && !d.override).length

  return (
    <section aria-labelledby="redline-h" className="mt-5">
      <h3 id="redline-h" className="eyebrow font-sans">
        Redline{current && !loading && open > 0 && <span className="ml-2 normal-case text-high">{open} need a reviewer</span>}
      </h3>
      {loadError && !loading ? (
        <p className="mt-2 text-sm text-high" role="alert">
          Couldn’t load the redline: {loadError}{' '}
          <button type="button" className="link min-h-0 text-sm" onClick={() => void loadAgreement(id)}>Try again</button>
        </p>
      ) : loading || !current ? (
        <p className="mt-2 text-sm text-muted" role="status">
          <LoaderCircle aria-hidden className="mr-1.5 inline size-4 animate-spin" /> Loading the redline…
        </p>
      ) : decisions.length === 0 ? (
        <p className="empty mt-2">No tracked changes found in this redline.</p>
      ) : (
        <div tabIndex={0} aria-label={`Site redline, ${decisions.length} changes`} className="well mt-2 max-h-[28rem] overflow-y-auto p-4">
          <RedlineDocument decisions={decisions} />
        </div>
      )}
    </section>
  )
}

export function SitesPage() {
  const { agreements, error, refresh } = useDesk()
  const [params, setParams] = useSearchParams()

  if (error && !agreements) {
    return (
      <div className="wrap py-16">
        <div className="tile mx-auto max-w-xl text-center" role="alert">
          <h1 className="text-[26px]">Can’t reach the Siteline API</h1>
          <p className="mt-3 text-muted">{error}</p>
          <button type="button" className="btn btn-primary mt-5" onClick={refresh}><RotateCw aria-hidden className="size-4" /> Try again</button>
        </div>
      </div>
    )
  }

  if (!agreements) {
    return (
      <div className="wrap pb-12" role="status" aria-label="Loading sites">
        <div className="hello pt-9 pb-6"><div className="h-12 w-1/3 animate-pulse rounded-[6px] bg-sunken" /></div>
        <div className="tile h-96 animate-pulse" />
      </div>
    )
  }

  const sites = openSites(agreements)
  const ranked = byPriority(sites)
  const selectedId = params.get('site') ?? ranked[0]?.id ?? null
  const pick = agreements.find((a) => a.id === selectedId)
  const select = (id: string) => setParams({ site: id }, { replace: true })
  const overTarget = sites.filter((s) => s.daysOpen > TARGET_DAYS).length
  const blocked = sites.filter((s) => s.stuckClauses.length > 0).length
  const atRisk = sites.reduce((n, s) => n + (s.priority?.moneyAtRiskPerWeek ?? 0), 0)

  return (
    <div className="wrap pb-12">
      <section className="hello pt-9">
        <span className="eyebrow">Portfolio</span>
        <h1>Sites</h1>
        <p>
          Every site still negotiating. On the radar, farther out means open longer, bigger means more money at risk per week of delay,
          and colour shows how many clauses are stuck. Past the dashed ring is over the {TARGET_DAYS}-day start-up target.
        </p>
        <dl className="stats">
          <Stat value={String(sites.length)} label="Open sites" />
          <Stat value={String(overTarget)} label={`Over ${TARGET_DAYS} days`} tone={overTarget ? '!text-elevated' : undefined} />
          <Stat value={String(blocked)} label="Blocked by stuck clauses" />
          <Stat value={`≈${usd(atRisk)}`} label="At risk per week" tone="!text-high" />
        </dl>
      </section>

      <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
        <section aria-labelledby="radar-h" className="tile min-[1081px]:col-span-7">
          <div className="tile-head"><h2 id="radar-h">Open sites <span className="badge tabular">{sites.length}</span></h2></div>
          <p className="tile-sub">Choose a blip to see that site.</p>
          <SiteRadar sites={sites} selected={selectedId} onSelect={select} className="mx-auto max-w-[520px]" />
          <RadarLegend />
        </section>

        <aside aria-live="polite" aria-labelledby="pick-h" className="tile min-[1081px]:col-span-5">
          {pick ? (
            <>
              <p className="eyebrow">Selected site</p>
              <h2 id="pick-h" className="mt-1 text-[26px]">Site {pick.siteNumber}</h2>
              <p className="font-medium">{pick.siteName}</p>
              <p className="text-sm text-muted">{[pick.city, statusLabel[pick.status]].filter(Boolean).join(' · ')}</p>
              <div className="well mt-4 p-4">
                <PriorityBadge priority={pick.priority} detail />
              </div>
              <p className="mt-5 font-serif text-4xl font-medium tabular">
                {pick.daysOpen}<span className="font-sans text-base font-normal text-muted"> days open</span>
              </p>
              <p className={cn('text-sm', pick.daysOpen > TARGET_DAYS ? 'font-medium text-elevated' : 'text-muted')}>
                {pick.daysOpen > TARGET_DAYS ? `${pick.daysOpen - TARGET_DAYS} days over target` : `${TARGET_DAYS - pick.daysOpen} days left before target`}
              </p>
              <h3 className="eyebrow mt-5 font-sans">Stuck clauses</h3>
              {pick.stuckClauses.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {pick.stuckClauses.map((c) => <li key={c} className="pill s-high">{clauseLabel[c]}</li>)}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-muted">Nothing blocking activation.</p>
              )}
              {pick.fileName ? (
                <>
                  <SiteRedline id={pick.id} />
                  <Link to={`/review/${pick.id}`} className="btn btn-primary mt-5">Open Site {pick.siteNumber} review <ArrowRight aria-hidden className="size-4" /></Link>
                </>
              ) : (
                <p className="empty mt-5">
                  {notTriaged(pick) ? 'This site’s redline hasn’t been triaged in Siteline yet.' : 'Tracked from the study plan; its redline wasn’t triaged in Siteline.'}
                </p>
              )}
            </>
          ) : (
            <p id="pick-h" className="text-muted">No open sites.</p>
          )}
        </aside>

        <section aria-labelledby="table-h" className="tile min-[1081px]:col-span-12">
          <div className="tile-head"><h2 id="table-h">All agreements <span className="badge tabular">{agreements.length}</span></h2></div>
          <p className="tile-sub">Waiting on us first, by money at risk, then days open.</p>
          <div className="overflow-x-auto rounded-[6px] border border-line">
            <table className="data-table min-w-[640px]">
              <thead>
                <tr>
                  <th scope="col">Site</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="!text-right">At risk / week</th>
                  <th scope="col" className="!text-right">Days open</th>
                  <th scope="col">Stuck clauses</th>
                </tr>
              </thead>
              <tbody>
                {byPriority(agreements).map((s) => (
                  <tr key={s.id} className={cn(s.id === selectedId && '[&>td]:bg-subtle')} aria-current={s.id === selectedId ? 'true' : undefined}>
                    <td>
                      <Link to={agreementPath(s)} className="font-semibold text-ink hover:text-accent hover:underline">Site {s.siteNumber}</Link>{' '}
                      <span className="text-muted">{s.siteName}</span>
                    </td>
                    <td>{statusLabel[s.status]}</td>
                    <td className="text-right tabular">
                      <span className="inline-flex items-center gap-2">
                        {s.priority?.moneyAtRiskPerWeek != null ? `≈${usd(s.priority.moneyAtRiskPerWeek)}` : '—'}
                        {s.priority && <span className={`pill ${priorityPill[s.priority.level]}`}>{priorityShort[s.priority.level]}</span>}
                      </span>
                    </td>
                    <td className={cn('text-right tabular', s.daysOpen > TARGET_DAYS && 'font-semibold text-elevated')}>{s.daysOpen}</td>
                    <td className="text-muted">{s.stuckClauses.map((c) => clauseLabel[c]).join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  )
}
