import { useId, useState, type FormEvent } from 'react'
import { Check, FileText, History, MessageSquare, MessageSquareText, Phone, ShieldAlert, ShieldCheck, Undo2, UserRound } from 'lucide-react'
import { motion } from 'motion/react'

import * as api from '@/api'
import { OutcomeBadge } from '@/components/siteline/outcome'
import { outcomeBg, outcomeIcon, outcomeVar } from '@/components/siteline/outcome-style'
import { RedlineDiff } from '@/components/siteline/RedlineDiff'
import { useNow } from '@/hooks/useNow'
import { formatDuration } from '@/lib/format'
import { cn } from '@/lib/utils'
import { approvers, clauseLabel, outcomeLabel, ownerLabel, replyMeaning } from '@/mocks/playbook'
import { effectiveOutcome, isConfirmed, isWaiting } from '@/state/decision'
import { useDemo } from '@/state/demo'
import type { Decision, Outcome } from '@/types'

const kindLabel: Record<Decision['kind'], string> = {
  insertion: 'Insertion',
  deletion: 'Deletion',
  replacement: 'Replacement',
  comment: 'Comment',
}

const MIN_REASON = 8
/** Outcomes an override can resolve to. Human review and novel would leave the change unresolved. */
const OVERRIDE_OUTCOMES: Outcome[] = ['accept', 'fallback', 'escalate']

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
        className="flex flex-wrap items-center gap-2 rounded-[18px] bg-mint px-4 py-3 text-sm text-mint-ink"
        role="status"
      >
        <ShieldCheck aria-hidden className="size-4" />
        <span className="font-extrabold">{person.name} replied “{a.reply}” · {replyMeaning[a.reply]}</span>
        <span>via {a.channel === 'imessage' ? 'iMessage' : 'voice call'} in {formatDuration(a.answeredAt - a.sentAt)}</span>
      </motion.div>
    )
  }

  const left = a.sentAt + noReplyMs - now
  const how = a.delivery === 'photon' ? 'by Photon iMessage' : 'to the on-screen phone'
  const callHow = a.state === 'calling' && a.callDelivery && a.callDelivery !== 'simulated' ? ' (live call via Twilio + Photon SIP)' : ''
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[18px] bg-rose px-4 py-3 text-sm text-rose-ink">
      {a.state === 'calling' ? <Phone aria-hidden className="size-4" /> : <MessageSquareText aria-hidden className="size-4" />}
      <span className="font-extrabold">
        {a.state === 'calling' ? `No reply: calling ${person.name}${callHow}…` : `Texted ${person.name} (${ownerLabel[d.owner]}) ${how} · awaiting reply`}
      </span>
      {a.state === 'sent' && <span className="tabular">calls in {formatDuration(left)}</span>}
      {(a.error || (a.state === 'calling' && a.callError)) && (
        <span className="basis-full text-xs">Delivery problem: {a.state === 'calling' && a.callError ? a.callError : a.error}</span>
      )}
      <span className="ml-auto flex gap-2">
        <button type="button" className="btn btn-soft btn-sm" onClick={() => focusEscalation(d.id)}>Show on phone</button>
        {a.state === 'sent' && <button type="button" className="btn btn-soft btn-sm" onClick={() => void callNow(d.id)}>Call now</button>}
      </span>
    </div>
  )
}

function OverrideForm({ d, onDone }: { d: Decision; onDone: () => void }) {
  const { override } = useDemo()
  // The backend refuses Siteline's own outcome, so it is not offered.
  const options = OVERRIDE_OUTCOMES.filter((o) => o !== d.outcome)
  const [outcome, setOutcome] = useState<Outcome>(options[0])
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
    <form onSubmit={submit} className="mt-4 rounded-[20px] bg-bg p-4" noValidate>
      <fieldset>
        <legend className="text-sm font-extrabold">Override outcome</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {options.map((o) => {
            const Icon = outcomeIcon[o]
            const on = outcome === o
            return (
              <label
                key={o}
                className={cn(
                  'inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-extrabold transition-colors has-[input:focus-visible]:outline-3 has-[input:focus-visible]:outline-blue',
                  on ? '' : 'bg-card text-muted shadow-[inset_0_0_0_2px_var(--line)] hover:text-ink',
                )}
                style={on ? { background: outcomeBg[o], color: outcomeVar[o], boxShadow: `inset 0 0 0 2px ${outcomeVar[o]}` } : undefined}
              >
                <input type="radio" name={`override-${d.id}`} value={o} checked={on} onChange={() => setOutcome(o)} className="sr-only" />
                <Icon aria-hidden className="size-4" />
                {outcomeLabel[o]}
              </label>
            )
          })}
        </div>
      </fieldset>
      <label htmlFor={reasonId} className="mt-4 block text-sm font-extrabold">
        Reason <span className="text-tangerine-ink" aria-hidden>*</span>
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
      <p id={`${reasonId}-help`} className={cn('mt-1 text-sm', error ? 'font-extrabold text-rose-ink' : 'text-muted')} role={error ? 'alert' : undefined}>
        {error ?? 'Logged with the decision and included in the export.'}
      </p>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn btn-orange" disabled={saving}>{saving ? 'Saving…' : 'Save override'}</button>
        <button type="button" className="btn btn-soft" onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}

export function DecisionCard({ d }: { d: Decision }) {
  const { activeEscalationId, clearOverride, confirm, unconfirm } = useDemo()
  const [editing, setEditing] = useState(false)
  const outcome = effectiveOutcome(d)
  const canConfirm = !isWaiting(d) && !isConfirmed(d)
  const widened = Boolean(d.leniency && d.ruleId.endsWith('P'))
  const person = approvers[d.owner]
  const isActive = activeEscalationId === d.id && d.approval.state !== 'answered'

  return (
    <article
      id={`change-${d.id}`}
      aria-labelledby={`${d.id}-title`}
      className={cn('panel scroll-mt-6 rounded-[24px] p-5 sm:p-6', isActive && 'outline-3 outline-offset-2 outline-tangerine')}
      style={{ boxShadow: `inset 6px 0 0 ${outcomeVar[outcome]}, var(--shadow)` }}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">Change {String(d.index).padStart(2, '0')} · {kindLabel[d.kind]} · {clauseLabel[d.clauseType]}</p>
          <h3 id={`${d.id}-title`} className="mt-1 text-xl">{d.section}</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {d.override && <span className="text-sm text-muted"><s>{outcomeLabel[d.outcome]}</s> →</span>}
          <OutcomeBadge outcome={outcome} />
        </div>
      </header>

      <div className="mt-4 rounded-[18px] bg-bg p-4">
        <RedlineDiff change={d} />
        {d.siteComment && (
          <p className="mt-3 flex gap-2 border-t-2 border-line pt-3 text-sm">
            <MessageSquare aria-hidden className="mt-0.5 size-4 shrink-0 text-blue" />
            <span><span className="font-extrabold">{d.author}:</span> {d.siteComment}</span>
          </p>
        )}
      </div>

      <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2 [&>div]:min-w-0">
        <div>
          <dt className="eyebrow">Rule fired</dt>
          <dd className="mt-1">
            <code className="chip mr-1 text-xs">{d.ruleId}</code>
            {widened && <span className="pill p-rose mr-1">Widened for site priority</span>}
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
                className={cn('pill max-w-full font-bold whitespace-normal [overflow-wrap:anywhere]', v.verified === false ? 'p-rose' : 'p-cream')}
              >
                <span className="font-semibold">{v.field}</span> <span className="font-extrabold text-ink">{v.value}</span>
                {v.verified === false && <ShieldAlert aria-label="quote not verified" className="size-3.5" />}
              </span>
            ))}
            {d.extracted.length === 0 && <span className="text-xs text-muted">None</span>}
            <span className={cn('pill', d.confidence < 0.8 ? 'p-butter' : 'p-cream')}>
              <span className="font-semibold">confidence</span> <span className="font-extrabold tabular">{d.confidence.toFixed(2)}</span>
            </span>
          </dd>
        </div>
        <div className="md:col-span-2">
          <dt className={cn('eyebrow flex items-center gap-1.5', d.quoteVerified ? 'text-mint-ink' : 'text-rose-ink')}>
            {d.quoteVerified ? <ShieldCheck aria-hidden className="size-3.5" /> : <ShieldAlert aria-hidden className="size-3.5" />}
            {d.quoteVerified ? 'Quote verified verbatim' : 'Quote failed verification'}
          </dt>
          <dd className="mt-1">
            {d.quote ? (
              <blockquote className={cn('border-l-4 pl-3 italic', d.quoteVerified ? 'border-mint' : 'border-rose')}>“{d.quote}”</blockquote>
            ) : (
              <p className="border-l-4 border-rose pl-3 text-muted">{d.extractionError ? `No extraction: ${d.extractionError}` : 'No quote returned.'}</p>
            )}
            {d.cached && <p className="mt-1 text-xs text-muted">From the cached extraction.</p>}
          </dd>
        </div>
        {d.precedent && (
          <div className="md:col-span-2">
            <dt className="eyebrow flex items-center gap-1.5 text-blue"><History aria-hidden className="size-3.5" /> Precedent</dt>
            <dd className="mt-1">{d.precedent.summary}</dd>
            {d.precedent.sameSite
              .filter((m) => m.sourceKey)
              .map((m, i) => (
                // Records from one confirmed agreement share its document key, so it can't be the key alone
                <dd key={`${m.agreementId}-${m.sourceSection ?? ''}-${i}`} className="mt-2 rounded-[14px] bg-sky px-3 py-2 text-xs">
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
            <span aria-hidden className="rank size-9 text-xs">{person.name.split(' ').map((p) => p[0]).join('')}</span>
            <span>
              <span className="font-extrabold">{ownerLabel[d.owner]}</span>
              <span className="text-muted"> · {person.name}, {person.role}</span>
            </span>
          </dd>
        </div>
        <div className="flex flex-wrap items-end justify-start gap-2 md:justify-end">
          {canConfirm && (
            <button type="button" className="btn btn-orange" onClick={() => void confirm(d.id)}>
              <Check aria-hidden className="size-4" /> {d.precedent ? 'Confirm precedent' : 'Confirm suggestion'}
            </button>
          )}
          {d.confirmation && !d.override && (
            <button type="button" className="btn btn-soft" onClick={() => void unconfirm(d.id)} aria-label="Undo confirmation">
              <Undo2 aria-hidden className="size-4" /> Confirmed by {d.confirmation.by}
            </button>
          )}
          {d.override ? (
            <button type="button" className="btn btn-soft" onClick={() => void clearOverride(d.id)}>
              <Undo2 aria-hidden className="size-4" /> Undo override
            </button>
          ) : (
            !editing && (
              <button type="button" className="btn btn-soft" onClick={() => setEditing(true)}>
                <UserRound aria-hidden className="size-4" /> Override
              </button>
            )
          )}
        </div>
      </dl>

      {d.override && (
        <p className="mt-4 rounded-[18px] bg-bg px-4 py-3 text-sm">
          <span className="font-extrabold">Overridden by you:</span> “{d.override.reason}”
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
