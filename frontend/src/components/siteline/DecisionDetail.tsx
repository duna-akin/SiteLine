import { useId, useState, type FormEvent } from 'react'
import { Check, FileText, History, MessageSquareText, Pencil, Phone, ShieldAlert, ShieldCheck, Undo2 } from 'lucide-react'
import { motion } from 'motion/react'

import * as api from '@/api'
import { outcomeBg, outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { ownerIcon } from '@/components/siteline/owner-style'
import { useNow } from '@/hooks/useNow'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'
import { approvers, clauseLabel, outcomeLabel, outcomeOrder, replyMeaning } from '@/mocks/playbook'
import { effectiveOutcome, isConfirmed, isWaiting } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { ApprovalReply, Decision, Outcome } from '@/types'

const kindLabel: Record<Decision['kind'], string> = {
  insertion: 'Insertion',
  deletion: 'Deletion',
  replacement: 'Replacement',
  comment: 'Comment',
}

const MIN_REASON = 8
const REPLIES: ApprovalReply[] = [1, 2, 3]
const replyShort: Record<ApprovalReply, string> = { 1: 'Approve', 2: 'Counter', 3: 'Reject' }

function ApprovalLine({ d }: { d: Decision }) {
  const { callNow, reply, noReplyMs } = useDemo()
  const waiting = d.approval.state === 'sent' || d.approval.state === 'calling'
  const now = useNow(1000, waiting)
  const person = approvers[d.owner]
  const a = d.approval

  if (a.state === 'none') return null

  if (a.state === 'answered') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-wrap items-center gap-2 rounded-[6px] border border-line border-l-[3px] border-l-ok bg-surface px-4 py-3 text-sm"
        role="status"
      >
        <ShieldCheck aria-hidden className="size-4 text-ok" />
        <span className="font-semibold">{person.title} replied “{a.reply}” · {replyMeaning[a.reply]}</span>
        <span className="text-muted">via {a.channel === 'imessage' ? 'iMessage' : 'voice call'} in {formatDuration(a.answeredAt - a.sentAt)}</span>
      </motion.div>
    )
  }

  const left = a.sentAt + noReplyMs - now
  const how = a.delivery === 'photon' ? 'by Photon iMessage' : '(simulated, no phone line set)'
  const callHow = a.state === 'calling' && a.callDelivery && a.callDelivery !== 'simulated' ? ' (live call via Twilio + Photon SIP)' : ''
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[6px] border border-line border-l-[3px] border-l-high bg-surface px-4 py-3 text-sm">
      {a.state === 'calling' ? <Phone aria-hidden className="size-4 text-high" /> : <MessageSquareText aria-hidden className="size-4 text-high" />}
      <span className="font-semibold">
        {a.state === 'calling' ? `No reply: calling the ${person.title.toLowerCase()}${callHow}…` : `Texted the ${person.title.toLowerCase()} ${how} · awaiting reply`}
      </span>
      {a.state === 'sent' && <span className="tabular text-muted">calls in {formatDuration(left)}</span>}
      {(a.error || (a.state === 'calling' && a.callError)) && (
        <span className="basis-full text-xs text-high">Delivery problem: {a.state === 'calling' && a.callError ? a.callError : a.error}</span>
      )}
      <span className="ml-auto flex gap-2">
        {a.state === 'sent' && <button type="button" className="btn btn-secondary btn-sm" onClick={() => void callNow(d.id)}>Call now</button>}
      </span>
      {/* Without a real phone line, the reviewer records the approver's answer here */}
      {(a.state === 'calling' ? a.callDelivery : a.delivery) !== 'photon' && (
        <span className="flex basis-full flex-wrap items-center gap-2" role="group" aria-label={`Record the ${person.title.toLowerCase()}’s reply`}>
          <span className="text-xs text-muted">Record their reply:</span>
          {REPLIES.map((r) => (
            <button key={r} type="button" className="btn btn-secondary btn-sm tabular" title={replyMeaning[r]}
              aria-label={`Reply ${r}: ${replyMeaning[r]}`} onClick={() => void reply(d.id, r, a.state === 'calling' ? 'voice' : 'imessage')}>
              {r} <span className="font-normal text-muted">{replyShort[r]}</span>
            </button>
          ))}
        </span>
      )}
    </div>
  )
}

export function OverrideForm({ d, onDone }: { d: Decision; onDone: () => void }) {
  const { override } = useDemo()
  // All five outcomes are listed; Siteline's own is shown but disabled, since the backend refuses it.
  // Human review and novel keep the change waiting, so export holds it until someone decides.
  const [outcome, setOutcome] = useState<Outcome>(outcomeOrder.find((o) => o !== d.outcome)!)
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
    setError(null)
    const failed = await override(d.id, outcome, reason.trim())
    setSaving(false)
    // Keep the form and the typed reason when the save fails, so nothing is lost.
    if (failed) setError(`Not saved: ${failed}`)
    else onDone()
  }

  return (
    <form onSubmit={submit} className="well mt-4 p-4" noValidate>
      <fieldset>
        <legend className="text-sm font-semibold">Override outcome</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {outcomeOrder.map((o) => {
            const Icon = outcomeIcon[o]
            const on = outcome === o
            const own = o === d.outcome
            return (
              <label
                key={o}
                title={own ? 'Siteline’s own outcome: pick a different one to override' : undefined}
                className={cn(
                  'inline-flex min-h-10 items-center gap-1.5 rounded-[6px] border px-3 text-sm font-medium transition-colors has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-accent',
                  own ? 'cursor-not-allowed border-dashed border-line-strong bg-subtle text-faint' : on ? '' : 'border-line-strong bg-surface text-muted hover:text-ink',
                )}
                style={on ? { background: outcomeBg[o], color: outcomeVar[o], borderColor: outcomeVar[o] } : undefined}
              >
                <input type="radio" name={`override-${d.id}`} value={o} checked={on} disabled={own} onChange={() => setOutcome(o)} className="sr-only" />
                <Icon aria-hidden className="size-4" />
                {outcomeLabel[o]}
                {own && <span className="text-xs font-normal">· Siteline’s call</span>}
              </label>
            )
          })}
        </div>
      </fieldset>
      <label htmlFor={reasonId} className="mt-4 block text-sm font-semibold">
        Reason <span className="text-elevated" aria-hidden>*</span>
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
      <p id={`${reasonId}-help`} className={cn('mt-1 text-sm', error ? 'font-semibold text-high' : 'text-muted')} role={error ? 'alert' : undefined}>
        {error ?? 'Logged with the decision and included in the export.'}
      </p>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save override'}</button>
        <button type="button" className="btn btn-secondary" onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}

/** Siteline's decision on one redlined paragraph, unfolded under it in the contract. */
export function DecisionDetail({ d }: { d: Decision }) {
  const { clearOverride, confirm, unconfirm } = useDemo()
  const [editing, setEditing] = useState(false)
  const outcome = effectiveOutcome(d)
  const canConfirm = !isWaiting(d) && !isConfirmed(d)
  const widened = Boolean(d.leniency && d.ruleId.endsWith('P'))
  const person = approvers[d.owner]
  const OwnerIcon = ownerIcon[d.owner]

  return (
    <div className="panel mt-2 mb-4 p-4 font-sans sm:p-5" style={{ borderLeft: `3px solid ${outcomeVar[outcome]}` }}>
      <p className="eyebrow">
        Change {String(d.index).padStart(2, '0')} · {kindLabel[d.kind]} · {clauseLabel[d.clauseType]}
        {d.override && <span className="ml-2 normal-case">Siteline said <s>{outcomeLabel[d.outcome]}</s></span>}
      </p>

      <dl className="mt-3 grid gap-4 text-sm md:grid-cols-2 [&>div]:min-w-0">
        <div>
          <dt className="eyebrow">Rule fired</dt>
          <dd className="mt-1">
            <code className="chip mr-1 text-xs">{d.ruleId}</code>
            {widened && <span className="pill s-high mr-1">Widened for site priority</span>}
            {d.ruleText}
          </dd>
          {d.precedent?.downgraded && (
            <dd className="mt-1 text-xs text-muted">
              Playbook rule <code className="chip text-xs">{d.precedent.originalRuleId}</code> would escalate: {d.precedent.originalRuleText}
            </dd>
          )}
        </div>
        <div>
          <dt className="eyebrow">Extracted values</dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {d.extracted.map((v, i) => (
              <span
                key={`${v.field}-${i}`}
                title={v.quote ? `“${v.quote}”${v.verified === false ? ' (not found in the redline)' : ''}` : undefined}
                className={cn('pill max-w-full font-semibold whitespace-normal [overflow-wrap:anywhere]', v.verified === false ? 's-high' : 's-neutral')}
              >
                <span className="font-semibold">{v.field}</span> <span className="font-semibold text-ink">{v.value}</span>
                {v.verified === false && <ShieldAlert aria-label="quote not verified" className="size-3.5" />}
              </span>
            ))}
            {d.extracted.length === 0 && <span className="text-xs text-muted">None</span>}
            <span className={cn('pill', d.confidence < 0.8 ? 's-elevated' : 's-neutral')}>
              <span className="font-semibold">confidence</span> <span className="font-semibold tabular">{d.confidence.toFixed(2)}</span>
            </span>
          </dd>
        </div>
        <div className="md:col-span-2">
          <dt className={cn('eyebrow flex items-center gap-1.5', d.quoteVerified ? 'text-ok' : 'text-high')}>
            {d.quoteVerified ? <ShieldCheck aria-hidden className="size-3.5" /> : <ShieldAlert aria-hidden className="size-3.5" />}
            {d.quoteVerified ? 'Quote verified verbatim' : 'Quote failed verification'}
          </dt>
          <dd className="mt-1">
            {d.quote ? (
              <blockquote className={cn('border-l-2 pl-3 font-serif text-[15px] text-ink-2', d.quoteVerified ? 'border-line-strong' : 'border-high')}>“{d.quote}”</blockquote>
            ) : (
              <p className="border-l-2 border-high pl-3 text-muted">{d.extractionError ? `No extraction: ${d.extractionError}` : 'No quote returned.'}</p>
            )}
            {d.cached && <p className="mt-1 text-xs text-muted">From the cached extraction.</p>}
          </dd>
        </div>
        {d.precedent && (
          <div className="md:col-span-2">
            <dt className="eyebrow flex items-center gap-1.5 text-accent"><History aria-hidden className="size-3.5" /> Precedent</dt>
            <dd className="mt-1">{d.precedent.summary}</dd>
            {d.precedent.sameSite
              .filter((m) => m.sourceKey)
              .map((m, i) => (
                // Records from one confirmed agreement share its document key, so it can't be the key alone
                <dd key={`${m.agreementId}-${m.sourceSection ?? ''}-${i}`} className="well mt-2 px-3 py-2 text-xs">
                  <span className="text-muted">Source: {m.siteName}, {m.sourceSection ?? 'final agreement'}</span>
                  {m.sourceQuote && <span className="block italic">“{m.sourceQuote}”</span>}
                  <a href={api.sourceUrl(m.sourceKey!)} className="link min-h-0 text-xs">
                    <FileText aria-hidden className="size-3.5" /> Open source document
                  </a>
                </dd>
              ))}
          </div>
        )}
        {d.counterText != null && (outcome === 'fallback' || outcome === 'escalate') && (
          <div className="md:col-span-2">
            <dt className="eyebrow">{outcome === 'fallback' ? 'Counter sent back' : 'If rejected, sponsor holds'}</dt>
            <dd className="mt-1 text-muted">{d.counterText || 'Delete the inserted text.'}</dd>
          </div>
        )}
        <div>
          <dt className="eyebrow">Owner</dt>
          <dd className="mt-1 flex items-center gap-2">
            <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-[6px] border border-line bg-subtle text-ink-2">
              <OwnerIcon className="size-4" />
            </span>
            <span>
              <span className="font-semibold">{person.title}</span>
              <span className="text-muted"> · {person.role}</span>
            </span>
          </dd>
        </div>
        <div className="flex flex-wrap items-end justify-start gap-2 md:justify-end">
          {canConfirm && (
            <button type="button" className="btn btn-primary" onClick={() => void confirm(d.id)}>
              <Check aria-hidden className="size-4" /> {d.precedent ? 'Confirm precedent' : 'Confirm suggestion'}
            </button>
          )}
          {d.confirmation && !d.override && (
            <button type="button" className="btn btn-secondary" onClick={() => void unconfirm(d.id)} aria-label="Undo confirmation">
              <Undo2 aria-hidden className="size-4" /> Confirmed by {d.confirmation.by}
            </button>
          )}
          {d.override ? (
            <button type="button" className="btn btn-secondary" onClick={() => void clearOverride(d.id)}>
              <Undo2 aria-hidden className="size-4" /> Undo override
            </button>
          ) : (
            !editing && (
              <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
                <Pencil aria-hidden className="size-4" /> Override
              </button>
            )
          )}
        </div>
      </dl>

      {d.override && (
        <p className="well mt-4 px-4 py-3 text-sm">
          <span className="font-semibold">Overridden by you:</span> “{d.override.reason}”
        </p>
      )}
      {editing && !d.override && <OverrideForm d={d} onDone={() => setEditing(false)} />}

      {outcome === 'escalate' && (
        <div className="mt-4">
          <ApprovalLine d={d} />
        </div>
      )}
    </div>
  )
}
