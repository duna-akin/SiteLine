import { timeAgo } from '@/lib/format'
import { ownerLabel } from '@/mocks/playbook'
import type { Agreement, EscalationQueueItem, InboundEmail } from '@/types'

/** Where an agreement opens: its decision list once triaged, otherwise its row on Sites. */
export const agreementPath = (a: Pick<Agreement, 'id' | 'fileName'>) => (a.fileName ? `/review/${a.id}` : `/sites?site=${encodeURIComponent(a.id)}`)

/** A site in the portfolio whose redline Siteline hasn't triaged yet. */
export const notTriaged = (a: Agreement) => a.changes === 0

/** Inbound emails, newest first. */
export const byArrival = (emails: InboundEmail[]) => [...emails].sort((a, b) => b.receivedAt.localeCompare(a.receivedAt))

/** Where an escalation's question stands: "Legal · texted 3 h ago". */
export function whoLine(item: EscalationQueueItem, now: number) {
  const d = item.decision
  const a = d.approval
  const status = a.state === 'calling' ? 'calling the approver' : a.state === 'sent' ? `texted ${timeAgo(a.sentAt, now)}` : 'not texted yet'
  return `${ownerLabel[d.owner]} · ${status}`
}

/** Matches the backend's priority line in an escalation text ("Site 07 = high priority, ≈$11,200/week at risk …"). */
export const PRIORITY_LINE = /^Site \S+ = .*priority/

export const hasPriorityLine = (text: string) => text.split('\n').some((l) => PRIORITY_LINE.test(l))
