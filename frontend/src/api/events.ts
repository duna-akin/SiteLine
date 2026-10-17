// One shared EventSource on /api/events; components subscribe to named server events.
import { useEffect, useRef } from 'react'

import * as api from '@/api'
import type { TriageStepEvent } from '@/types'

type Handler = (data: unknown) => void

const handlers = new Map<string, Set<Handler>>()
const attached = new Set<string>()
let source: EventSource | null = null

function connect() {
  if (source) return source
  source = new EventSource('/api/events')
  attached.clear()
  for (const name of handlers.keys()) attach(name)
  return source
}

function attach(name: string) {
  if (!source || attached.has(name)) return
  attached.add(name)
  source.addEventListener(name, (e) => {
    const data: unknown = JSON.parse((e as MessageEvent<string>).data)
    handlers.get(name)?.forEach((h) => h(data))
  })
}

export function onServerEvent<T = unknown>(name: string, handler: (data: T) => void): () => void {
  if (!handlers.has(name)) handlers.set(name, new Set())
  handlers.get(name)!.add(handler as Handler)
  connect()
  attach(name)
  return () => handlers.get(name)?.delete(handler as Handler)
}

/** Subscribe for the lifetime of a component; the latest handler always runs. */
export function useServerEvent<T = unknown>(name: string, handler: (data: T) => void) {
  const ref = useRef(handler)
  useEffect(() => {
    ref.current = handler
  })
  useEffect(() => onServerEvent<T>(name, (d) => ref.current(d)), [name])
}

export interface TriageResult {
  agreementId: string
  triageSeconds: number
}

/**
 * Upload a redline and follow its job until it finishes. Events can arrive before the
 * upload response names the job, so they are buffered and replayed.
 */
export async function runTriage(
  file: File | null,
  options: api.UploadOptions,
  onStep: (e: TriageStepEvent) => void,
  onLog: (line: string) => void,
): Promise<TriageResult> {
  connect()
  let jobId: string | null = null
  const early: Array<[string, { jobId: string }]> = []
  let settle: { resolve: (r: TriageResult) => void; reject: (e: Error) => void } | null = null
  const done = new Promise<TriageResult>((resolve, reject) => {
    settle = { resolve, reject }
  })

  const handle = (name: string, data: { jobId: string }) => {
    if (jobId === null) {
      early.push([name, data])
      return
    }
    if (data.jobId !== jobId) return
    if (name === 'triage.step') onStep(data as TriageStepEvent)
    else if (name === 'triage.log') onLog((data as unknown as { line: string }).line)
    else if (name === 'triage.done') {
      const d = data as unknown as { agreement: { id: string }; triageSeconds: number }
      settle?.resolve({ agreementId: d.agreement.id, triageSeconds: d.triageSeconds })
    } else if (name === 'triage.failed') settle?.reject(new Error((data as unknown as { error: string }).error))
  }
  const offs = ['triage.step', 'triage.log', 'triage.done', 'triage.failed'].map((name) =>
    onServerEvent<{ jobId: string }>(name, (d) => handle(name, d)),
  )
  try {
    const res = await api.uploadRedline(file, options)
    jobId = res.jobId
    for (const [name, data] of early.splice(0)) handle(name, data)
    return await done
  } finally {
    offs.forEach((off) => off())
  }
}
