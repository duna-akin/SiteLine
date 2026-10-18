import { Link } from 'react-router-dom'

import { usd, usdK } from '@/components/siteline/priority-style'
import { agreementPath, notTriaged } from '@/lib/sites'
import { cn } from '@/lib/utils'
import type { Agreement } from '@/types'

const TARGET_DAYS = 90

const unknownFigures = (a: Agreement) => a.priority?.moneyAtRiskPerWeek == null

function barColour(a: Agreement) {
  if (notTriaged(a) || unknownFigures(a)) return 'var(--muted)'
  const stuck = a.stuckClauses.length
  return stuck >= 3 ? 'var(--stuck-many)' : stuck > 0 ? 'var(--stuck-some)' : 'var(--stuck-none)'
}

function rowLabel(a: Agreement) {
  const money = a.priority?.moneyAtRiskPerWeek
  const stuck = a.stuckClauses.length
  return `Site ${a.siteNumber}, ${a.siteName}, ${a.daysOpen} days open, ${stuck} stuck clause${stuck === 1 ? '' : 's'}, ${
    notTriaged(a) ? 'not triaged yet' : money != null ? `about ${usd(money)} a week at risk` : 'no priority figures yet'
  }`
}

function Row({ a, maxMoney }: { a: Agreement; maxMoney: number }) {
  const money = a.priority?.moneyAtRiskPerWeek
  const stuck = a.stuckClauses.length
  return (
    <>
      <span className="n">{a.siteNumber}</span>
      <span className="nm">{a.siteName}</span>
      <span className="bar" aria-hidden>
        <span style={{ width: `${money != null && maxMoney ? (money / maxMoney) * 100 : 0}%`, background: barColour(a) }} />
      </span>
      <span className={cn('d', a.daysOpen > TARGET_DAYS && 'over')}>{a.daysOpen} d</span>
      <span className="m">
        {notTriaged(a) ? (
          <span className="pill s-info">Not triaged</span>
        ) : money != null ? (
          <b>{usdK(money)}/wk</b>
        ) : (
          <span className="pill s-neutral">Unknown</span>
        )}
      </span>
      <span className="s">{stuck ? `${stuck} stuck` : '—'}</span>
    </>
  )
}

/**
 * One row per open site, in the order given: bar length = money at risk per week (relative to
 * the largest shown), colour = stuck clauses; days open is text, marked past the 90-day target.
 * With `onSelect` rows are buttons; otherwise links.
 */
export function SiteBars({ sites, selected, onSelect, label = 'Open sites' }: {
  sites: Agreement[]
  selected?: string | null
  onSelect?: (id: string) => void
  label?: string
}) {
  const maxMoney = Math.max(0, ...sites.map((s) => s.priority?.moneyAtRiskPerWeek ?? 0))
  return (
    <ol className="site-bars" aria-label={label}>
      {sites.map((a) => (
        <li key={a.id}>
          {onSelect ? (
            <button
              type="button"
              aria-pressed={selected === a.id}
              aria-label={rowLabel(a)}
              className={cn(selected === a.id && 'sel')}
              onClick={() => onSelect(a.id)}
            >
              <Row a={a} maxMoney={maxMoney} />
            </button>
          ) : (
            <Link to={agreementPath(a)} aria-label={rowLabel(a)}>
              <Row a={a} maxMoney={maxMoney} />
            </Link>
          )}
        </li>
      ))}
    </ol>
  )
}

export function SiteBarsLegend() {
  return (
    <ul className="legend" aria-label="Legend">
      <li>Bar = money at risk per week</li>
      <li><i style={{ background: 'var(--stuck-none)' }} />No stuck clauses</li>
      <li><i style={{ background: 'var(--stuck-some)' }} />1–2 stuck</li>
      <li><i style={{ background: 'var(--stuck-many)' }} />3+ stuck</li>
      <li><i style={{ background: 'var(--muted)' }} />No figures yet</li>
      <li><b className="font-semibold text-elevated">Days in gold</b> = over the {TARGET_DAYS}-day target</li>
    </ul>
  )
}
