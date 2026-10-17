import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, RotateCw } from 'lucide-react'

import { PriorityBadge } from '@/components/siteline/PriorityBadge'
import { byPriority, openSites, priorityPill, priorityShort, usd } from '@/components/siteline/priority-style'
import { RadarLegend, SiteRadar } from '@/components/siteline/SiteRadar'
import { agreementPath, notTriaged } from '@/lib/sites'
import { cn } from '@/lib/utils'
import { clauseLabel } from '@/mocks/playbook'
import { statusLabel } from '@/mocks/portfolio'
import { useDesk } from '@/state/desk'

const TARGET_DAYS = 90

function Stat({ value, label, tone }: { value: string; label: string; tone?: string }) {
  return (
    <div className="tile py-5">
      <p className={cn('font-display text-4xl font-semibold tabular', tone)}>{value}</p>
      <p className="mt-1 text-sm font-bold text-muted">{label}</p>
    </div>
  )
}

export function SitesPage() {
  const { agreements, error, refresh } = useDesk()
  const [params, setParams] = useSearchParams()

  if (error && !agreements) {
    return (
      <div className="wrap py-16">
        <div className="tile mx-auto max-w-xl text-center" role="alert">
          <h1 className="text-3xl">Can’t reach the Siteline API</h1>
          <p className="mt-3 text-muted">{error}</p>
          <button type="button" className="btn btn-orange mt-5" onClick={refresh}><RotateCw aria-hidden className="size-4" /> Try again</button>
        </div>
      </div>
    )
  }

  if (!agreements) {
    return (
      <div className="wrap pb-12" role="status" aria-label="Loading sites">
        <div className="hello pt-7 pb-6"><div className="h-12 w-1/3 animate-pulse rounded-2xl bg-card" /></div>
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
      <section className="hello pt-7 pb-6">
        <h1>Sites</h1>
        <p>
          Every site still negotiating. On the radar, farther out means open longer, bigger means more money at risk per week of delay,
          and colour shows how many clauses are stuck. Past the dashed ring is over the {TARGET_DAYS}-day start-up target.
        </p>
      </section>

      <div className="grid grid-cols-2 gap-[18px] lg:grid-cols-4">
        <Stat value={String(sites.length)} label="open sites" />
        <Stat value={String(overTarget)} label={`over ${TARGET_DAYS} days`} tone={overTarget ? 'text-tangerine-ink' : undefined} />
        <Stat value={String(blocked)} label="blocked by stuck clauses" />
        <Stat value={`≈${usd(atRisk)}`} label="at risk per week" tone="text-rose-ink" />
      </div>

      <div className="mt-[18px] grid grid-cols-1 gap-[18px] min-[1081px]:grid-cols-12">
        <section aria-labelledby="radar-h" className="tile min-[1081px]:col-span-7">
          <div className="tile-head"><h2 id="radar-h">Open sites <span className="badge tabular">{sites.length}</span></h2></div>
          <p className="tile-sub">Choose a blip to see that site.</p>
          <SiteRadar sites={sites} selected={selectedId} onSelect={select} className="mx-auto max-w-[520px]" />
          <RadarLegend />
        </section>

        <aside aria-live="polite" aria-labelledby="pick-h" className="tile bg-butter min-[1081px]:col-span-5">
          {pick ? (
            <>
              <p className="eyebrow">Selected site</p>
              <h2 id="pick-h" className="mt-1 text-3xl">Site {pick.siteNumber}</h2>
              <p className="font-extrabold">{pick.siteName}</p>
              <p className="text-sm text-muted">{[pick.city, statusLabel[pick.status]].filter(Boolean).join(' · ')}</p>
              <div className="mt-4 rounded-[20px] bg-card p-4">
                <PriorityBadge priority={pick.priority} detail />
              </div>
              <p className="mt-4 font-display text-5xl font-semibold tabular">
                {pick.daysOpen}<span className="font-body text-xl font-bold text-muted"> days open</span>
              </p>
              <p className={cn('text-sm', pick.daysOpen > TARGET_DAYS ? 'font-extrabold text-tangerine-ink' : 'text-muted')}>
                {pick.daysOpen > TARGET_DAYS ? `${pick.daysOpen - TARGET_DAYS} days over target` : `${TARGET_DAYS - pick.daysOpen} days left before target`}
              </p>
              <h3 className="mt-5 font-body text-sm font-extrabold">Stuck clauses</h3>
              {pick.stuckClauses.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {pick.stuckClauses.map((c) => <li key={c} className="pill p-rose">{clauseLabel[c]}</li>)}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-muted">Nothing blocking activation.</p>
              )}
              {pick.fileName ? (
                <Link to={`/review/${pick.id}`} className="btn btn-orange mt-5">Open Site {pick.siteNumber} review <ArrowRight aria-hidden className="size-4" /></Link>
              ) : (
                <p className="mt-5 rounded-[20px] bg-card px-4 py-3 text-sm text-muted">
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
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-muted">
                <tr className="border-b-2 border-line">
                  <th scope="col" className="px-3 py-3 font-extrabold">Site</th>
                  <th scope="col" className="px-3 py-3 font-extrabold">Status</th>
                  <th scope="col" className="px-3 py-3 text-right font-extrabold">At risk / week</th>
                  <th scope="col" className="px-3 py-3 text-right font-extrabold">Days open</th>
                  <th scope="col" className="px-3 py-3 font-extrabold">Stuck clauses</th>
                </tr>
              </thead>
              <tbody>
                {byPriority(agreements).map((s) => (
                  <tr key={s.id} className={cn('border-b border-line last:border-0', s.id === selectedId && 'bg-bg')}>
                    <td className="px-3 py-3">
                      <Link to={agreementPath(s)} className="font-extrabold hover:underline">Site {s.siteNumber}</Link>{' '}
                      <span className="text-muted">{s.siteName}</span>
                    </td>
                    <td className="px-3 py-3">{statusLabel[s.status]}</td>
                    <td className="px-3 py-3 text-right tabular">
                      <span className="inline-flex items-center gap-2">
                        {s.priority?.moneyAtRiskPerWeek != null ? `≈${usd(s.priority.moneyAtRiskPerWeek)}` : '—'}
                        {s.priority && <span className={`pill ${priorityPill[s.priority.level]}`}>{priorityShort[s.priority.level]}</span>}
                      </span>
                    </td>
                    <td className={cn('px-3 py-3 text-right tabular', s.daysOpen > TARGET_DAYS && 'font-extrabold text-tangerine-ink')}>{s.daysOpen}</td>
                    <td className="px-3 py-3 text-muted">{s.stuckClauses.map((c) => clauseLabel[c]).join(', ') || '—'}</td>
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
