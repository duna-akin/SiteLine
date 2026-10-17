import { useEffect, useId, useRef, useState, type ChangeEvent } from 'react'
import { CircleHelp, Download, LoaderCircle, RotateCcw, Save, Upload } from 'lucide-react'

import * as api from '@/api'
import { outcomeVar } from '@/components/siteline/outcome-style'
import { BlurFade } from '@/components/ui/blur-fade'
import { playbook as defaultPlaybook, ownerLabel } from '@/mocks/playbook'
import { useDemo } from '@/state/demo'
import type { Owner, PlaybookRule } from '@/types'

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
  const fields: { key: 'standard' | 'fallback' | 'escalateWhen'; label: string; tone: string }[] = [
    { key: 'standard', label: 'Standard (accept)', tone: outcomeVar.accept },
    { key: 'fallback', label: 'Fallback (counter)', tone: outcomeVar.fallback },
    { key: 'escalateWhen', label: 'Escalate when', tone: outcomeVar.escalate },
  ]
  return (
    <article className="panel p-5" aria-labelledby={`${id}-name`}>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${id}-name`} className="text-2xl">{rule.label}</h2>
        <div className="flex items-center gap-2">
          <label htmlFor={`${id}-owner`} className="text-sm text-muted">Owner</label>
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
        <p className="mt-3 flex items-start gap-2 rounded-2xl border border-butter/50 bg-butter/10 px-3 py-2 text-sm">
          <CircleHelp aria-hidden className="mt-0.5 size-4 shrink-0 text-butter" />
          <span><span className="font-bold">Open question:</span> {rule.openQuestion}</span>
        </p>
      )}
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {fields.map((f) => (
          <div key={f.key}>
            <label htmlFor={`${id}-${f.key}`} className="flex items-center gap-1.5 text-sm font-bold">
              <span aria-hidden className="size-2 rounded-full" style={{ background: f.tone }} /> {f.label}
            </label>
            <textarea
              id={`${id}-${f.key}`}
              value={rule[f.key]}
              onChange={(e) => onChange({ ...rule, [f.key]: e.target.value })}
              rows={4}
              className="field mt-1 text-sm"
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
    <div className="wrap py-10 sm:py-14">
      <BlurFade>
        <p className="eyebrow">Playbook · 9 clause types</p>
        <div className="mt-3 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-4xl sm:text-6xl">Playbook <span className="text-yellow">editor</span></h1>
            <p className="mt-3 max-w-2xl text-lg text-muted">
              The rules engine reads these positions. Each change maps to one clause type, then lands on accept, fallback or escalate. Anything the rules don’t cover is novel.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" onChange={importJson} aria-label="Load playbook JSON" tabIndex={-1} />
            <button type="button" className="btn btn-ghost" onClick={() => fileRef.current?.click()}>
              <Upload aria-hidden className="size-4" /> Load JSON
            </button>
            <button type="button" className="btn btn-ghost" onClick={exportJson} disabled={!rules}>
              <Download aria-hidden className="size-4" /> Export JSON
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => { setRules(structuredClone(defaultPlaybook)); setDirty(true) }}>
              <RotateCcw aria-hidden className="size-4" /> Reset
            </button>
            <button type="button" className="btn btn-primary" onClick={save} disabled={!rules || !dirty || saving}>
              {saving ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Save aria-hidden className="size-4" />}
              {dirty ? 'Save playbook' : 'Saved'}
            </button>
          </div>
        </div>
      </BlurFade>

      {importError && <p role="alert" className="mt-4 rounded-2xl border border-butter/50 bg-butter/10 px-4 py-3 text-sm font-bold">{importError}</p>}

      <div className="mt-8 flex flex-col gap-4">
        {!rules && Array.from({ length: 3 }, (_, i) => <div key={i} className="panel h-48 animate-pulse" aria-hidden />)}
        {rules?.map((r, i) => (
          <BlurFade key={r.clauseType} delay={Math.min(i, 6) * 0.03} inView>
            <RuleEditor rule={r} onChange={(next) => edit(i, next)} />
          </BlurFade>
        ))}
      </div>
    </div>
  )
}
