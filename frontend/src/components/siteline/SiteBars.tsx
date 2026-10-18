import { Link } from 'react-router-dom'

import { usd, usdK } from '@/components/siteline/priority-style'
import { agreementPath, notTriaged } from '@/lib/sites'
import { cn } from '@/lib/utils'
import type { Agreement } from '@/types'

const MAX_DAYS = 180
const TARGET_DAYS = 90

const unknownFigures = (a: Agreement) => a.priority?.moneyAtRiskPerWeek == null

function barColour(a: Agreement) {
  if (notTriaged(a) || unknownFigures(a)) return 'var(--muted)'
  const stuck = a.stuckClauses.length
  return stuck >= 3 ? 'var(--radar-bad)' : stuck > 0 ? 'var(--radar-warn)' : 'var(--radar-ok)'
}

function rowLabel(a: Agreement) {
  const money = a.priority?.moneyAtRiskPerWeek
  const stuck = a.stuckClauses.length
  return `Site ${a.siteNumber}, ${a.siteName}, ${a.daysOpen} days open, ${stuck} stuck clause${stuck === 1 ? '' : 's'}, ${
    notTriaged(a) ? 'not triaged yet' : money != null ? `about ${usd(money)} a week at risk` : 'no priority figures yet'
  }`
}

function Row({ a }: { a: Agreement }) {
  const money = a.priority?.moneyAtRiskPerWeek
  const stuck = a.stuckClauses.length
  return (
    <>
      <span className="n">{a.siteNumber}</span>
      <span className="nm">{a.siteName}</span>
      <span className="bar" aria-hidden>
        <span style={{ width: `${(Math.min(Math.max(a.daysOpen, 0), MAX_DAYS) / MAX_DAYS) * 100}%`, background: barColour(a) }} />
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
 * One row per open site, in the order given: bar length = days open (dashed line at the
 * 90-day target), colour = stuck clauses. With `onSelect` rows are buttons; otherwise links.
 */
export function SiteBars({ sites, selected, onSelect, label = 'Open sites' }: {
  sites: Agreement[]
  selected?: string | null
  onSelect?: (id: string) => void
  label?: string
}) {
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
              <Row a={a} />
            </button>
          ) : (
            <Link to={agreementPath(a)} aria-label={rowLabel(a)}>
              <Row a={a} />
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
      <li>Bar = days open</li>
      <li><i style={{ background: 'var(--radar-ok)' }} />No stuck clauses</li>
      <li><i style={{ background: 'var(--radar-warn)' }} />1–2 stuck</li>
      <li><i style={{ background: 'var(--radar-bad)' }} />3+ stuck</li>
      <li><i style={{ background: 'var(--muted)' }} />No figures yet</li>
      <li><i style={{ borderLeft: '1.5px dashed var(--elevated)', borderRadius: 0, height: 12, width: 0 }} />{TARGET_DAYS}-day target</li>
    </ul>
  )
}
