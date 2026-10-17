import { Cloud, Database, HardDrive, ListChecks, Trash2 } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { Agreement, Integrations } from '@/types'

const PATHS = [
  'M58 60 C110 60 120 115 158 115',
  'M58 170 C110 170 120 115 158 115',
  'M202 115 C240 115 250 60 302 60',
  'M202 115 C240 115 250 170 302 170',
]

/** Where each agreement's data goes: email or upload → parser + OpenAI → precedent store and document store. */
export function DataMap({ integrations, agreements, className }: {
  integrations: Integrations | null
  agreements: Agreement[]
  className?: string
}) {
  const daytona = Boolean(integrations?.daytona)
  const postgres = integrations?.precedentStore === 'postgres'
  const s3 = integrations?.documentStore === 's3'
  const middle = daytona ? 'Sandbox + OpenAI' : 'Parser + OpenAI'
  const precedentLabel = postgres ? 'Postgres' : 'State file'
  const documentLabel = s3 ? 'S3' : 'Local disk'

  const executed = agreements.filter((a) => a.status === 'executed')
  const lastDoc = executed.map((a) => a.finalDocumentKey).filter(Boolean).at(-1)
  const withFigures = agreements.find((a) => a.priority?.figures.some((f) => f.verified))
  // One quote can state two figures ("48 subjects over 18 months"), so show each once
  const figureQuotes = [...new Set(withFigures?.priority?.figures.filter((f) => f.verified).map((f) => f.quote) ?? [])]

  return (
    <div className={cn('grid items-center gap-5 min-[1081px]:grid-cols-[minmax(0,420px)_minmax(0,1fr)]', className)}>
      <div className="well p-3">
        <svg
          viewBox="0 0 360 230"
          className="block h-auto w-full"
          role="img"
          aria-label={`Redlines arrive by email or upload, are parsed ${daytona ? 'in a sandbox that is then deleted' : 'on the server'}, OpenAI extracts the values, and results are saved to ${precedentLabel} and ${documentLabel}.`}
        >
          {PATHS.map((d) => <path key={d} className="beam" d={d} />)}
          <g fontFamily="var(--sans)" fontSize={12} fontWeight={500} fill="var(--ink)" textAnchor="middle">
            <g fill="var(--surface)" stroke="var(--line-strong)">
              <circle cx={36} cy={60} r={22} /><circle cx={36} cy={170} r={22} />
              <circle cx={180} cy={115} r={28} />
              <circle cx={324} cy={60} r={22} /><circle cx={324} cy={170} r={22} />
            </g>
            <text x={36} y={100}>Email</text>
            <text x={36} y={210}>Upload</text>
            <text x={180} y={162}>{middle}</text>
            <text x={324} y={100}>{precedentLabel}</text>
            <text x={324} y={210}>{documentLabel}</text>
          </g>
          <g fill="none" stroke="var(--ink-2)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <g transform="translate(26 50) scale(.84)"><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></g>
            <g transform="translate(26 160) scale(.84)"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" /></g>
            <g transform="translate(168 103)"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></g>
            <g transform="translate(314 50) scale(.84)"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" /></g>
            <g transform="translate(314 160) scale(.84)"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" /></g>
          </g>
        </svg>
      </div>
      <ul className="kept">
        <li>
          {s3 ? <Cloud aria-hidden className="size-4 shrink-0 text-faint" /> : <HardDrive aria-hidden className="size-4 shrink-0 text-faint" />}
          <div className="min-w-0"><b>Documents</b> are kept {s3 ? 'in S3' : 'on the server’s disk'}<code>{lastDoc ?? 'No final documents yet'}</code></div>
        </li>
        <li>
          <Database aria-hidden className="size-4 shrink-0 text-faint" />
          <div className="min-w-0"><b>Precedents</b> are kept {postgres ? 'in Postgres' : 'in the state file'}<code>{executed.length} confirmed agreement{executed.length === 1 ? '' : 's'} so far</code></div>
        </li>
        <li>
          <ListChecks aria-hidden className="size-4 shrink-0 text-faint" />
          <div className="min-w-0">
            <b>Priority figures</b> are saved with each agreement
            <code>{withFigures ? `Site ${withFigures.siteNumber} · ${figureQuotes.map((q) => `“${q}”`).join(' · ')}` : 'No figures read yet'}</code>
          </div>
        </li>
        <li className="gone">
          <Trash2 aria-hidden className="size-4 shrink-0" />
          <div className="min-w-0">
            {daytona ? <><b>Sandboxes</b> are deleted right after each parse</> : <><b>Parsing</b> runs on the server: no Daytona key is set</>}
          </div>
        </li>
      </ul>
    </div>
  )
}
