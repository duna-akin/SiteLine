import { timeAgo } from '@/lib/format'
import { approvers, ownerLabel } from '@/mocks/playbook'
import type { Agreement, EscalationQueueItem, InboundEmail } from '@/types'

/** Where an agreement opens: its decision list once triaged, otherwise its row on Sites. */
export const agreementPath = (a: Pick<Agreement, 'id' | 'fileName'>) => (a.fileName ? `/review/${a.id}` : `/sites?site=${encodeURIComponent(a.id)}`)

/** A site in the portfolio whose redline Siteline hasn't triaged yet. */
export const notTriaged = (a: Agreement) => a.changes === 0

/** Inbound emails, newest first. */
export const byArrival = (emails: InboundEmail[]) => [...emails].sort((a, b) => b.receivedAt.localeCompare(a.receivedAt))

/** Where an escalation's question stands: "Legal · Tuna was texted 3 h ago". */
export function whoLine(item: EscalationQueueItem, now: number) {
  const d = item.decision
  const first = approvers[d.owner].name.split(' ')[0]
  const a = d.approval
  const status = a.state === 'calling' ? `${first} is being called` : a.state === 'sent' ? `${first} was texted ${timeAgo(a.sentAt, now)}` : `${first} isn’t texted yet`
  return `${ownerLabel[d.owner]} · ${status}`
}
