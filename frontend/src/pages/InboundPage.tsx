import { useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, AtSign, Copy, RotateCw, Upload } from 'lucide-react'

import { EscalationQueue } from '@/components/siteline/EscalationQueue'
import { InboundFeed } from '@/components/siteline/InboundFeed'
import { openSites } from '@/components/siteline/priority-style'
import { SponsorChip } from '@/components/siteline/SponsorChip'
import { useHashScroll } from '@/hooks/useHashScroll'
import { byArrival } from '@/lib/sites'
import { useDemo } from '@/state/demo'
import { useDesk } from '@/state/desk'

const TARGET_DAYS = 90

function median(values: number[]) {
  const s = [...values].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}{note && <small>{note}</small>}</dd>
    </div>
  )
}

export function InboundPage() {
  const { notify, inboundAddress } = useDemo()
  const { agreements, emails, queue, imap, error, refresh } = useDesk()
  const navigate = useNavigate()
  const [over, setOver] = useState(false)
  const ready = Boolean(agreements && emails && queue)
  useHashScroll(ready)

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(inboundAddress)
      notify('Inbound address copied')
    } catch {
      notify(inboundAddress)
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) navigate('/upload', { state: { file } })
  }

  if (error && !ready) {
    return (
      <div className="wrap py-16">
        <div className="tile mx-auto max-w-xl text-center" role="alert">
          <h1 className="text-[26px]">Can’t reach the Siteline API</h1>
          <p className="mt-3 text-muted">{error}</p>
          <button type="button" className="btn btn-primary mt-5" onClick={refresh}><RotateCw aria-hidden className="size-4" /> Try again</button>
        </div>
      </div>
    )
  }

  const open = openSites(agreements ?? [])
  const waiting = (emails ?? []).filter((e) => !e.triaged).length

  return (
    <div className="wrap pb-12">
      <section className="hello pt-9">
        <span className="eyebrow">Intake</span>
        <h1>Inbound</h1>
        <p>
          Redlines that sites emailed or you uploaded, and every escalation still out with an approver.
          {ready && (waiting === 0 ? ' Nothing is waiting for triage.' : ` ${waiting} ${waiting === 1 ? 'redline is' : 'redlines are'} waiting for triage.`)}
        </p>
        <dl className="stats">
          <Kpi label="Awaiting triage" value={ready ? String(waiting) : '–'} />
          <Kpi label="Open agreements" value={ready ? String(open.length) : '–'} />
          <Kpi label="Median days open" value={ready && open.length ? `${median(open.map((a) => a.daysOpen))} d` : '–'} note={`target ${TARGET_DAYS} d`} />
          <Kpi label="Escalations unanswered" value={ready ? String(queue!.length) : '–'} />
        </dl>
      </section>

      <div className="grid grid-cols-1 gap-6 min-[1081px]:grid-cols-12">
        <section className="tile min-[1081px]:col-span-7" aria-labelledby="mail-h">
          <div className="tile-head">
            <h2 id="mail-h">Mailbox</h2>
            <span className="pill s-neutral">Agent inbox</span>
          </div>
          <p className="tile-sub">
            Sites email a redline straight to the agent and it lands here.{' '}
            {imap ? 'The mailbox is checked every 30 s.' : 'No mailbox is connected (IMAP), so these are the seeded emails.'}
          </p>
          <div className="well mb-4 flex items-center gap-2 py-1 pr-1 pl-3">
            <AtSign aria-hidden className="size-4 shrink-0 text-faint" />
            <code className="min-w-0 flex-1 truncate font-mono text-[13px] text-ink">{inboundAddress}</code>
            <button type="button" className="btn btn-secondary btn-sm" onClick={copyAddress} aria-label="Copy inbound address">
              <Copy aria-hidden className="size-4" /> Copy
            </button>
          </div>
          {!ready ? (
            <div className="flex flex-col gap-2.5" aria-hidden>
              {[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-[6px] bg-sunken" />)}
            </div>
          ) : emails!.length === 0 ? (
            <p className="empty">No redlines have come in yet.</p>
          ) : (
            <InboundFeed emails={byArrival(emails!)} />
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <SponsorChip sponsor="Daytona" label="Parsed in Daytona" />
            <SponsorChip sponsor="OpenAI" label="Extracted by OpenAI" />
          </div>
        </section>

        <section className="tile min-[1081px]:col-span-5" aria-labelledby="up-h">
          <div className="tile-head"><h2 id="up-h">Upload a redline</h2></div>
          <p className="tile-sub">A Word file with tracked changes and comments. Siteline hands back one decision per change.</p>
          <Link
            to="/upload"
            className="drop min-h-40 flex-col justify-center text-center"
            data-over={over}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
          >
            <Upload aria-hidden className="size-8 text-faint" />
            <span className="font-medium text-ink">Drop a .docx here, or choose a file</span>
            <span>The Site 07 demo file is one click away on the upload page.</span>
          </Link>
          <Link to="/upload" className="btn btn-primary mt-4 w-full">Go to upload <ArrowRight aria-hidden className="size-4" /></Link>
        </section>

        <section id="queue" className="tile scroll-mt-6 min-[1081px]:col-span-12" aria-labelledby="queue-h">
          <div className="tile-head">
            <h2 id="queue-h">Escalation queue <span className="badge tabular">{queue?.length ?? 0}</span></h2>
          </div>
          <p className="tile-sub">Most money at risk first, then oldest question. An approver’s bare “1”, “2” or “3” still answers the oldest text they got.</p>
          {!ready ? (
            <div className="h-24 animate-pulse rounded-[6px] bg-sunken" aria-hidden />
          ) : queue!.length === 0 ? (
            <p className="empty">Nothing is waiting on an approver.</p>
          ) : (
            <EscalationQueue items={queue!} />
          )}
        </section>
      </div>
    </div>
  )
}
