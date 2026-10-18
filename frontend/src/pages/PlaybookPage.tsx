import { useEffect, useId, useRef, useState, type ChangeEvent } from 'react'
import { CircleHelp, Download, LoaderCircle, RotateCcw, Save, Upload } from 'lucide-react'

import * as api from '@/api'
import { outcomeVar } from '@/components/siteline/outcome-style'
import { PrioritySettings } from '@/components/siteline/PrioritySettings'
import { useHashScroll } from '@/hooks/useHashScroll'
import { playbook as defaultPlaybook, ownerLabel } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { Outcome, Owner, PlaybookRule } from '@/types'

const OWNERS: Owner[] = ['legal', 'finance', 'privacy']
const CLAUSES = new Set(defaultPlaybook.map((r) => r.clauseType))

function isRuleList(value: unknown): value is PlaybookRule[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (r) =>
        r && typeof r === 'object' &&
        CLAUSES.has(r.clauseType) &&
        OWNERS.includes(r.owner) &&
        ['label', 'standard', 'fallback', 'escalateWhen'].every((k) => typeof r[k] === 'string'),
    )
  )
}

function RuleEditor({ rule, onChange }: { rule: PlaybookRule; onChange: (r: PlaybookRule) => void }) {
  const id = useId()
  const fields: { key: 'standard' | 'fallback' | 'escalateWhen'; label: string; outcome: Outcome }[] = [
    { key: 'standard', label: 'Standard (accept)', outcome: 'accept' },
    { key: 'fallback', label: 'Fallback position (Counter)', outcome: 'counter' },
    { key: 'escalateWhen', label: 'Escalate when', outcome: 'escalate' },
  ]
  return (
    <article className="tile" aria-labelledby={`${id}-name`}>
      <header className="tile-head">
        <h2 id={`${id}-name`}>{rule.label}</h2>
        <div className="flex items-center gap-2">
          <label htmlFor={`${id}-owner`} className="text-sm font-medium text-muted">Owner</label>
          <select
            id={`${id}-owner`}
            value={rule.owner}
            onChange={(e) => onChange({ ...rule, owner: e.target.value as Owner })}
            className="field w-auto py-1"
          >
            {OWNERS.map((o) => <option key={o} value={o}>{ownerLabel[o]}</option>)}
          </select>
        </div>
      </header>
      {rule.openQuestion && (
        <p className="mt-3 flex items-start gap-2 rounded-[6px] border border-line border-l-[3px] border-l-elevated bg-surface px-3 py-2 text-sm">
          <CircleHelp aria-hidden className="mt-0.5 size-4 shrink-0 text-elevated" />
          <span><span className="font-semibold">Open question:</span> {rule.openQuestion}</span>
        </p>
      )}
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {fields.map((f) => (
          <div key={f.key} className="rounded-[6px] border border-line bg-subtle p-3" style={{ borderTop: `2px solid ${outcomeVar[f.outcome]}` }}>
            <label htmlFor={`${id}-${f.key}`} className="text-sm font-medium" style={{ color: outcomeVar[f.outcome] }}>{f.label}</label>
            <textarea
              id={`${id}-${f.key}`}
              value={rule[f.key]}
              onChange={(e) => onChange({ ...rule, [f.key]: e.target.value })}
              rows={4}
              className="field mt-1.5 text-sm"
            />
          </div>
        ))}
      </div>
    </article>
  )
}

export function PlaybookPage() {
  const { notify } = useDemo()
  const [rules, setRules] = useState<PlaybookRule[] | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  useHashScroll(rules !== null)

  useEffect(() => {
    api.getPlaybook().then(setRules, (e: Error) => setImportError(e.message))
  }, [])

  function edit(i: number, r: PlaybookRule) {
    setRules((rs) => rs && rs.map((x, j) => (j === i ? r : x)))
    setDirty(true)
  }

  async function save() {
    if (!rules) return
    setSaving(true)
    try {
      const res = await api.savePlaybook(rules)
      setDirty(false)
      setImportError(null)
      notify(`Playbook saved: ${res.saved} clause types. New uploads use it.`)
    } catch (e) {
      setImportError(e instanceof Error ? `Not saved. ${e.message}` : 'Not saved.')
    } finally {
      setSaving(false)
    }
  }

  function exportJson() {
    if (!rules) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(rules, null, 2)], { type: 'application/json' }))
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
      if (!isRuleList(parsed)) throw new Error('shape')
      setRules(parsed)
      setDirty(true)
      setImportError(null)
      notify(`Loaded ${parsed.length} rules from ${file.name}`)
    } catch {
      setImportError('That file isn’t a Siteline playbook. Expect a JSON array of rules with clauseType, owner, label, standard, fallback and escalateWhen.')
    }
  }

  return (
    <div className="wrap pb-12">
      <section className="hello pt-9 pb-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="eyebrow">Negotiation positions</span>
            <h1>Playbook</h1>
            <p>
              The rules engine reads these positions. Each change maps to one clause type, then lands on accept, counter or escalate. Anything the rules don’t cover, or can’t read reliably, goes to human review.{' '}
              <a href="#priority" className="font-medium text-accent hover:underline">Priority settings</a> widen a few accept lines for sites that cost the most to wait on.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" onChange={importJson} aria-label="Load playbook JSON" tabIndex={-1} />
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => fileRef.current?.click()}><Upload aria-hidden className="size-4" /> Load JSON</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={exportJson} disabled={!rules}><Download aria-hidden className="size-4" /> Export JSON</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setRules(structuredClone(defaultPlaybook)); setDirty(true) }}>
              <RotateCcw aria-hidden className="size-4" /> Reset
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={save} disabled={!rules || !dirty || saving}>
              {saving ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Save aria-hidden className="size-4" />}
              {dirty ? 'Save playbook' : 'Saved'}
            </button>
          </div>
        </div>
      </section>

      {importError && <p role="alert" className="alert mb-6">{importError}</p>}

      <div className="flex flex-col gap-6">
        {!rules && Array.from({ length: 3 }, (_, i) => <div key={i} className="tile h-48 animate-pulse" aria-hidden />)}
        {rules?.map((r, i) => <RuleEditor key={r.clauseType} rule={r} onChange={(next) => edit(i, next)} />)}
      </div>

      <section id="priority" className="mt-14 scroll-mt-6" aria-labelledby="priority-h">
        <div className="hello pb-5">
          <h2 id="priority-h" className="text-[clamp(24px,2.6vw,30px)]">Priority settings</h2>
          <p>How much money at risk makes a site a priority, and how much leeway each level gets on site asks. Escalate floors never move, and every suggestion still needs a person’s confirmation.</p>
        </div>
        <PrioritySettings />
      </section>
    </div>
  )
}
