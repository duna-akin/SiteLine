import type { ReactNode } from 'react'
import { ChevronLeft, PhoneCall, PhoneForwarded, Signal, Wifi } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'

import { SponsorChip } from '@/components/siteline/SponsorChip'
import { Iphone } from '@/components/ui/iphone'
import { Ripple } from '@/components/ui/ripple'
import { useNow } from '@/hooks/useNow'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'
import { approvers, clauseLabel, ownerLabel, replyMeaning } from '@/mocks/playbook'
import { NO_REPLY_MS } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { ApprovalReply, Decision } from '@/types'

// Screen rectangle inside the Magic UI iPhone frame (433×882 viewBox).
const SCREEN = {
  left: `${(21.25 / 433) * 100}%`,
  top: `${(19.25 / 882) * 100}%`,
  width: `${(389.5 / 433) * 100}%`,
  height: `${(843.5 / 882) * 100}%`,
  borderRadius: `${(55.75 / 389.5) * 100}% / ${(55.75 / 843.5) * 100}%`,
}

const REPLIES: ApprovalReply[] = [1, 2, 3]

function Bubble({ from, children }: { from: 'agent' | 'me'; children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
      className={cn(
        'max-w-[86%] rounded-2xl px-3 py-2 text-[12.5px] leading-snug whitespace-pre-line',
        from === 'agent' ? 'self-start rounded-bl-md bg-space-2 text-text' : 'self-end rounded-br-md bg-blue text-text',
      )}
    >
      {children}
    </motion.div>
  )
}

function Thread({ d }: { d: Decision }) {
  const { reply } = useDemo()
  const person = approvers[d.owner]
  const a = d.approval
  const answered = a.state === 'answered' ? a : null

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3 pt-1 pb-2">
        <ChevronLeft aria-hidden className="size-4 text-blue-l" />
        <div className="flex flex-1 flex-col items-center">
          <span aria-hidden className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-butter to-magenta text-[11px] font-black text-ink">S</span>
          <span className="mt-0.5 text-[11px] font-bold">Siteline Approvals</span>
          <span className="text-[10px] text-muted">to {person.name}</span>
        </div>
        <span className="size-4" />
      </div>

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto px-3 py-3" aria-live="polite">
        <span className="self-center text-[10px] text-muted">iMessage · Today</span>
        {a.state !== 'none' && (
          <Bubble from="agent">
            {`Site 07 · ${d.section}\n${clauseLabel[d.clauseType]} needs ${ownerLabel[d.owner]}.\n“${d.quote}”\nRule ${d.ruleId}.\n\nReply 1 approve · 2 counter with fallback · 3 reject`}
          </Bubble>
        )}
        {answered && (
          <>
            <Bubble from="me">{answered.reply}</Bubble>
            <Bubble from="agent">{`Got it: ${replyMeaning[answered.reply].toLowerCase()}. Site 07 card updated.`}</Bubble>
          </>
        )}
        {a.state === 'none' && <p className="self-center text-[11px] text-muted">No text sent yet.</p>}
      </div>

      <div className="border-t border-line px-2 py-2">
        <div className="flex gap-1.5" role="group" aria-label={`Reply as ${person.name}`}>
          {REPLIES.map((r) => (
            <button
              key={r}
              type="button"
              disabled={a.state !== 'sent'}
              onClick={() => void reply(d.id, r, 'imessage')}
              title={replyMeaning[r]}
              aria-label={`Reply ${r}: ${replyMeaning[r]}`}
              className="flex min-h-11 flex-1 items-center justify-center rounded-full border border-line bg-space text-base font-black text-text transition-colors hover:border-blue-l disabled:opacity-40"
            >
              {r}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function CallScreen({ d }: { d: Decision }) {
  const { reply } = useDemo()
  const now = useNow(500)
  const person = approvers[d.owner]
  const startedAt = d.approval.state === 'calling' ? d.approval.callStartedAt : now
  const connected = now - startedAt > 2500

  return (
    <div className="relative flex h-full flex-col items-center overflow-hidden px-4 pt-10 pb-6 text-center">
      <Ripple mainCircleSize={110} numCircles={5} className="top-[-12%]" />
      <span aria-hidden className="relative flex size-16 items-center justify-center rounded-full bg-gradient-to-br from-butter to-magenta text-xl font-black text-ink">
        {person.name.split(' ').map((p) => p[0]).join('')}
      </span>
      <p className="relative mt-3 text-lg font-bold">{person.name}</p>
      <p className="relative text-xs text-muted tabular" aria-live="polite">
        {connected ? `Siteline voice agent · ${formatDuration(now - startedAt - 2500)}` : 'Calling…'}
      </p>
      {connected && (
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="relative mt-5 rounded-2xl bg-space-2/90 px-3 py-2 text-[12px] leading-snug">
          “Hi {person.name.split(' ')[0]}, Siteline here with one Site 07 escalation: {d.section}. Press 1 to approve, 2 to counter with the fallback, 3 to reject.”
        </motion.p>
      )}
      <div className="relative mt-auto grid w-full grid-cols-3 gap-3" role="group" aria-label="Keypad">
        {REPLIES.map((r) => (
          <button
            key={r}
            type="button"
            disabled={!connected}
            onClick={() => void reply(d.id, r, 'voice')}
            aria-label={`Press ${r}: ${replyMeaning[r]}`}
            className="mx-auto flex size-14 items-center justify-center rounded-full bg-space-2 text-2xl font-bold text-text transition-transform active:scale-95 disabled:opacity-40"
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ApproverPhone({ escalations }: { escalations: Decision[] }) {
  const { activeEscalationId, focusEscalation, callNow } = useDemo()
  const active = escalations.find((d) => d.id === activeEscalationId) ?? escalations[0]
  const now = useNow(1000, active?.approval.state === 'sent')

  if (!active) return null
  const calling = active.approval.state === 'calling'

  return (
    <section aria-labelledby="phone-heading" className="flex flex-col items-center">
      <div className="flex w-full flex-wrap items-center justify-between gap-2">
        <h2 id="phone-heading" className="text-2xl">Approver phone</h2>
        <SponsorChip sponsor="Photon" label="Photon 2.0" />
      </div>
      <div className="mt-3 flex w-full flex-wrap gap-1.5" role="tablist" aria-label="Escalations">
        {escalations.map((d) => (
          <button
            key={d.id}
            type="button"
            role="tab"
            aria-selected={d.id === active.id}
            onClick={() => focusEscalation(d.id)}
            className={cn(
              'flex min-h-11 items-center gap-1.5 rounded-full border px-3 text-xs font-bold transition-colors',
              d.id === active.id ? 'border-yellow bg-yellow/10 text-text' : 'border-line text-muted hover:text-text',
            )}
          >
            <span
              aria-hidden
              className={cn('size-2 rounded-full', d.approval.state === 'answered' ? 'bg-mint' : d.approval.state === 'calling' ? 'bg-butter' : 'bg-red')}
            />
            {d.section.split(' ')[0]} · {ownerLabel[d.owner]}
            <span className="sr-only">
              {d.approval.state === 'answered' ? ' (answered)' : d.approval.state === 'calling' ? ' (calling)' : ' (awaiting reply)'}
            </span>
          </button>
        ))}
      </div>

      <div className="relative mt-4 w-full max-w-[290px]">
        <Iphone />
        <div className="absolute z-10 flex flex-col overflow-hidden bg-ink" style={SCREEN}>
          <div className="flex items-center justify-between px-6 pt-2.5 pb-1 text-[11px] font-bold">
            <span className="tabular">9:41</span>
            <span className="flex items-center gap-1" aria-hidden>
              <Signal className="size-3" /> <Wifi className="size-3" />
            </span>
          </div>
          <div className="min-h-0 flex-1 pt-5">
            <AnimatePresence mode="wait">
              <motion.div
                key={`${active.id}-${calling ? 'call' : 'msg'}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, transition: { duration: 0.12 } }}
                className="h-full"
              >
                {calling ? <CallScreen d={active} /> : <Thread d={active} />}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>

      <div className="mt-4 w-full text-center text-sm text-muted">
        {active.approval.state === 'sent' && (
          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className="tabular">
              <PhoneForwarded aria-hidden className="mr-1 inline size-4" />
              Voice call in {formatDuration(active.approval.sentAt + NO_REPLY_MS - now)} if no reply
            </span>
            <button type="button" className="btn btn-ghost min-h-9 px-3 py-1 text-xs" onClick={() => void callNow(active.id)}>
              <PhoneCall aria-hidden className="size-3.5" /> Simulate no reply
            </button>
          </div>
        )}
        {active.approval.state === 'calling' && <p>Text got no reply, so the Photon voice agent is calling.</p>}
        {active.approval.state === 'answered' && <p className="text-mint">Answered. The card updated live.</p>}
        <p className="mt-2 text-xs">On-screen phone for the demo; a teammate’s iPhone gets the real text.</p>
      </div>
    </section>
  )
}
