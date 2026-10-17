import { Link } from 'react-router-dom'

import { priorityPill, priorityShort, usd } from '@/components/siteline/priority-style'
import { useNow } from '@/hooks/useNow'
import { whoLine } from '@/lib/sites'
import { clauseLabel } from '@/mocks/playbook'
import type { EscalationQueueItem } from '@/types'

/** Ranked escalations, most money at risk first, then oldest question (the order the API returns). */
export function EscalationQueue({ items, start = 0 }: { items: EscalationQueueItem[]; start?: number }) {
  const now = useNow(60_000)
  return (
    <ol className="queue">
      {items.map((item, i) => {
        const d = item.decision
        const money = item.priority.moneyAtRiskPerWeek
        return (
          <li key={d.id}>
            <Link to={`/review/${item.agreementId}#change-${d.id}`} className="q">
              <span className="rank" aria-hidden>{start + i + 1}</span>
              <div className="min-w-0">
                <h3 className="truncate">{clauseLabel[d.clauseType]} · Site {item.siteNumber}</h3>
                <div className="who">{whoLine(item, now)}</div>
              </div>
              <div className="money">
                <b className="tabular">
                  {money != null ? <>{usd(money)}<small className="text-[13px]">/wk</small></> : '—'}
                </b>
                <span className={`pill ${priorityPill[item.priority.level]}`}>{priorityShort[item.priority.level]}</span>
              </div>
            </Link>
          </li>
        )
      })}
    </ol>
  )
}
