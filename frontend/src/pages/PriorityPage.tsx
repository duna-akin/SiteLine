import { useCallback, useEffect, useId, useState } from 'react'
import { Eye, LoaderCircle, RotateCcw, Save } from 'lucide-react'

import * as api from '@/api'
import { priorityLabel, priorityTone, usd } from '@/components/siteline/priority-style'
import { BlurFade } from '@/components/ui/blur-fade'
import { useDemo } from '@/state/demo'
import type { PriorityBand, PriorityConfig, PrioritySettings, RedecidedChange } from '@/types'

const LEVELS = ['high', 'elevated', 'standard'] as const

const pct = (share: number) => `${Math.round(share * 100)}%`

/** The accept line a share of the gap gives this band (mirrors rules.band_limit). */
const bandLimit = (b: PriorityBand, share: number) => Math.round((b.standard + share * (b.floor - b.standard)) * 100) / 100

function NumberField({ label, value, onChange, min, max, prefix, suffix }: {
  label: string; value: number; onChange: (v: number) => void; min: number; max: number; prefix?: string; suffix?: string
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="text-sm font-bold">{label}</label>
      <div className="mt-1 flex items-center gap-2">
        {prefix && <span className="text-muted">{prefix}</span>}
        <input
          id={id}
          type="number"
          inputMode="numeric"
          className="field tabular"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {suffix && <span className="shrink-0 text-sm text-muted">{suffix}</span>}
      </div>
    </div>
  )
}

export function PriorityPage() {
  const { notify } = useDemo()
  const [settings, setSettings] = useState<PrioritySettings | null>(null)
  const [draft, setDraft] = useState<PriorityConfig | null>(null)
  const [preview, setPreview] = useState<RedecidedChange[] | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.getPrioritySettings().then(
      (s) => {
        setSettings(s)
        setDraft(s.config)
      },
      (e: Error) => setErrors([e.message]),
    )
  }, [])
  useEffect(load, [load])

  if (!settings || !draft) {
    return (
      <div className="wrap py-16 text-muted" role="status">
        {errors.length ? errors.join(' ') : <><LoaderCircle aria-hidden className="mr-2 inline size-5 animate-spin" /> Loading priority settings…</>}
      </div>
    )
  }

  const edit = (next: PriorityConfig) => {
    setDraft(next)
    setPreview(null)
    setErrors([])
  }
  const [first, second] = draft.daysBuckets
  const buckets = [`0–${first} days`, `${first + 1}–${second} days`, `over ${second} days`]
  const dirty = JSON.stringify(draft) !== JSON.stringify(settings.config)

  async function run(kind: 'preview' | 'save') {
    if (!draft) return
    setBusy(true)
    setErrors([])
    try {
      if (kind === 'preview') {
        setPreview((await api.previewPriorityConfig(draft)).changes)
      } else {
        const res = await api.savePriorityConfig(draft)
        setSettings(res)
        setDraft(res.config)
        setPreview(null)
        notify(`Priority settings saved · ${res.changes.length} open suggestion${res.changes.length === 1 ? '' : 's'} re-decided`)
      }
    } catch (e) {
      setErrors(e instanceof api.ApiError && e.details ? e.details : [e instanceof Error ? e.message : 'Request failed'])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="wrap py-10 sm:py-14">
      <BlurFade>
        <p className="eyebrow">Sponsor settings</p>
        <h1 className="mt-3 max-w-3xl text-4xl sm:text-6xl">
          Site <span className="text-yellow">priority</span>
        </h1>
        <p className="mt-4 max-w-3xl text-lg text-muted">
          Claude reads each contract’s enrollment target, enrollment period and per-patient amount, each with a verbatim quote.
          Siteline turns them into money at risk per week of delay (per-patient amount × patients per week, at {settings.weeksPerMonth.toFixed(2)} weeks a month),
          then widens only the accept line of the bands below by a share of the gap. Escalate floors never move, and every suggestion still needs a person’s confirmation.
        </p>
      </BlurFade>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex flex-col gap-6">
          <section aria-labelledby="levels-heading" className="panel p-5">
            <h2 id="levels-heading" className="text-2xl">Priority levels</h2>
            <p className="mt-1 text-sm text-muted">Money at risk per week of delay decides the level. A contract without usable figures is “unknown” and treated as standard.</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <NumberField label="High at or above" prefix="$" suffix="/ week" min={1} max={10_000_000} value={draft.thresholds.high}
                onChange={(v) => edit({ ...draft, thresholds: { ...draft.thresholds, high: v } })} />
              <NumberField label="Elevated at or above" prefix="$" suffix="/ week" min={1} max={10_000_000} value={draft.thresholds.elevated}
                onChange={(v) => edit({ ...draft, thresholds: { ...draft.thresholds, elevated: v } })} />
              <NumberField label="Planned enrollment (study)" suffix="patients" min={1} max={100_000} value={draft.plannedEnrollment}
                onChange={(v) => edit({ ...draft, plannedEnrollment: v })} />
            </div>
          </section>

          <section aria-labelledby="days-heading" className="panel p-5">
            <h2 id="days-heading" className="text-2xl">Days waiting</h2>
            <p className="mt-1 text-sm text-muted">Counted from when the site’s current redline arrived. The longer it waits, the more leniency the matrix can give.</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <NumberField label="First bucket ends at" suffix="days" min={1} max={3650} value={first}
                onChange={(v) => edit({ ...draft, daysBuckets: [v, second] })} />
              <NumberField label="Second bucket ends at" suffix="days" min={2} max={3650} value={second}
                onChange={(v) => edit({ ...draft, daysBuckets: [first, v] })} />
            </div>
          </section>

          <section aria-labelledby="matrix-heading" className="panel p-5">
            <h2 id="matrix-heading" className="text-2xl">Leniency: share of the gap</h2>
            <p className="mt-1 text-sm text-muted">
              Each cell is how far the accept line moves from the standard toward the escalate floor. Capped at {pct(settings.maxShare)}, so it never reaches the floor.
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="text-muted">
                  <tr>
                    <th scope="col" className="py-2 pr-3 font-bold">Priority</th>
                    {buckets.map((b) => <th key={b} scope="col" className="px-3 py-2 font-bold">{b}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {LEVELS.map((level) => (
                    <tr key={level} className="border-t border-line">
                      <th scope="row" className="py-3 pr-3">
                        <span className="inline-flex items-center gap-1.5 font-bold">
                          <span aria-hidden className="size-2 rounded-full" style={{ background: priorityTone[level] }} />
                          {priorityLabel[level]}
                        </span>
                      </th>
                      {draft.leniency[level].map((share, i) => (
                        <td key={i} className="px-3 py-3">
                          <input
                            type="range"
                            min={0}
                            max={settings.maxShare}
                            step={0.05}
                            value={share}
                            aria-label={`${priorityLabel[level]}, ${buckets[i]}: share of the gap`}
                            className="w-full accent-[var(--yellow)]"
                            onChange={(e) => {
                              const row = [...draft.leniency[level]] as [number, number, number]
                              row[i] = Number(e.target.value)
                              edit({ ...draft, leniency: { ...draft.leniency, [level]: row } })
                            }}
                          />
                          <span className="tabular font-bold">{pct(share)}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section aria-labelledby="bands-heading" className="panel p-5">
            <h2 id="bands-heading" className="text-2xl">What a high-priority site gets</h2>
            <p className="mt-1 text-sm text-muted">Accept lines under the high-priority row above. Standards and floors are fixed in the rules engine.</p>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead className="text-muted">
                  <tr>
                    <th scope="col" className="py-2 pr-3 font-bold">Band</th>
                    <th scope="col" className="px-3 py-2 font-bold">Standard</th>
                    {buckets.map((b) => <th key={b} scope="col" className="px-3 py-2 font-bold">{b}</th>)}
                    <th scope="col" className="px-3 py-2 font-bold">Escalate floor</th>
                  </tr>
                </thead>
                <tbody>
                  {settings.bands.map((b) => (
                    <tr key={b.field} className="border-t border-line">
                      <th scope="row" className="py-3 pr-3 font-bold">{b.label} <code className="ml-1 text-xs text-muted">{b.ruleId}</code></th>
                      <td className="px-3 py-3 tabular">{b.standard}{b.unit}</td>
                      {draft.leniency.high.map((share, i) => (
                        <td key={i} className="px-3 py-3 tabular font-bold">{bandLimit(b, share)}{b.unit}</td>
                      ))}
                      <td className="px-3 py-3 tabular text-red">{b.floor}{b.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <aside className="flex h-fit flex-col gap-4 lg:sticky lg:top-24">
          <div className="panel p-5">
            <h2 className="text-2xl">Apply</h2>
            <p className="mt-1 text-sm text-muted">Only unconfirmed suggestions change; confirmed ones stay as they are.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className="btn btn-ghost" disabled={busy || !dirty} onClick={() => void run('preview')}>
                <Eye aria-hidden className="size-4" /> Preview
              </button>
              <button type="button" className="btn btn-primary" disabled={busy || !dirty} onClick={() => void run('save')}>
                {busy ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : <Save aria-hidden className="size-4" />} Save
              </button>
              <button type="button" className="btn btn-ghost" disabled={busy || !dirty} onClick={() => edit(settings.config)}>
                <RotateCcw aria-hidden className="size-4" /> Undo edits
              </button>
            </div>
            {errors.length > 0 && (
              <ul role="alert" className="mt-3 rounded-2xl border border-red/50 bg-red/10 px-4 py-3 text-sm">
                {errors.map((e) => <li key={e}>{e}</li>)}
              </ul>
            )}
            {preview && (
              <div className="mt-4" aria-live="polite">
                <p className="font-bold">
                  {preview.length} open decision{preview.length === 1 ? '' : 's'} across {new Set(preview.map((c) => c.agreementId)).size} site{new Set(preview.map((c) => c.agreementId)).size === 1 ? '' : 's'} would change
                </p>
                <ul className="mt-2 flex flex-col gap-1.5 text-sm">
                  {preview.map((c) => (
                    <li key={c.changeId} className="rounded-xl border border-line px-3 py-2">
                      <span className="font-bold">{c.agreementId.replace('site-', 'Site ')}</span> · {c.section}:{' '}
                      <code className="text-xs">{c.from.ruleId}</code> → <code className="text-xs">{c.to.ruleId}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="panel p-5">
            <h2 className="text-2xl">Change log</h2>
            {settings.log.length === 0 ? (
              <p className="mt-1 text-sm text-muted">No changes yet. Defaults come from backend/data/priority_config.json.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2 text-sm">
                {settings.log.map((entry) => (
                  <li key={entry.at} className="border-l-2 border-line pl-3">
                    <span className="font-bold">{entry.by}</span> <span className="text-muted">· {new Date(entry.at).toLocaleString()}</span>
                    <span className="block text-xs text-muted">
                      High {usd(entry.old.thresholds.high)} → {usd(entry.new.thresholds.high)} · elevated {usd(entry.old.thresholds.elevated)} → {usd(entry.new.thresholds.elevated)}
                      {JSON.stringify(entry.old.leniency) !== JSON.stringify(entry.new.leniency) && ' · leniency matrix changed'}
                      {JSON.stringify(entry.old.daysBuckets) !== JSON.stringify(entry.new.daysBuckets) && ` · buckets ${entry.old.daysBuckets.join('/')} → ${entry.new.daysBuckets.join('/')}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
