import { EvalResults } from '@/components/siteline/EvalResults'
import { useHashScroll } from '@/hooks/useHashScroll'
import { useDemo } from '@/state/demo'

export function DataPage() {
  const { integrations } = useDemo()
  useHashScroll(Boolean(integrations))

  // Each store: whether it is live, what it holds, and where that goes without it
  const stores = [
    {
      name: 'Daytona sandbox',
      live: Boolean(integrations?.daytona),
      holds: 'Each file is opened in a fresh sandbox with network access blocked. Only the parsed text reaches the model, then the sandbox is deleted.',
      off: 'Off: files are parsed on the server',
    },
    {
      name: 'Postgres',
      live: integrations?.precedentStore === 'postgres',
      holds: 'Confirmed terms from executed agreements, kept as precedents',
      off: 'Off: precedents are kept in the server’s state file',
    },
    {
      name: 'S3',
      live: integrations?.documentStore === 's3',
      holds: 'Document storage for the agreements’ files',
      off: 'Off: files are kept on the server’s disk',
    },
  ]

  return (
    <div className="wrap pb-12">
      <section id="evals" className="scroll-mt-6" aria-labelledby="evals-h">
        <div className="hello pt-9 pb-6">
          <span className="eyebrow">Data · Governance</span>
          <h1 id="evals-h">Siteline vs an LLM-only baseline</h1>
          <p>The safety eval runs both on every labeled change. The number that matters most: how often a change that needed an approver slipped through.</p>
        </div>
        <EvalResults />
      </section>

      <section className="tile mt-14" aria-labelledby="store-h">
        <div className="tile-head"><h2 id="store-h">Where your data lives</h2></div>
        {!integrations ? (
          <div className="h-24 animate-pulse rounded-[6px] bg-sunken" aria-hidden />
        ) : (
          <ul className="grid gap-2.5 md:grid-cols-3">
            {stores.map((s) => (
              <li key={s.name} className="flex items-start justify-between gap-3 rounded-[6px] border border-line bg-surface px-4 py-3">
                <div className="min-w-0">
                  <p className="font-medium">{s.name}</p>
                  <p className="text-sm text-muted">{s.holds}</p>
                  {!s.live && <p className="mt-1.5 text-sm text-faint">{s.off}</p>}
                </div>
                <span className={`pill ${s.live ? 's-ok' : 's-neutral'}`}>{s.live ? 'Live' : 'Off'}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
