import type { KeyboardEvent } from 'react'

import { usd } from '@/components/siteline/priority-style'
import { notTriaged } from '@/lib/sites'
import { cn } from '@/lib/utils'
import type { Agreement } from '@/types'

const C = 160
const MAX_DAYS = 180
const TARGET_DAYS = 90
const RINGS = [30, 60, 90, 120, 180]
const START_DEG = -60 // no blip sits on the ring-label axis

/** Distance from the centre: 18 + min(days, 180) / 180 × 132 (mockup formula). */
const radiusFor = (days: number) => 18 + (Math.min(Math.max(days, 0), MAX_DAYS) / MAX_DAYS) * 132

const unknownFigures = (a: Agreement) => a.priority?.moneyAtRiskPerWeek == null

function blip(a: Agreement, maxMoney: number) {
  if (notTriaged(a)) return { r: 6, fill: 'var(--surface)', stroke: 'var(--accent)', dashed: true }
  if (unknownFigures(a)) return { r: 6, fill: 'var(--surface)', stroke: 'var(--muted)', dashed: true }
  const money = a.priority!.moneyAtRiskPerWeek!
  const fill = a.stuckClauses.length >= 3 ? 'var(--radar-bad)' : a.stuckClauses.length > 0 ? 'var(--radar-warn)' : 'var(--radar-ok)'
  return { r: 4 + 12 * Math.sqrt(maxMoney ? money / maxMoney : 0), fill, stroke: 'var(--surface)', dashed: false }
}

function blipLabel(a: Agreement) {
  const money = a.priority?.moneyAtRiskPerWeek
  const stuck = a.stuckClauses.length
  return `Site ${a.siteNumber}, ${a.daysOpen} days open, ${stuck} stuck clause${stuck === 1 ? '' : 's'}, ${
    notTriaged(a) ? 'not triaged yet' : money != null ? `about ${usd(money)} a week at risk` : 'no priority figures yet'
  }`
}

/**
 * Open sites: farther out = open longer, bigger = more money at risk, colour = stuck clauses.
 * With `onSelect` each blip is a button; otherwise the radar is a picture and a list carries the data.
 */
export function SiteRadar({ sites, selected, onSelect, className }: {
  sites: Agreement[]
  selected?: string | null
  onSelect?: (id: string) => void
  className?: string
}) {
  const maxMoney = Math.max(0, ...sites.map((s) => s.priority?.moneyAtRiskPerWeek ?? 0))
  const interactive = Boolean(onSelect)
  const key = (id: string) => (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelect?.(id)
    }
  }

  return (
    <svg
      viewBox="0 0 320 320"
      className={cn('radar block h-auto w-full', className)}
      role={interactive ? 'group' : 'img'}
      aria-label={
        interactive
          ? 'Radar of open sites. Choose a site to see its details.'
          : 'Radar of open sites. Farther out means open longer. Bigger means more money at risk. A ranked list follows.'
      }
    >
      <circle cx={C} cy={C} r={150} fill="var(--subtle)" stroke="var(--line)" />
      <g fill="none" stroke="var(--line)" strokeWidth={1}>
        {RINGS.filter((d) => d !== TARGET_DAYS).map((d) => <circle key={d} cx={C} cy={C} r={radiusFor(d)} />)}
      </g>
      <circle cx={C} cy={C} r={radiusFor(TARGET_DAYS)} fill="none" stroke="var(--elevated)" strokeWidth={1} strokeDasharray="4 4" />
      <g fontFamily="var(--sans)" fontSize={10} fontWeight={500} fill="var(--muted)" aria-hidden>
        {RINGS.map((d) => (
          <text key={d} x={C + 3} y={Math.max(9, C - radiusFor(d) - 3)} fill={d === TARGET_DAYS ? 'var(--elevated)' : undefined}>
            {d} d
          </text>
        ))}
      </g>
      <g fontFamily="var(--sans)" fontSize={11.5} fontWeight={500} fill="var(--ink-2)">
        {sites.map((s, i) => {
          const angle = ((START_DEG + (i * 360) / Math.max(sites.length, 1)) * Math.PI) / 180
          const dist = radiusFor(s.daysOpen)
          const x = C + dist * Math.cos(angle)
          const y = C + dist * Math.sin(angle)
          const b = blip(s, maxMoney)
          const right = x + b.r + 22 < 318
          const isSel = selected === s.id
          const body = (
            <>
              {interactive && <circle cx={x} cy={y} r={Math.max(b.r, 14)} fill="transparent" />}
              {isSel && <circle cx={x} cy={y} r={b.r + 5} fill="none" stroke="var(--ink)" strokeWidth={1.5} />}
              <circle
                cx={x}
                cy={y}
                r={b.r}
                fill={b.fill}
                stroke={b.stroke}
                strokeWidth={b.dashed ? 1.25 : 1.5}
                strokeDasharray={b.dashed ? '3 2' : undefined}
              />
              <text x={right ? x + b.r + 4 : x - b.r - 4} y={y + 5} textAnchor={right ? 'start' : 'end'} aria-hidden>
                {s.siteNumber}
              </text>
            </>
          )
          return interactive ? (
            <g
              key={s.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSel}
              aria-label={blipLabel(s)}
              className="cursor-pointer"
              onClick={() => onSelect?.(s.id)}
              onKeyDown={key(s.id)}
            >
              {body}
            </g>
          ) : (
            <g key={s.id}>{body}</g>
          )
        })}
      </g>
    </svg>
  )
}

export function RadarLegend() {
  return (
    <ul className="legend" aria-label="Legend">
      <li>Farther out = open longer</li>
      <li>Bigger = more money at risk</li>
      <li><i style={{ background: 'var(--radar-ok)' }} />No stuck clauses</li>
      <li><i style={{ background: 'var(--radar-warn)' }} />1–2 stuck</li>
      <li><i style={{ background: 'var(--radar-bad)' }} />3+ stuck</li>
      <li><i style={{ border: '1.5px dashed var(--muted)' }} />No figures yet</li>
      <li><i style={{ border: '1.5px dashed var(--accent)' }} />Not triaged</li>
      <li><i style={{ border: '1.5px dashed var(--elevated)', borderRadius: 0, height: 0, width: 14 }} />90-day target</li>
    </ul>
  )
}
