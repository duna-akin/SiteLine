import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'

import * as api from '@/api'
import { PriorityBadge } from '@/components/siteline/PriorityBadge'
import { byPriority, priorityLabel, usd } from '@/components/siteline/priority-style'
import { BlurFade } from '@/components/ui/blur-fade'
import { cn } from '@/lib/utils'
import { clauseLabel } from '@/mocks/playbook'
import { statusLabel } from '@/mocks/portfolio'
import type { Agreement } from '@/types'

const SIZE = 400
const C = SIZE / 2
const MAX_DAYS = 180
const R = 170
const RINGS = [30, 60, 90, 120, 180]
const TARGET_DAYS = 90

/** Inner offset keeps brand-new sites from piling up on the center point. */
const INNER = 26
const radiusFor = (days: number) => INNER + (Math.min(days, MAX_DAYS) / MAX_DAYS) * (R - INNER)

/** Blip area grows with money at risk per week; sites with no figures get the smallest blip. */
function blipSize(a: Agreement, maxRisk: number) {
  const risk = a.priority?.moneyAtRiskPerWeek ?? 0
  return Math.round(12 + 22 * Math.sqrt(maxRisk ? risk / maxRisk : 0))
}

function blipColor(a: Agreement) {
  if (a.stuckClauses.length >= 3) return 'var(--red)'
  if (a.stuckClauses.length > 0) return 'var(--butter)'
  return 'var(--mint)'
}

export function PortfolioPage() {
  const [sites, setSites] = useState<Agreement[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    void api.getPortfolio().then((s) => {
      setSites(s)
      setSelected(s.slice().sort((a, b) => b.daysOpen - a.daysOpen)[0]?.id ?? null)
    })
  }, [])

  const pick = sites.find((s) => s.id === selected)
  const blocked = sites.filter((s) => s.stuckClauses.length > 0)
  const overTarget = sites.filter((s) => s.daysOpen > TARGET_DAYS)
  const maxRisk = Math.max(0, ...sites.map((s) => s.priority?.moneyAtRiskPerWeek ?? 0))
  const atRisk = sites.reduce((n, s) => n + (s.status === 'executed' ? 0 : s.priority?.moneyAtRiskPerWeek ?? 0), 0)

  return (
    <div className="wrap py-10 sm:py-14">
      <BlurFade>
        <p className="eyebrow">Study start-up lead</p>
        <h1 className="mt-3 max-w-3xl text-4xl sm:text-6xl">
          Portfolio <span className="text-yellow">radar</span>
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted">
          Distance from the center is days open. Size is money at risk per week of delay. Color shows how many clauses are stuck. Anything past the dashed ring is over the {TARGET_DAYS}-day start-up target.
        </p>
      </BlurFade>

      <div className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <span><span className="text-2xl font-bold tabular">{sites.length}</span> <span className="text-muted">open sites</span></span>
        <span><span className="text-2xl font-bold tabular text-butter">{overTarget.length}</span> <span className="text-muted">over {TARGET_DAYS} days</span></span>
        <span><span className="text-2xl font-bold tabular">{blocked.length}</span> <span className="text-muted">blocked by stuck clauses</span></span>
        <span><span className="text-2xl font-bold tabular text-red">≈{usd(atRisk)}</span> <span className="text-muted">at risk per week across open sites</span></span>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <section aria-labelledby="radar-heading" className="panel relative overflow-hidden p-4 sm:p-6">
          <h2 id="radar-heading" className="sr-only">Radar of open sites</h2>
          <div className="relative mx-auto aspect-square w-full max-w-[560px]">
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="absolute inset-0 size-full" role="img" aria-label="Radar chart of days open per site. A table follows with the same data.">
              <defs>
                <radialGradient id="radar-bg">
                  <stop offset="0%" stopColor="var(--space-2)" />
                  <stop offset="100%" stopColor="var(--space)" />
                </radialGradient>
                <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="var(--mint)" stopOpacity="0" />
                  <stop offset="100%" stopColor="var(--mint)" stopOpacity="0.35" />
                </linearGradient>
              </defs>
              <circle cx={C} cy={C} r={R} fill="url(#radar-bg)" />
              {RINGS.map((d) => (
                <g key={d}>
                  <circle
                    cx={C}
                    cy={C}
                    r={radiusFor(d)}
                    fill="none"
                    stroke={d === TARGET_DAYS ? 'var(--yellow)' : 'var(--line)'}
                    strokeDasharray={d === TARGET_DAYS ? '6 6' : undefined}
                    strokeWidth={d === TARGET_DAYS ? 1.5 : 1}
                  />
                  <text x={C + 4} y={C - radiusFor(d) - 4} fill="var(--muted)" fontSize="10" fontFamily="var(--sans)">
                    {d}d{d === TARGET_DAYS ? ' target' : ''}
                  </text>
                </g>
              ))}
              <line x1={C - R} y1={C} x2={C + R} y2={C} stroke="var(--line)" />
              <line x1={C} y1={C - R} x2={C} y2={C + R} stroke="var(--line)" />
              <g className="origin-center motion-safe:animate-[spin_6s_linear_infinite]" style={{ transformOrigin: `${C}px ${C}px` }}>
                <path d={`M ${C} ${C} L ${C + R} ${C} A ${R} ${R} 0 0 0 ${C + R * Math.cos(-Math.PI / 5)} ${C + R * Math.sin(-Math.PI / 5)} Z`} fill="url(#sweep)" />
              </g>
            </svg>

            {sites.map((s, i) => {
              const angle = (i / sites.length) * Math.PI * 2 - Math.PI / 2
              const r = radiusFor(s.daysOpen)
              const x = ((C + r * Math.cos(angle)) / SIZE) * 100
              const y = ((C + r * Math.sin(angle)) / SIZE) * 100
              const size = blipSize(s, maxRisk)
              const isSel = s.id === selected
              const risk = s.priority?.moneyAtRiskPerWeek
              return (
                <motion.button
                  key={s.id}
                  type="button"
                  onClick={() => setSelected(s.id)}
                  aria-pressed={isSel}
                  aria-label={`Site ${s.siteNumber}, ${s.daysOpen} days open, ${s.stuckClauses.length} stuck clauses, ${risk != null ? `about ${usd(risk)} per week at risk` : 'priority unknown'}`}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.05 * i, type: 'spring', stiffness: 260, damping: 20 }}
                  className="absolute flex size-11 -translate-x-1/2 -translate-y-1/2 items-center justify-center"
                  style={{ left: `${x}%`, top: `${y}%` }}
                >
                  <span
                    aria-hidden
                    className={cn('rounded-full transition-shadow duration-200', isSel && 'ring-2 ring-yellow ring-offset-2 ring-offset-space')}
                    style={{ width: size, height: size, background: blipColor(s), boxShadow: `0 0 18px ${blipColor(s)}` }}
                  />
                  <span aria-hidden className="absolute top-full -mt-1 text-[11px] font-bold text-text">{s.siteNumber}</span>
                </motion.button>
              )
            })}
          </div>
          <ul className="mt-4 flex flex-wrap justify-center gap-4 text-xs text-muted" aria-label="Legend">
            <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-mint" /> No stuck clauses</li>
            <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-butter" /> 1–2 stuck</li>
            <li className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-red" /> 3+ stuck</li>
            <li className="flex items-center gap-1.5"><span className="h-0 w-4 border-t border-dashed border-yellow" /> {TARGET_DAYS}-day target</li>
            <li className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-muted" /><span className="size-3 rounded-full bg-muted" /> Bigger = more money at risk</li>
          </ul>
        </section>

        <aside className="panel h-fit p-5" aria-live="polite">
          {pick ? (
            <>
              <p className="eyebrow">Selected site</p>
              <h2 className="mt-2 text-3xl">Site {pick.siteNumber}</h2>
              <p className="font-bold">{pick.siteName}</p>
              <p className="text-sm text-muted">{pick.city} · {statusLabel[pick.status]}</p>
              <PriorityBadge priority={pick.priority} detail className="mt-3" />
              <p className="mt-4 text-5xl font-bold tabular">
                {pick.daysOpen}<span className="text-2xl text-muted"> days open</span>
              </p>
              <p className={cn('text-sm', pick.daysOpen > TARGET_DAYS ? 'font-bold text-butter' : 'text-muted')}>
                {pick.daysOpen > TARGET_DAYS ? `${pick.daysOpen - TARGET_DAYS} days over target` : `${TARGET_DAYS - pick.daysOpen} days left before target`}
              </p>
              <h3 className="mt-5 font-sans text-sm font-bold">Stuck clauses</h3>
              {pick.stuckClauses.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {pick.stuckClauses.map((c) => (
                    <li key={c} className="rounded-full border border-red/60 bg-red/10 px-2.5 py-0.5 text-xs font-bold">{clauseLabel[c]}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-muted">Nothing blocking activation.</p>
              )}
              {pick.id === 'site-07' && <Link to="/review/site-07" className="btn btn-primary mt-5">Open Site 07 review</Link>}
            </>
          ) : (
            <p className="text-muted">Loading sites…</p>
          )}
        </aside>
      </div>

      <section aria-labelledby="table-heading" className="mt-8">
        <h2 id="table-heading" className="text-2xl">All open sites</h2>
        <div className="panel mt-3 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="text-muted">
              <tr className="border-b border-line">
                <th scope="col" className="px-4 py-3 font-bold">Site</th>
                <th scope="col" className="px-4 py-3 font-bold">Status</th>
                <th scope="col" className="px-4 py-3 text-right font-bold">At risk / week</th>
                <th scope="col" className="px-4 py-3 text-right font-bold">Days open</th>
                <th scope="col" className="px-4 py-3 font-bold">Stuck clauses</th>
              </tr>
            </thead>
            <tbody>
              {byPriority(sites).map((s) => (
                <tr key={s.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3"><span className="font-bold">Site {s.siteNumber}</span> <span className="text-muted">{s.siteName}</span></td>
                  <td className="px-4 py-3">{statusLabel[s.status]}</td>
                  <td className="px-4 py-3 text-right tabular">
                    {s.priority?.moneyAtRiskPerWeek != null ? `≈${usd(s.priority.moneyAtRiskPerWeek)}` : '—'}
                    {s.priority && <span className="block text-xs text-muted">{priorityLabel[s.priority.level]}</span>}
                  </td>
                  <td className={cn('px-4 py-3 text-right tabular', s.daysOpen > TARGET_DAYS && 'font-bold text-butter')}>{s.daysOpen}</td>
                  <td className="px-4 py-3 text-muted">{s.stuckClauses.map((c) => clauseLabel[c]).join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
