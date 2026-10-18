import { useEffect, useId, useRef, useState, type ChangeEvent } from 'react'
import { ChevronRight, Download, LoaderCircle, Pencil, RotateCcw, Save, Upload } from 'lucide-react'

import * as api from '@/api'
import { outcomeBg, outcomeVar } from '@/components/siteline/outcome-style'
import { PrioritySettings } from '@/components/siteline/PrioritySettings'
import { useHashScroll } from '@/hooks/useHashScroll'
import { formatClock } from '@/lib/format'
import { fill, forgetRulePositions, positionAnchor, templatesOnly } from '@/lib/playbook'
import { cn } from '@/lib/utils'
import { outcomeLabel, ownerLabel } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { Outcome, Owner, Playbook, PlaybookChange, PlaybookClause, PlaybookLogEntry, PlaybookPosition } from '@/types'

const OWNERS: Owner[] = ['legal', 'finance', 'privacy']
const TEXTS: { key: 'standard' | 'counter' | 'escalate'; label: string; outcome: Outcome }[] = [
  { key: 'standard', label: 'Standard', outcome: 'accept' },
  { key: 'counter', label: 'Counter', outcome: 'counter' },
  { key: 'escalate', label: 'Escalate', outcome: 'escalate' },
]

const isText = (v: unknown) => typeof v === 'string'

/** Enough of the shape that the page can render it; the server validates the rest on Save. */
function isPlaybook(value: unknown): value is Playbook {
  const v = value as Playbook
  return !!v && typeof v === 'object' && Array.isArray(v.clauses) && v.clauses.every((c) =>
    !!c && typeof c === 'object' && isText(c.clauseType) && isText(c.label) && isText(c.summary) && Array.isArray(c.positions) &&
    c.positions.every((p) =>
      !!p && typeof p === 'object' && [p.id, p.issue, p.form, p.standard, p.counter, p.escalate, p.rationale].every(isText) &&
      Array.isArray(p.talkingPoints) && p.talkingPoints.every(isText) &&
      !!p.limits && typeof p.limits === 'object' &&
      Object.values(p.limits).every((l) => !!l && typeof l === 'object' && typeof l.value === 'number' && isText(l.unit) && isText(l.label)) &&
      Array.isArray(p.rules) && p.rules.every((r) => !!r && isText(r.id) && isText(r.when) && isText(r.outcome))))
}

function Position({ clause, p, onChange }: { clause: PlaybookClause; p: PlaybookPosition; onChange: (p: PlaybookPosition) => void }) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  return (
    <article id={positionAnchor(clause.clauseType, p.id)} aria-labelledby={`${id}-issue`} className="scroll-mt-6 border-t border-line pt-5 first:border-t-0 first:pt-0">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={`${id}-issue`} className="font-serif text-[18px]">
          {p.issue} <span className="ml-1 font-sans text-xs font-normal text-muted">{p.form}</span>
        </h3>
        <span className="flex flex-wrap items-center gap-1.5">
          {p.rules.map((r) => (
            <code key={r.id} title={`${outcomeLabel[r.outcome]}: ${fill(r.when, p.limits)}`} className="chip text-xs"
              style={{ color: outcomeVar[r.outcome], background: outcomeBg[r.outcome] }}>{r.id}</code>
          ))}
          <button type="button" className="btn btn-secondary btn-sm" aria-pressed={editing} onClick={() => setEditing((e) => !e)}>
            <Pencil aria-hidden className="size-3.5" /> {editing ? 'Done' : 'Edit wording'}
          </button>
        </span>
      </header>

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {TEXTS.map((t) => (
          <div key={t.key} className="rounded-[6px] border border-line bg-subtle p-3" style={{ borderTop: `2px solid ${outcomeVar[t.outcome]}` }}>
            <label htmlFor={`${id}-${t.key}`} className="text-xs font-semibold tracking-wide uppercase" style={{ color: outcomeVar[t.outcome] }}>{t.label}</label>
            {editing ? (
              <textarea id={`${id}-${t.key}`} value={p[t.key]} rows={4} className="field mt-1.5 text-sm"
                onChange={(e) => onChange({ ...p, [t.key]: e.target.value })} />
            ) : (
              <p id={`${id}-${t.key}`} className="mt-1.5 text-sm leading-relaxed">{fill(p[t.key], p.limits)}</p>
            )}
          </div>
        ))}
      </div>
      {editing && <p className="mt-1.5 text-xs text-muted">Write a limit as {'{name}'}, e.g. {Object.keys(p.limits).map((k) => `{${k}}`).join(', ') || 'none for this position'}.</p>}

      {Object.keys(p.limits).length > 0 && (
        <fieldset className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
          <legend className="sr-only">Limits for {p.issue}</legend>
          {Object.entries(p.limits).map(([k, lim]) => (
            <label key={k} className="flex items-center gap-2 text-sm">
              <span className="text-muted">{lim.label}</span>
              {/* An empty box stays empty (NaN) and blocks Save, rather than quietly becoming 0 */}
              <input type="number" min={0} step="any" value={Number.isNaN(lim.value) ? '' : lim.value} aria-invalid={Number.isNaN(lim.value)}
                className={cn('field w-20 py-1 text-right tabular', Number.isNaN(lim.value) && 'border-high')}
                onChange={(e) => onChange({ ...p, limits: { ...p.limits, [k]: { ...lim, value: e.target.value === '' ? NaN : Number(e.target.value) } } })} />
              <span className="text-muted">{lim.unit.trim()}</span>
            </label>
          ))}
        </fieldset>
      )}

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium text-accent">Rationale and talking points</summary>
        <p className="mt-2 leading-relaxed">{fill(p.rationale, p.limits)}</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-2">
          {p.talkingPoints.map((t, i) => <li key={i}>{fill(t, p.limits)}</li>)}
        </ul>
      </details>
    </article>
  )
}

function Clause({ clause, onChange }: { clause: PlaybookClause; onChange: (c: PlaybookClause) => void }) {
  const id = useId()
  return (
    <section id={clause.clauseType} aria-labelledby={`${id}-name`} className="tile scroll-mt-6">
      <header className="tile-head">
        <h2 id={`${id}-name`}>{clause.label} <span className="badge tabular">{clause.positions.length}</span></h2>
        <div className="flex items-center gap-2">
          <label htmlFor={`${id}-owner`} className="text-sm font-medium text-muted">Owner</label>
          <select id={`${id}-owner`} value={clause.owner} className="field w-auto py-1"
            onChange={(e) => onChange({ ...clause, owner: e.target.value as Owner })}>
            {OWNERS.map((o) => <option key={o} value={o}>{ownerLabel[o]}</option>)}
          </select>
        </div>
      </header>
      <p className="tile-sub max-w-3xl">{clause.summary}</p>
      <div className="mt-5 flex flex-col gap-5">
        {clause.positions.map((p, i) => (
          <Position key={p.id} clause={clause} p={p}
            onChange={(next) => onChange({ ...clause, positions: clause.positions.map((x, j) => (j === i ? next : x)) })} />
        ))}
      </div>
    </section>
  )
}

const siteLabel = (agreementId: string) => agreementId.replace(/^site-/, 'Site ')

/** What a save or reset will re-decide, shown before it happens. */
function Pending({ changes, action, busy, onConfirm, onCancel }: {
  changes: PlaybookChange[] | null; action: 'save' | 'reset'; busy: boolean; onConfirm: () => void; onCancel: () => void
}) {
  return (
    <div role="alertdialog" aria-labelledby="pending-h" className="tile mb-6 border-l-[3px] border-l-accent">
      <h2 id="pending-h" className="text-[18px]">{action === 'save' ? 'Save the playbook?' : 'Reset to the default playbook?'}</h2>
      {changes === null ? (
        <p className="mt-2 text-sm text-muted">Open suggestions are re-decided under the default playbook. Confirmed decisions, overrides and answered escalations never move.</p>
      ) : changes.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No open suggestion changes. New uploads use the saved playbook.</p>
      ) : (
        <>
          <p className="mt-2 text-sm">{action === 'save' ? 'Saving' : 'Resetting'} re-decides {changes.length} open suggestion{changes.length === 1 ? '' : 's'}. Confirmed decisions, overrides and answered escalations never move; a new escalation texts its approver.</p>
          <ul className="mt-2 space-y-1 text-sm">
            {changes.map((c) => (
              <li key={c.changeId}>
                <span className="font-medium">{siteLabel(c.agreementId)}</span> · {c.section}:{' '}
                <code className="chip text-xs">{c.from.ruleId}</code> {outcomeLabel[c.from.outcome]}
                <ChevronRight aria-hidden className="mx-1 inline size-3.5" />
                <code className="chip text-xs">{c.to.ruleId}</code> <span style={{ color: outcomeVar[c.to.outcome] }}>{outcomeLabel[c.to.outcome]}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-4 flex gap-2">
        <button type="button" className="btn btn-primary btn-sm" onClick={onConfirm} disabled={busy}>
          {busy && <LoaderCircle aria-hidden className="size-4 animate-spin" />} {action === 'save' ? 'Save playbook' : 'Reset playbook'}
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </div>
  )
}

export function PlaybookPage() {
  const { notify } = useDemo()
  const [pb, setPb] = useState<Playbook | null>(null)
  const [log, setLog] = useState<PlaybookLogEntry[]>([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<{ action: 'save' | 'reset'; changes: PlaybookChange[] | null } | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  // Bumped on every save or reset: the priority bands come from the playbook, so that panel reloads
  const [savedAt, setSavedAt] = useState(0)
  const fileRef = useRef<HTMLInputElement>(null)
  useHashScroll(pb !== null)

  useEffect(() => {
    api.getPlaybook().then((s) => { setPb(templatesOnly(s.playbook)); setLog(s.log) }, (e: Error) => setErrors([e.message]))
  }, [])

  function edit(i: number, c: PlaybookClause) {
    setPb((p) => p && { ...p, clauses: p.clauses.map((x, j) => (j === i ? c : x)) })
    setDirty(true)
    setPending(null) // the preview no longer describes what Save would do
  }

  const fail = (e: unknown) => setErrors(e instanceof api.ApiError && e.details?.length ? e.details : [e instanceof Error ? e.message : 'Not saved.'])

  async function askSave() {
    if (!pb) return
    setBusy(true)
    try {
      const { changes } = await api.previewPlaybook(pb)
      setErrors([])
      setPending({ action: 'save', changes })
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  async function askReset() {
    setBusy(true)
    try {
      const { changes } = await api.previewPlaybookReset()
      setErrors([])
      setPending({ action: 'reset', changes })
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  async function commit() {
    if (!pb || !pending) return
    setBusy(true)
    try {
      const res = pending.action === 'save' ? await api.savePlaybook(pb) : await api.resetPlaybook()
      setPb(templatesOnly(res.playbook))
      setLog(res.log)
      setDirty(false)
      setErrors([])
      setPending(null)
      forgetRulePositions()
      setSavedAt(Date.now())
      notify(`${pending.action === 'save' ? 'Playbook saved' : 'Playbook reset'}; ${res.changes.length} open suggestion${res.changes.length === 1 ? '' : 's'} re-decided.`)
    } catch (e) {
      fail(e)
      setPending(null)
    } finally {
      setBusy(false)
    }
  }

  function exportJson() {
    if (!pb) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(templatesOnly(pb), null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'siteline-playbook.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function importJson(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const parsed: unknown = JSON.parse(await file.text())
      if (!isPlaybook(parsed)) throw new Error('shape')
      setPb(templatesOnly(parsed))
      setDirty(true)
      setErrors([])
      notify(`Loaded ${parsed.clauses.length} clauses from ${file.name}. Save to apply them.`)
    } catch {
      setErrors(['That file isn’t a Siteline playbook. Expect an object with a list of clauses, each with its positions.'])
    }
  }

  const positions = pb?.clauses.reduce((n, c) => n + c.positions.length, 0) ?? 0
  const blank = pb?.clauses.flatMap((c) => c.positions.filter((p) => Object.values(p.limits).some((l) => Number.isNaN(l.value))).map((p) => p.issue)) ?? []
  const ruleCount = pb?.clauses.reduce((n, c) => n + c.positions.reduce((m, p) => m + p.rules.length, 0), 0) ?? 0

  return (
    <div className="wrap pb-12">
      <section className="hello pt-9 pb-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="eyebrow">Negotiation positions</span>
            <h1>Playbook</h1>
            <p>
              {pb ? `${pb.clauses.length} clauses, ${positions} positions, ${ruleCount} rules. ` : ''}
              Each position states the form’s standard, the counter Siteline sends back and when it escalates. The numbers below
              are the ones the rules engine decides by: change one and open suggestions are re-decided. Anything no position covers,
              or that can’t be read reliably, goes to human review.{' '}
              <a href="#priority" className="font-medium text-accent hover:underline">Priority settings</a> widen three accept lines for sites that cost the most to wait on.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" onChange={importJson} aria-label="Load playbook JSON" tabIndex={-1} />
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => fileRef.current?.click()}><Upload aria-hidden className="size-4" /> Load JSON</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={exportJson} disabled={!pb}><Download aria-hidden className="size-4" /> Export JSON</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => void askReset()} disabled={!pb || busy}>
              <RotateCcw aria-hidden className="size-4" /> Reset to default
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => void askSave()} disabled={!pb || !dirty || busy || blank.length > 0}
              title={blank.length ? `Fill in every limit first: ${blank.join(', ')}` : undefined}>
              {busy && !pending ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Save aria-hidden className="size-4" />}
              {dirty ? 'Save playbook' : 'Saved'}
            </button>
          </div>
        </div>
        {pb && (
          <nav aria-label="Clauses" className="mt-5 flex flex-wrap gap-1.5">
            {pb.clauses.map((c) => <a key={c.clauseType} href={`#${c.clauseType}`} className="pill s-neutral hover:text-accent">{c.label} <span className="tabular">{c.positions.length}</span></a>)}
          </nav>
        )}
      </section>

      {blank.length > 0 && <p role="status" className="alert mb-6">Fill in every limit before saving: {blank.join(', ')}.</p>}
      {errors.length > 0 && (
        <div role="alert" className="alert mb-6">
          <p className="font-semibold">Not saved.</p>
          <ul className="mt-1 list-disc pl-5">{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </div>
      )}
      {pending && <Pending {...pending} busy={busy} onConfirm={() => void commit()} onCancel={() => setPending(null)} />}

      <div className="flex flex-col gap-6">
        {!pb && Array.from({ length: 3 }, (_, i) => <div key={i} className="tile h-48 animate-pulse" aria-hidden />)}
        {pb?.clauses.map((c, i) => <Clause key={c.clauseType} clause={c} onChange={(next) => edit(i, next)} />)}
      </div>

      {log.length > 0 && (
        <section aria-labelledby="playbook-log-h" className="mt-8">
          <h2 id="playbook-log-h" className="eyebrow font-sans">Change log</h2>
          <ol className="mt-2 space-y-1 text-sm">
            {[...log].reverse().map((e, i) => (
              <li key={i} className={cn('flex flex-wrap gap-x-2', i > 0 && 'text-muted')}>
                <span className="tabular">{formatClock(e.at)}</span><span className="font-medium">{e.by}</span><span>{e.summary}</span>
                {e.moved !== undefined && <span className="text-muted">· {e.moved} open suggestion{e.moved === 1 ? '' : 's'} re-decided</span>}
              </li>
            ))}
          </ol>
        </section>
      )}

      <section id="priority" className="mt-14 scroll-mt-6" aria-labelledby="priority-h">
        <div className="hello pb-5">
          <h2 id="priority-h" className="text-[clamp(24px,2.6vw,30px)]">Priority settings</h2>
          <p>How much money at risk makes a site a priority, and how much leeway each level gets on site asks. Escalate floors never move, and every suggestion still needs a person’s confirmation.</p>
        </div>
        <PrioritySettings key={savedAt} />
      </section>
    </div>
  )
}
