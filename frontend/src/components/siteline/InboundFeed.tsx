import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, LoaderCircle, Mail } from 'lucide-react'

import * as api from '@/api'
import { priorityPill, priorityShort, usdK } from '@/components/siteline/priority-style'
import { arrivedLabel } from '@/lib/format'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'
import type { Agreement, InboundEmail } from '@/types'

function Item({ e, agreement, busy, onTriage }: { e: InboundEmail; agreement?: Agreement; busy: boolean; onTriage: () => void }) {
  const done = e.triaged
  const prio = agreement?.priority
  return (
    <li id={`email-${e.id}`} className="scroll-mt-24">
      <span className="blob" style={done ? { color: 'var(--ok)' } : undefined}>
        {done ? <Check aria-hidden className="size-[18px]" /> : <Mail aria-hidden className="size-[18px]" />}
        <span className="sr-only">{done ? 'Triaged' : 'Waiting for triage'}</span>
      </span>
      <div className="min-w-0">
        <div className="name">
          {done && agreement ? <Link to={`/review/${agreement.id}`} className="text-ink hover:text-accent hover:underline">{e.subject}</Link> : e.subject}
        </div>
        <div className="meta">
          {done && agreement
            ? `Site ${agreement.siteNumber} · ${agreement.changes} changes · ${arrivedLabel(e.receivedAt)}`
            : `${e.siteName} · ${e.from} · ${arrivedLabel(e.receivedAt)}`}
        </div>
      </div>
      <div className="act">
        {!done && (
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={onTriage}>
            {busy && <LoaderCircle aria-hidden className="size-4 animate-spin" />} Triage now
          </button>
        )}
        {done && prio && (
          <span className={`pill ${priorityPill[prio.level]}`}>
            {priorityShort[prio.level]}{prio.moneyAtRiskPerWeek != null && ` · ${usdK(prio.moneyAtRiskPerWeek)}/wk`}
          </span>
        )}
        {done && agreement && agreement.changes > 0 && (
          <span className="pill s-neutral">{agreement.confirmed ?? 0} of {agreement.changes} confirmed</span>
        )}
      </div>
    </li>
  )
}

/** Inbound redlines: waiting ones get a Triage button, triaged ones show their site's priority and progress. */
export function InboundFeed({ emails }: { emails: InboundEmail[] }) {
  const { notify } = useDemo()
  const { agreements, refresh } = useDesk()
  const [busy, setBusy] = useState<string | null>(null)
  const byId = new Map((agreements ?? []).map((a) => [a.id, a]))

  async function triage(e: InboundEmail) {
    setBusy(e.id)
    try {
      const { agreement } = await api.triageEmail(e.id)
      notify(`Triaged ${e.attachment}: ${agreement.changes} changes`)
      refresh()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Triage failed')
    } finally {
      setBusy(null)
    }
  }

  return (
    <ul className="feed">
      {emails.map((e) => (
        <Item key={e.id} e={e} agreement={e.agreementId ? byId.get(e.agreementId) : undefined} busy={busy !== null} onTriage={() => void triage(e)} />
      ))}
    </ul>
  )
}
