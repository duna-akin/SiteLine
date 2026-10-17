import { DataMap } from '@/components/siteline/DataMap'
import { EvalResults } from '@/components/siteline/EvalResults'
import { useHashScroll } from '@/hooks/useHashScroll'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'
import type { Integrations } from '@/types'

/** Each integration: whether it is live, and what Siteline does without it. */
function integrationRows(i: Integrations) {
  return [
    { name: 'OpenAI extraction', live: i.claude, on: `Model ${i.claudeModel}`, off: 'Cached extractions only; anything else goes to human review' },
    { name: 'Daytona sandboxes', live: i.daytona, on: 'One fresh sandbox per file, deleted after the parse', off: 'The local parser reads the file on the server' },
    { name: 'Photon texts', live: i.photon, on: 'Escalations text the approvers’ phones', off: 'Texts are simulated; record replies on Review' },
    { name: 'Twilio voice', live: i.voice, on: 'A call follows an unanswered text', off: 'Calls are simulated on screen' },
    { name: 'Inbound mailbox', live: i.imap, on: 'The IMAP mailbox is checked every 30 s', off: 'Seeded emails only' },
    { name: 'Precedent store', live: i.precedentStore === 'postgres', on: 'Postgres', off: 'The server’s state file' },
    { name: 'Document store', live: i.documentStore === 's3', on: 'S3-compatible bucket', off: 'The server’s disk' },
  ]
}

export function DataPage() {
  const { integrations } = useDemo()
  const { agreements } = useDesk()
  useHashScroll(Boolean(integrations))

  return (
    <div className="wrap pb-12">
      <section className="hello pt-9 pb-6">
        <span className="eyebrow">Governance</span>
        <h1>Data</h1>
        <p>Where each agreement’s data goes, which integrations are live, and how Siteline scores against an LLM-only baseline.</p>
      </section>

      <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
        <section className="tile min-[1081px]:col-span-12" aria-labelledby="map-h">
          <div className="tile-head"><h2 id="map-h">Where your data lives</h2></div>
          <p className="tile-sub">Redlines arrive by email or upload, are parsed, read by the model, and only the results are kept.</p>
          <DataMap integrations={integrations} agreements={agreements ?? []} />
        </section>

        <section className="tile min-[1081px]:col-span-12" aria-labelledby="int-h">
          <div className="tile-head"><h2 id="int-h">Integrations</h2></div>
          <p className="tile-sub">Every integration is optional. Without one, Siteline falls back as shown.</p>
          {!integrations ? (
            <div className="h-40 animate-pulse rounded-[6px] bg-sunken" aria-hidden />
          ) : (
            <ul className="grid gap-2.5 md:grid-cols-2">
              {integrationRows(integrations).map((r) => (
                <li key={r.name} className="flex items-start justify-between gap-3 rounded-[6px] border border-line bg-surface px-4 py-3">
                  <div className="min-w-0">
                    <p className="font-medium">{r.name}</p>
                    <p className="text-sm text-muted">{r.live ? r.on : r.off}</p>
                  </div>
                  <span className={`pill ${r.live ? 's-ok' : 's-neutral'}`}>{r.live ? 'Live' : 'Off'}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section id="evals" className="mt-14 scroll-mt-6" aria-labelledby="evals-h">
        <div className="hello pb-5">
          <h2 id="evals-h" className="text-[clamp(24px,2.6vw,30px)]">Siteline vs an LLM-only baseline</h2>
          <p>The safety eval runs both on every labeled change. The number that matters most: how often a change that needed an approver slipped through.</p>
        </div>
        <EvalResults />
      </section>
    </div>
  )
}
