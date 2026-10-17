import { useId, useState, type FormEvent } from 'react'
import { MessageSquare, MessageSquareText, Phone, ShieldAlert, ShieldCheck, Undo2, UserRound } from 'lucide-react'
import { motion } from 'motion/react'

import { OutcomeBadge } from '@/components/siteline/outcome'
import { outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { RedlineDiff } from '@/components/siteline/RedlineDiff'
import { BorderBeam } from '@/components/ui/border-beam'
import { useNow } from '@/hooks/useNow'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'
import { approvers, clauseLabel, outcomeLabel, outcomeOrder, ownerLabel, replyMeaning } from '@/mocks/playbook'
import { effectiveOutcome } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { Decision, Outcome } from '@/types'

const kindLabel: Record<Decision['kind'], string> = {
  insertion: 'Insertion',
  deletion: 'Deletion',
  replacement: 'Replacement',
  comment: 'Comment',
}

const MIN_REASON = 8

function ApprovalLine({ d }: { d: Decision }) {
  const { focusEscalation, callNow, noReplyMs } = useDemo()
  const waiting = d.approval.state === 'sent' || d.approval.state === 'calling'
  const now = useNow(1000, waiting)
  const person = approvers[d.owner]
  const a = d.approval

  if (a.state === 'none') return null

  if (a.state === 'answered') {
    return (
      <motion.div
        initial={{ scale: 0.98, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="flex flex-wrap items-center gap-2 rounded-2xl border border-mint/40 bg-mint/10 px-4 py-3 text-sm"
        role="status"
      >
        <ShieldCheck aria-hidden className="size-4 text-mint" />
        <span className="font-bold">
          {person.name} replied “{a.reply}” · {replyMeaning[a.reply]}
        </span>
        <span className="text-muted">
          via {a.channel === 'imessage' ? 'iMessage' : 'voice call'} in {formatDuration(a.answeredAt - a.sentAt)}
        </span>
      </motion.div>
    )
  }

  const left = a.sentAt + noReplyMs - now
  const how = a.delivery === 'photon' ? 'by Photon iMessage' : 'to the on-screen phone'
  const callHow = a.state === 'calling' && a.callDelivery && a.callDelivery !== 'simulated' ? ' (live call via Twilio + Photon SIP)' : ''
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-red/50 bg-red/10 px-4 py-3 text-sm">
      {a.state === 'calling' ? <Phone aria-hidden className="size-4 text-butter" /> : <MessageSquareText aria-hidden className="size-4 text-butter" />}
      <span className="font-bold">
        {a.state === 'calling' ? `No reply: calling ${person.name}${callHow}…` : `Texted ${person.name} (${ownerLabel[d.owner]}) ${how} · awaiting reply`}
      </span>
      {a.state === 'sent' && <span className="tabular text-muted">calls in {formatDuration(left)}</span>}
      {(a.error || (a.state === 'calling' && a.callError)) && (
        <span className="basis-full text-xs text-butter">Delivery problem: {a.state === 'calling' && a.callError ? a.callError : a.error}</span>
      )}
      <span className="ml-auto flex gap-2">
        <button type="button" className="btn btn-ghost min-h-9 px-3 py-1 text-xs" onClick={() => focusEscalation(d.id)}>
          Show on phone
        </button>
        {a.state === 'sent' && (
          <button type="button" className="btn btn-ghost min-h-9 px-3 py-1 text-xs" onClick={() => void callNow(d.id)}>
            Call now
          </button>
        )}
      </span>
    </div>
  )
}

function OverrideForm({ d, onDone }: { d: Decision; onDone: () => void }) {
  const { override } = useDemo()
  const [outcome, setOutcome] = useState<Outcome>(effectiveOutcome(d) === 'accept' ? 'fallback' : 'accept')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const reasonId = useId()

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (reason.trim().length < MIN_REASON) {
      setError(`Add a reason of at least ${MIN_REASON} characters so the override is auditable.`)
      return
    }
    setSaving(true)
    await override(d.id, outcome, reason.trim())
    setSaving(false)
    onDone()
  }

  return (
    <form onSubmit={submit} className="mt-4 rounded-2xl border border-line bg-space/70 p-4" noValidate>
      <fieldset>
        <legend className="text-sm font-bold">Override outcome</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {outcomeOrder.map((o) => {
            const Icon = outcomeIcon[o]
            return (
              <label
                key={o}
                className={cn(
                  'inline-flex min-h-11 items-center gap-1.5 rounded-full border px-3 text-sm font-bold transition-colors has-[input:focus-visible]:ring-2 has-[input:focus-visible]:ring-yellow',
                  outcome === o ? 'text-text' : 'border-line text-muted hover:text-text',
                )}
                style={outcome === o ? { borderColor: outcomeVar[o], background: `color-mix(in oklab, ${outcomeVar[o]} 18%, transparent)` } : undefined}
              >
                <input type="radio" name={`override-${d.id}`} value={o} checked={outcome === o} onChange={() => setOutcome(o)} className="sr-only" />
                <Icon aria-hidden className="size-4" style={{ color: outcomeVar[o] }} />
                {outcomeLabel[o]}
              </label>
            )
          })}
        </div>
      </fieldset>
      <label htmlFor={reasonId} className="mt-4 block text-sm font-bold">
        Reason <span className="text-butter" aria-hidden>*</span>
      </label>
      <textarea
        id={reasonId}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        onBlur={() => reason && reason.trim().length < MIN_REASON && setError(`Add a reason of at least ${MIN_REASON} characters so the override is auditable.`)}
        rows={2}
        required
        aria-invalid={!!error}
        aria-describedby={`${reasonId}-help`}
        className="field mt-1"
        placeholder="e.g. Site is a state institution; venue clause is non-negotiable for them"
      />
      <p id={`${reasonId}-help`} className={cn('mt-1 text-sm', error ? 'font-bold text-butter' : 'text-muted')} role={error ? 'alert' : undefined}>
        {error ?? 'Logged with the decision and included in the export.'}
      </p>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save override'}</button>
        <button type="button" className="btn btn-ghost" onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}

export function DecisionCard({ d }: { d: Decision }) {
  const { activeEscalationId, clearOverride } = useDemo()
  const [editing, setEditing] = useState(false)
  const outcome = effectiveOutcome(d)
  const person = approvers[d.owner]
  const isActive = activeEscalationId === d.id && d.approval.state !== 'answered'

  return (
    <article
      id={`change-${d.id}`}
      aria-labelledby={`${d.id}-title`}
      className="panel relative scroll-mt-24 overflow-hidden p-5 sm:p-6"
      style={{ borderLeft: `4px solid ${outcomeVar[outcome]}` }}
    >
      {isActive && <BorderBeam size={90} duration={7} colorFrom="var(--yellow)" colorTo="var(--magenta)" />}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">
            Change {String(d.index).padStart(2, '0')} · {kindLabel[d.kind]} · {clauseLabel[d.clauseType]}
          </p>
          <h3 id={`${d.id}-title`} className="mt-1 font-sans text-lg font-bold">{d.section}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {d.override && (
            <span className="inline-flex items-center gap-1 text-sm text-muted">
              <s>{outcomeLabel[d.outcome]}</s> →
            </span>
          )}
          <OutcomeBadge outcome={outcome} />
        </div>
      </header>

      <div className="mt-4 rounded-2xl bg-space/60 p-4">
        <RedlineDiff change={d} />
        {d.siteComment && (
          <p className="mt-3 flex gap-2 border-t border-line pt-3 text-sm">
            <MessageSquare aria-hidden className="mt-0.5 size-4 shrink-0 text-blue-l" />
            <span><span className="font-bold">{d.author}:</span> {d.siteComment}</span>
          </p>
        )}
      </div>

      <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2">
        <div>
          <dt className="eyebrow">Rule fired</dt>
          <dd className="mt-1">
            <code className="rounded bg-space-2 px-1.5 py-0.5 text-xs font-bold text-cream">{d.ruleId}</code>{' '}
            {d.ruleText}
          </dd>
        </div>
        <div>
          <dt className="eyebrow">Extracted values</dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {d.extracted.map((v) => (
              <span
                key={v.field}
                title={v.quote ? `“${v.quote}”${v.verified === false ? ' (not found in the redline)' : ''}` : undefined}
                className={cn('rounded-full border px-2.5 py-0.5 text-xs', v.verified === false ? 'border-butter' : 'border-line')}
              >
                <span className="text-muted">{v.field}</span> <span className="font-bold">{v.value}</span>
                {v.verified === false && <ShieldAlert aria-label="quote not verified" className="ml-1 inline size-3 text-butter" />}
              </span>
            ))}
            {d.extracted.length === 0 && <span className="text-xs text-muted">None</span>}
            <span className="rounded-full border border-line px-2.5 py-0.5 text-xs">
              <span className="text-muted">confidence</span>{' '}
              <span className={cn('tabular font-bold', d.confidence < 0.8 && 'text-butter')}>{d.confidence.toFixed(2)}</span>
            </span>
          </dd>
        </div>
        <div className="md:col-span-2">
          <dt className="eyebrow flex items-center gap-1.5">
            {d.quoteVerified ? <ShieldCheck aria-hidden className="size-3.5 text-mint" /> : <ShieldAlert aria-hidden className="size-3.5 text-butter" />}
            {d.quoteVerified ? 'Quote verified verbatim' : 'Quote failed verification'}
          </dt>
          <dd className="mt-1">
            {d.quote ? (
              <blockquote className={cn('border-l-2 pl-3 italic', d.quoteVerified ? 'border-mint' : 'border-butter')}>
                “{d.quote}”
              </blockquote>
            ) : (
              <p className="border-l-2 border-butter pl-3 text-muted">{d.extractionError ? `No extraction: ${d.extractionError}` : 'No quote returned.'}</p>
            )}
            {d.cached && <p className="mt-1 text-xs text-muted">From the cached extraction.</p>}
          </dd>
        </div>
        {d.counterText != null && (outcome === 'fallback' || outcome === 'escalate') && (
          <div className="md:col-span-2">
            <dt className="eyebrow">{outcome === 'fallback' ? 'Counter sent back' : 'If rejected, sponsor holds'}</dt>
            <dd className="mt-1 text-muted">{d.counterText || 'Delete the inserted text.'}</dd>
          </div>
        )}
        <div>
          <dt className="eyebrow">Owner</dt>
          <dd className="mt-1 flex items-center gap-2">
            <span aria-hidden className="flex size-8 items-center justify-center rounded-full bg-space-2 text-xs font-bold text-yellow">
              {person.name.split(' ').map((p) => p[0]).join('')}
            </span>
            <span>
              <span className="font-bold">{ownerLabel[d.owner]}</span>
              <span className="text-muted"> · {person.name}, {person.role}</span>
            </span>
          </dd>
        </div>
        <div className="flex items-end justify-start md:justify-end">
          {d.override ? (
            <button type="button" className="btn btn-ghost" onClick={() => void clearOverride(d.id)}>
              <Undo2 aria-hidden className="size-4" /> Undo override
            </button>
          ) : (
            !editing && (
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(true)}>
                <UserRound aria-hidden className="size-4" /> Override
              </button>
            )
          )}
        </div>
      </dl>

      {d.override && (
        <p className="mt-4 rounded-2xl border border-line px-4 py-3 text-sm">
          <span className="font-bold">Overridden by you:</span> “{d.override.reason}”
        </p>
      )}
      {editing && !d.override && <OverrideForm d={d} onDone={() => setEditing(false)} />}

      {outcome === 'escalate' && (
        <div className="mt-4">
          <ApprovalLine d={d} />
        </div>
      )}
    </article>
  )
}
