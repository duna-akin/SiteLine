import { PhoneCall, PhoneForwarded } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { ownerIcon } from '@/components/siteline/owner-style'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { TextBubble } from '@/components/siteline/TextBubble'
import { useNow } from '@/hooks/useNow'
import { formatClock, formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'
import { approvers, ownerLabel, replyMeaning } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { ApprovalReply, Decision } from '@/types'

const REPLIES: ApprovalReply[] = [1, 2, 3]

function Thread({ d }: { d: Decision }) {
  const { reply } = useDemo()
  const person = approvers[d.owner]
  const a = d.approval
  const answered = a.state === 'answered' ? a : null

  return (
    <div className="flex flex-col">
      <div className="phone-top"><span><b>Siteline</b> · Text to the {person.title.toLowerCase()}</span>{a.state !== 'none' && <span className="tabular">{formatClock(a.sentAt)}</span>}</div>
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
      <div className="mt-4 flex gap-2" role="group" aria-label={`Reply as the ${person.title.toLowerCase()}`}>
        {REPLIES.map((r) => (
          <button
            key={r}
            type="button"
            disabled={a.state !== 'sent'}
            onClick={() => void reply(d.id, r, 'imessage')}
            title={replyMeaning[r]}
            aria-label={`Reply ${r}: ${replyMeaning[r]}`}
            className="btn btn-secondary flex-1 p-0 text-base tabular"
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
  const Icon = ownerIcon[d.owner]
  const startedAt = d.approval.state === 'calling' ? d.approval.callStartedAt : now
  const connected = now - startedAt > 2500

  return (
    <div className="flex min-h-80 flex-col items-center px-2 pt-6 pb-2 text-center">
      <span aria-hidden className="flex size-14 items-center justify-center rounded-[6px] border border-line bg-subtle text-ink-2">
        <Icon className="size-6" />
      </span>
      <p className="mt-4 font-serif text-lg font-medium">{person.title}</p>
      <p className="text-xs text-muted tabular" aria-live="polite">
        {connected ? `Siteline voice agent · ${formatDuration(now - startedAt - 2500)}` : 'Calling…'}
      </p>
      {connected && (
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bubble mt-4 text-left text-[13px]">
          “Hello, Siteline here with one Site {agreement?.siteNumber} escalation: {d.section}. Press 1 to approve, 2 to counter with the fallback, 3 to reject.”
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
            className="btn btn-secondary h-12 w-full text-lg tabular"
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
    <section aria-labelledby="phone-heading" className="tile">
      <div className="tile-head">
        <h2 id="phone-heading">Approver messages</h2>
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
              'inline-flex min-h-9 items-center gap-1.5 rounded-[6px] border px-2.5 text-xs font-medium transition-colors',
              d.id === active.id ? 'border-ink-2 bg-subtle text-ink' : 'border-line bg-surface text-muted hover:text-ink',
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
            <span className="tabular text-muted">
              <PhoneForwarded aria-hidden className="mr-1 inline size-4" />
              Voice call in {formatDuration(active.approval.sentAt + noReplyMs - now)} if no reply
            </span>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void callNow(active.id)}>
              <PhoneCall aria-hidden className="size-3.5" /> Simulate no reply
            </button>
          </div>
        )}
        {active.approval.state === 'calling' && (
          <p className="text-muted">
            The text got no reply, so the voice agent is calling
            {active.approval.callDelivery && active.approval.callDelivery !== 'simulated' ? ' the real phone through Photon.' : ' (on-screen call).'}
          </p>
        )}
        {active.approval.state === 'answered' && <p className="font-medium text-ok">Answered. The card updated live.</p>}
        <p className="mt-2 text-xs text-muted">
          {active.approval.state !== 'none' && active.approval.delivery === 'photon'
            ? `Live: this text went to the ${approvers[active.owner].title.toLowerCase()}’s phone by Photon. Their reply updates here; these buttons are the backup.`
            : integrations?.photon
              ? 'On-screen phone: this approver has no real phone number configured.'
              : 'On-screen phone: Photon isn’t configured on the server, so texts stay on this screen.'}
        </p>
      </div>
    </section>
  )
}
