// One shared stream of server events from /api/events; components subscribe by event name.
//
// The stream is read with fetch rather than EventSource. EventSource hides the API's keep-alive
// comments, so it can't tell a quiet stream from a dead one, and a proxy (Vite in dev) can leave a
// dead stream open forever after the API restarts. Reading the bytes ourselves, any 40 s without
// even a keep-alive (sent every 15 s) counts as a drop, and every drop reconnects with backoff.
import { useEffect, useRef } from 'react'

import * as api from '@/api'
import type { SandboxPhaseEvent, TriageStepEvent } from '@/types'

type Handler = (data: unknown) => void

/** Fired locally (not by the server) when the stream comes back after a drop: refetch what may have been missed. */
export const RECONNECTED = 'stream.reconnected'

const STALE_MS = 40_000
const RETRY_MIN_MS = 1_000
const RETRY_MAX_MS = 30_000
const TRIAGE_TIMEOUT_MS = 5 * 60_000

const handlers = new Map<string, Set<Handler>>()
const lostListeners = new Set<() => void>()
let started = false
let lost = false
/** Aborts the stream in flight. */
let current: AbortController | null = null

const emit = (name: string, data: unknown) => handlers.get(name)?.forEach((h) => h(data))
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** One "event: name / data: json" block of the stream. Comments (keep-alives) have no event. */
function dispatch(block: string) {
  let name = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) name = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  if (!data.length) return
  try {
    emit(name, JSON.parse(data.join('\n')))
  } catch {
    /* not JSON: nothing subscribes to it */
  }
}

function dropped() {
  if (lost) return
  lost = true
  lostListeners.forEach((fn) => fn())
}

async function listen() {
  let retryMs = RETRY_MIN_MS
  for (;;) {
    const ctrl = new AbortController()
    current = ctrl
    let watchdog = setTimeout(() => ctrl.abort(), STALE_MS)
    const alive = () => {
      clearTimeout(watchdog)
      watchdog = setTimeout(() => ctrl.abort(), STALE_MS)
    }
    try {
      const res = await fetch('/api/events', { signal: ctrl.signal, cache: 'no-store', headers: { Accept: 'text/event-stream' } })
      if (!res.ok || !res.body) throw new Error(`events stream returned ${res.status}`)
      retryMs = RETRY_MIN_MS
      if (lost) {
        lost = false
        emit(RECONNECTED, {})
      }
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        alive()
        buffer += value.replace(/\r\n?/g, '\n')
        let end
        while ((end = buffer.indexOf('\n\n')) >= 0) {
          dispatch(buffer.slice(0, end))
          buffer = buffer.slice(end + 2)
        }
      }
    } catch {
      /* unreachable, an HTTP error, or a stream that went quiet: reconnect below */
    } finally {
      clearTimeout(watchdog)
      ctrl.abort()
    }
    dropped()
    await sleep(retryMs)
    retryMs = Math.min(retryMs * 2, RETRY_MAX_MS)
  }
}

function connect() {
  if (started) return
  started = true
  // A page kept in the back/forward cache keeps its fetch streams open, and six of them use up
  // the browser's connections to this host. Close the stream when the page is hidden; if the page
  // comes back, the listen loop reconnects and RECONNECTED refetches what it missed.
  window.addEventListener('pagehide', () => current?.abort())
  void listen()
}

export function onServerEvent<T = unknown>(name: string, handler: (data: T) => void): () => void {
  if (!handlers.has(name)) handlers.set(name, new Set())
  handlers.get(name)!.add(handler as Handler)
  connect()
  return () => handlers.get(name)?.delete(handler as Handler)
}

/** Called once each time the live connection drops. */
function onConnectionLost(fn: () => void): () => void {
  lostListeners.add(fn)
  return () => lostListeners.delete(fn)
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
 * upload response names the job, so they are buffered and replayed. Fails, rather than
 * waiting forever, if the live connection drops or no result arrives in time.
 */
export async function runTriage(
  file: File | null,
  options: api.UploadOptions,
  onStep: (e: TriageStepEvent) => void,
  onLog: (line: string) => void,
  onSandbox?: (e: SandboxPhaseEvent) => void,
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
    else if (name === 'triage.sandbox') onSandbox?.(data as SandboxPhaseEvent)
    else if (name === 'triage.done') {
      const d = data as unknown as { agreement: { id: string }; triageSeconds: number }
      settle?.resolve({ agreementId: d.agreement.id, triageSeconds: d.triageSeconds })
    } else if (name === 'triage.failed') settle?.reject(new Error((data as unknown as { error: string }).error))
  }
  const offs: Array<() => unknown> = ['triage.step', 'triage.log', 'triage.sandbox', 'triage.done', 'triage.failed'].map((name) =>
    onServerEvent<{ jobId: string }>(name, (d) => handle(name, d)),
  )
  offs.push(onConnectionLost(() =>
    settle?.reject(new Error('Lost the live connection to the Siteline API during triage. It may still finish: check Inbound in a moment.')),
  ))
  const timer = setTimeout(
    () => settle?.reject(new Error(`No result from the Siteline API after ${TRIAGE_TIMEOUT_MS / 60_000} minutes. Check that it is running, then try again.`)),
    TRIAGE_TIMEOUT_MS,
  )
  try {
    const res = await api.uploadRedline(file, options)
    jobId = res.jobId
    for (const [name, data] of early.splice(0)) handle(name, data)
    return await done
  } finally {
    clearTimeout(timer)
    offs.forEach((off) => off())
  }
}
