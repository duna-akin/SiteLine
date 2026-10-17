import { PhoneCall, PhoneForwarded } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { SponsorChip } from '@/components/siteline/SponsorChip'
import { TextBubble } from '@/components/siteline/TextBubble'
import { useNow } from '@/hooks/useNow'
import { formatClock, formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'
import { approvers, ownerLabel, replyMeaning } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { ApprovalReply, Decision } from '@/types'

const REPLIES: ApprovalReply[] = [1, 2, 3]
const initials = (name: string) => name.split(' ').map((p) => p[0]).join('')

function Thread({ d }: { d: Decision }) {
  const { reply } = useDemo()
  const person = approvers[d.owner]
  const a = d.approval
  const answered = a.state === 'answered' ? a : null

  return (
    <div className="flex flex-col">
      <div className="phone-top"><b>Siteline</b> · Text to {person.name.split(' ')[0]}{a.state !== 'none' && ` · ${formatClock(a.sentAt)}`}</div>
      <div className="flex min-h-56 flex-col" aria-live="polite">
        {a.state !== 'none' && a.text && <TextBubble text={a.text} />}
        {a.state === 'none' && <p className="mt-6 text-center text-sm text-muted">No text sent yet.</p>}
        {answered && (
          <>
            <div className="reply">{answered.reply}</div>
            <div className="bubble">{`Recorded C${String(d.index).padStart(2, '0')}: ${replyMeaning[answered.reply]}. Thank you.`}</div>
          </>
        )}
      </div>
      <div className="mt-4 flex gap-2" role="group" aria-label={`Reply as ${person.name}`}>
        {REPLIES.map((r) => (
          <button
            key={r}
            type="button"
            disabled={a.state !== 'sent'}
            onClick={() => void reply(d.id, r, 'imessage')}
            title={replyMeaning[r]}
            aria-label={`Reply ${r}: ${replyMeaning[r]}`}
            className="btn btn-soft flex-1 p-0 font-display text-lg"
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  )
}

function CallScreen({ d }: { d: Decision }) {
  const { reply, agreement } = useDemo()
  const now = useNow(500)
  const person = approvers[d.owner]
  const startedAt = d.approval.state === 'calling' ? d.approval.callStartedAt : now
  const connected = now - startedAt > 2500

  return (
    <div className="flex min-h-80 flex-col items-center px-2 pt-6 pb-2 text-center">
      <span aria-hidden className="flex size-16 items-center justify-center rounded-full bg-peach font-display text-xl font-semibold text-tangerine-ink shadow-[0_0_0_6px_var(--butter)]">
        {initials(person.name)}
      </span>
      <p className="mt-4 font-display text-lg font-semibold">{person.name}</p>
      <p className="text-xs text-muted tabular" aria-live="polite">
        {connected ? `Siteline voice agent · ${formatDuration(now - startedAt - 2500)}` : 'Calling…'}
      </p>
      {connected && (
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bubble mt-4 text-left text-[13px]">
          “Hi {person.name.split(' ')[0]}, Siteline here with one Site {agreement?.siteNumber} escalation: {d.section}. Press 1 to approve, 2 to counter with the fallback, 3 to reject.”
        </motion.p>
      )}
      <div className="mt-auto grid w-full grid-cols-3 gap-3 pt-5" role="group" aria-label="Keypad">
        {REPLIES.map((r) => (
          <button
            key={r}
            type="button"
            disabled={!connected}
            onClick={() => void reply(d.id, r, 'voice')}
            aria-label={`Press ${r}: ${replyMeaning[r]}`}
            className="mx-auto flex size-14 items-center justify-center rounded-full bg-bg font-display text-2xl font-semibold shadow-[inset_0_0_0_2px_var(--line)] transition-transform active:scale-95 disabled:opacity-40"
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ApproverPhone({ escalations }: { escalations: Decision[] }) {
  const { activeEscalationId, focusEscalation, callNow, noReplyMs, integrations } = useDemo()
  const active = escalations.find((d) => d.id === activeEscalationId) ?? escalations[0]
  const now = useNow(1000, active?.approval.state === 'sent')

  if (!active) return null
  const calling = active.approval.state === 'calling'

  return (
    <section aria-labelledby="phone-heading" className="tile bg-peach">
      <div className="tile-head">
        <h2 id="phone-heading">Approver phone</h2>
        <SponsorChip sponsor="Photon" label="Photon 2.0" />
      </div>
      <div className="mt-2 mb-4 flex flex-wrap gap-1.5" role="tablist" aria-label="Escalations">
        {escalations.map((d) => (
          <button
            key={d.id}
            type="button"
            role="tab"
            aria-selected={d.id === active.id}
            onClick={() => focusEscalation(d.id)}
            className={cn(
              'inline-flex min-h-11 items-center gap-1.5 rounded-full px-3 text-xs font-extrabold transition-colors',
              d.id === active.id ? 'bg-ink text-[var(--on-ink)]' : 'bg-card text-muted hover:text-ink',
            )}
          >
            <span
              aria-hidden
              className="size-2 rounded-full"
              style={{ background: d.approval.state === 'answered' ? 'var(--radar-ok)' : d.approval.state === 'calling' ? 'var(--radar-warn)' : 'var(--radar-bad)' }}
            />
            {d.section.split(' ')[0]} · {ownerLabel[d.owner]}
            <span className="sr-only">{d.approval.state === 'answered' ? ' (answered)' : d.approval.state === 'calling' ? ' (calling)' : ' (awaiting reply)'}</span>
          </button>
        ))}
      </div>

      <div className="phone">
        <AnimatePresence mode="wait">
          <motion.div
            key={`${active.id}-${calling ? 'call' : 'msg'}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
          >
            {calling ? <CallScreen d={active} /> : <Thread d={active} />}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="mt-4 text-center text-sm">
        {active.approval.state === 'sent' && (
          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className="tabular text-tangerine-ink">
              <PhoneForwarded aria-hidden className="mr-1 inline size-4" />
              Voice call in {formatDuration(active.approval.sentAt + noReplyMs - now)} if no reply
            </span>
            <button type="button" className="btn btn-soft btn-sm" onClick={() => void callNow(active.id)}>
              <PhoneCall aria-hidden className="size-3.5" /> Simulate no reply
            </button>
          </div>
        )}
        {active.approval.state === 'calling' && (
          <p className="text-tangerine-ink">
            The text got no reply, so the voice agent is calling
            {active.approval.callDelivery && active.approval.callDelivery !== 'simulated' ? ' the real phone through Photon.' : ' (on-screen call).'}
          </p>
        )}
        {active.approval.state === 'answered' && <p className="font-extrabold text-mint-ink">Answered. The card updated live.</p>}
        <p className="mt-2 text-xs text-muted">
          {active.approval.state !== 'none' && active.approval.delivery === 'photon'
            ? `Live: this text went to ${approvers[active.owner].name}’s phone by Photon. Their reply updates here; these buttons are the backup.`
            : integrations?.photon
              ? 'On-screen phone: this approver has no real phone number configured.'
              : 'On-screen phone: Photon isn’t configured on the server, so texts stay on this screen.'}
        </p>
      </div>
    </section>
  )
}
