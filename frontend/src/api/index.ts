// Client for the Siteline API (backend/). In dev, Vite proxies /api to http://127.0.0.1:8000.
import type {
  Agreement,
  ApprovalReply,
  Decision,
  EvalResults,
  InboundEmail,
  Integrations,
  Outcome,
  PlaybookRule,
} from '@/types'

export class ApiError extends Error {
  status: number
  details?: string[]
  constructor(status: number, message: string, details?: string[]) {
    super(message)
    this.status = status
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError(0, 'Can’t reach the Siteline API. Start it with `uv run siteline serve` in backend/.')
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    let details: string[] | undefined
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
      if (Array.isArray(body.errors)) {
        details = body.errors
        message = body.errors.join(' ')
      }
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message, details)
  }
  return res.json() as Promise<T>
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export interface Health {
  ok: boolean
  integrations: Integrations
  inboundAddress: string
}

export const getHealth = () => request<Health>('/health')

export interface UploadOptions {
  /** Skip the Daytona sandbox and parse locally (PRD fallback flag). */
  localParser: boolean
  /** Use the cached Claude extraction when one exists (the demo file ships with one). */
  useCache: boolean
}

/** Start triage. Progress arrives as triage.* events with this jobId. No file = the Site 07 demo redline. */
export async function uploadRedline(file: File | null, options: UploadOptions) {
  const form = new FormData()
  if (file) form.append('file', file)
  form.append('localParser', String(options.localParser))
  form.append('useCache', String(options.useCache))
  return request<{ jobId: string; fileName: string; sizeKb: number }>('/agreements/upload', { method: 'POST', body: form })
}

export const demoFileUrl = '/api/demo-file'

export const getAgreement = (agreementId: string) =>
  request<{ agreement: Agreement; decisions: Decision[] }>(`/agreements/${encodeURIComponent(agreementId)}`)

export const overrideDecision = (changeId: string, outcome: Outcome, reason: string) =>
  request<Decision>(`/decisions/${changeId}/override`, json('POST', { outcome, reason }))

export const clearOverride = (changeId: string) => request<Decision>(`/decisions/${changeId}/override`, { method: 'DELETE' })

export const sendApprovalText = (changeId: string) => request<Decision>(`/approvals/${changeId}/text`, { method: 'POST' })

/** The on-screen phone's reply (a real reply arrives through the Photon webhook instead). */
export const recordApprovalReply = (changeId: string, reply: ApprovalReply, channel: 'imessage' | 'voice') =>
  request<Decision>(`/approvals/${changeId}/reply`, json('POST', { reply, channel }))

export const placeApprovalCall = (changeId: string) => request<Decision>(`/approvals/${changeId}/call`, { method: 'POST' })

/** Download the Word counter-proposal and hand it to the browser. */
export async function exportCounterProposal(agreementId: string) {
  let res: Response
  try {
    res = await fetch(`/api/agreements/${encodeURIComponent(agreementId)}/export.docx`)
  } catch {
    throw new ApiError(0, 'Can’t reach the Siteline API.')
  }
  if (!res.ok) throw new ApiError(res.status, res.status === 404 ? 'Triage this agreement before exporting it.' : `Export failed (${res.status})`)
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'counter-proposal.docx'
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return { fileName: name }
}

/** Download link for a final agreed document, as cited by a precedent's sourceKey. */
export const sourceUrl = (key: string) => `/api/sources?key=${encodeURIComponent(key)}`

/** Confirm the agreement: the backend keeps the final document and saves its accepted terms as precedent. */
export const completeAgreement = (agreementId: string) =>
  request<{ agreement: Agreement; finalDocumentKey: string; precedentsSaved: number }>(
    `/agreements/${encodeURIComponent(agreementId)}/complete`,
    { method: 'POST' },
  )

export const listAgreements = () => request<Agreement[]>('/agreements')

export const getPortfolio = () => request<Agreement[]>('/portfolio')

export type EvalLatest =
  | { available: true; result: EvalResults; status: EvalStatus }
  | { available: false; status: EvalStatus; dataset: { name: string; labeledChanges: number; shouldEscalate: number } }

export interface EvalStatus {
  running: boolean
  runId: string | null
  error: string | null
}

export const getEvalResults = () => request<EvalLatest>('/evals/latest')

export const startEvalRun = (limit = 0) => request<{ started: boolean }>(`/evals/run?limit=${limit}`, { method: 'POST' })

export const getPlaybook = () => request<PlaybookRule[]>('/playbook')

export const savePlaybook = (rules: PlaybookRule[]) => request<{ saved: number; at: number }>('/playbook', json('PUT', rules))

export const getInboundEmails = () => request<{ address: string; imap: boolean; emails: InboundEmail[] }>('/inbound-emails')

export const triageEmail = (emailId: string) => request<{ agreement: Agreement }>(`/inbound-emails/${emailId}/triage`, { method: 'POST' })

export const resetDemo = () => request<{ ok: boolean }>('/demo/reset', { method: 'POST' })
