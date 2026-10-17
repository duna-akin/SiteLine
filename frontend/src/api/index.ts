// Stub API layer. No function here performs a real network request:
// each returns mock data after a short simulated delay so the UI can be wired up
// before the backend exists. Swap the bodies for real calls later.
import { agreements, evalResults, inboundEmails } from '@/mocks/portfolio'
import { playbook } from '@/mocks/playbook'
import { SITE07, site07Changes } from '@/mocks/site07'
import type {
  Agreement,
  ApprovalReply,
  Change,
  EvalResults,
  InboundEmail,
  Outcome,
  PlaybookRule,
} from '@/types'

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
const clone = <T,>(value: T): T => structuredClone(value)

export interface UploadOptions {
  /** Skip the Daytona sandbox and parse locally (PRD fallback flag). */
  localParser: boolean
  /** Use the cached Claude extraction for the demo file. */
  useCache: boolean
}

export async function uploadRedline(file: File | null, options: UploadOptions) {
  // TODO: wire to backend — POST /api/agreements/upload (multipart .docx + options)
  await wait(300)
  return {
    agreementId: SITE07.agreementId,
    fileName: file?.name ?? SITE07.fileName,
    sandbox: options.localParser ? null : 'daytona-sbx-7f3a',
    cached: options.useCache,
  }
}

export async function getDecisions(agreementId: string): Promise<Change[]> {
  // TODO: wire to backend — GET /api/agreements/:agreementId/decisions
  await wait(250)
  return agreementId === SITE07.agreementId ? clone(site07Changes) : []
}

export async function overrideDecision(changeId: string, outcome: Outcome, reason: string) {
  // TODO: wire to backend — POST /api/decisions/:changeId/override { outcome, reason }
  await wait(250)
  return { changeId, outcome, reason, at: Date.now() }
}

export async function sendApprovalText(changeId: string, phone: string) {
  // TODO: wire to backend — POST /api/approvals/:changeId/text (Photon iMessage)
  await wait(200)
  return { changeId, phone, channel: 'imessage' as const, sentAt: Date.now() }
}

export async function recordApprovalReply(changeId: string, reply: ApprovalReply, channel: 'imessage' | 'voice') {
  // TODO: wire to backend — inbound Photon webhook, POST /api/approvals/:changeId/reply { reply, channel }
  await wait(150)
  return { changeId, reply, channel, answeredAt: Date.now() }
}

export async function placeApprovalCall(changeId: string, phone: string) {
  // TODO: wire to backend — POST /api/approvals/:changeId/call (Photon voice agent)
  await wait(200)
  return { changeId, phone, channel: 'voice' as const, startedAt: Date.now() }
}

export async function exportCounterProposal(agreementId: string) {
  // TODO: wire to backend — GET /api/agreements/:agreementId/export.docx (Word with comments)
  await wait(600)
  return { agreementId, fileName: `NSO-417_CTA_Site${SITE07.siteNumber}_counter-proposal.docx` }
}

export async function listAgreements(): Promise<Agreement[]> {
  // TODO: wire to backend — GET /api/agreements
  await wait(250)
  return clone(agreements)
}

export async function getPortfolio(): Promise<Agreement[]> {
  // TODO: wire to backend — GET /api/portfolio
  await wait(250)
  return clone(agreements.filter((a) => a.status !== 'executed'))
}

export async function getEvalResults(): Promise<EvalResults> {
  // TODO: wire to backend — GET /api/evals/latest (Chalk Agent Evals run)
  await wait(300)
  return clone(evalResults)
}

export async function startEvalRun() {
  // TODO: wire to backend — POST /api/evals/run (parallel Daytona sandboxes)
  await wait(300)
  return { runId: `eval-${Date.now()}` }
}

export async function getPlaybook(): Promise<PlaybookRule[]> {
  // TODO: wire to backend — GET /api/playbook
  await wait(200)
  return clone(playbook)
}

export async function savePlaybook(rules: PlaybookRule[]) {
  // TODO: wire to backend — PUT /api/playbook
  await wait(300)
  return { saved: rules.length, at: Date.now() }
}

export async function getInboundEmails(): Promise<InboundEmail[]> {
  // TODO: wire to backend — GET /api/inbound-emails (agent mailbox)
  await wait(200)
  return clone(inboundEmails)
}
