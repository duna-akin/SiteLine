export type Outcome = 'accept' | 'fallback' | 'escalate' | 'human_review' | 'novel'

export type ClauseType =
  | 'indemnification'
  | 'subject_injury'
  | 'publication'
  | 'confidentiality'
  | 'intellectual_property'
  | 'data_privacy'
  | 'payment_terms'
  | 'termination'
  | 'governing_law'

export type Owner = 'legal' | 'finance' | 'privacy'

export type ChangeKind = 'insertion' | 'deletion' | 'replacement' | 'comment'

export interface PlaybookRule {
  clauseType: ClauseType
  label: string
  owner: Owner
  standard: string
  fallback: string
  escalateWhen: string
  /** Open question carried over from the PRD, shown as a flag in the editor. */
  openQuestion?: string
}

export interface ExtractedValue {
  field: string
  value: string
  /** Verbatim quote Claude gave for this value, and whether it was found in the redline. */
  quote?: string
  verified?: boolean
}

/** A run of paragraph text: plain, inserted or deleted by the site. */
export interface Segment {
  type: 'text' | 'ins' | 'del'
  text: string
  author?: string
}

/** Reply digits the approver can text or press on a call. */
export type ApprovalReply = 1 | 2 | 3

export type ApprovalChannel = 'imessage' | 'voice'

/** How the text and call actually went out: through Photon / Twilio, or only to the on-screen phone. */
export interface ApprovalDelivery {
  delivery?: 'photon' | 'simulated'
  text?: string
  error?: string | null
  callDelivery?: 'twilio' | 'twilio+photon-sip' | 'simulated'
  callError?: string | null
}

export type ApprovalStatus =
  | { state: 'none' }
  | ({ state: 'sent'; sentAt: number } & ApprovalDelivery)
  | ({ state: 'calling'; sentAt: number; callStartedAt: number } & ApprovalDelivery)
  | ({ state: 'answered'; sentAt: number; reply: ApprovalReply; channel: ApprovalChannel; answeredAt: number } & ApprovalDelivery)

export interface Override {
  outcome: Outcome
  reason: string
  at: number
}

export interface PrecedentMatch {
  siteName: string
  agreementId: string
  siteNumber: string
  protocol: string
  label: string
  via: 'executed' | 'approver_reply'
  reply: ApprovalReply | null
  decidedAt: string
  /** Key of the final agreed document (S3 later) and where in it the term sits. */
  sourceKey?: string | null
  sourceSection?: string | null
  sourceQuote?: string | null
}

export interface Precedent {
  /** This institution's accepted terms that cover the site's ask, newest first. */
  sameSite: PrecedentMatch[]
  /** True when same-site precedent turned an escalation into an accept (rule PREC-A1). */
  downgraded: boolean
  originalRuleId: string | null
  originalRuleText: string | null
  summary: string
}

export interface Change {
  id: string
  index: number
  kind: ChangeKind
  section: string
  clauseType: ClauseType
  /** Text before the site's edit (empty for pure insertions). */
  original: string
  /** Text after the site's edit (empty for pure deletions). */
  revised: string
  siteComment?: string | null
  /** The paragraph as parsed from Word, with the site's tracked insertions and deletions. */
  segments?: Segment[]
  author: string
  extracted: ExtractedValue[]
  quote: string
  quoteVerified: boolean
  confidence: number
  outcome: Outcome
  ruleId: string
  ruleText: string
  owner: Owner
  /** What Siteline sends back in the counter-proposal ('' deletes the site's text). */
  counterText?: string | null
  /** What an approver's reply 2 ("counter with the fallback") sends back. */
  fallbackText?: string | null
  /** Past sponsor decisions on this clause, checked after the rules. */
  precedent?: Precedent | null
  rationale?: string | null
  novelIssue?: string | null
  /** Set when Claude extraction failed; the change goes to human review. */
  extractionError?: string | null
  cached?: boolean
}

export interface Decision extends Change {
  override?: Override
  approval: ApprovalStatus
}

export type AgreementStatus = 'triaging' | 'awaiting_approval' | 'ready_to_export' | 'sent_to_site' | 'executed'

export interface Agreement {
  id: string
  siteNumber: string
  siteName: string
  city: string
  status: AgreementStatus
  daysOpen: number
  changes: number
  stuckClauses: ClauseType[]
  outcomeMix: Record<Outcome, number>
  source: 'upload' | 'email'
  receivedAt: string
  fileName?: string
  triageSeconds?: number
  parser?: 'daytona' | 'local'
  sandboxId?: string | null
  /** Set once the agreement is confirmed: the stored final document (see api.sourceUrl). */
  finalDocumentKey?: string
}

export interface InboundEmail {
  id: string
  from: string
  siteName: string
  subject: string
  attachment: string
  receivedAt: string
  triaged: boolean
  agreementId?: string
}

export interface Approver {
  owner: Owner
  name: string
  role: string
  phone: string
}

export interface EvalMetric {
  key: string
  label: string
  description: string
  siteline: number
  baseline: number
  unit: '%' | 's'
  /** true when lower is better (unsafe accepts, latency). */
  lowerIsBetter: boolean
  target?: string
}

export interface EvalResults {
  runId: string
  harness: string
  datasetName: string
  labeledChanges: number
  shouldEscalate: number
  parallelSandboxes: number
  finishedAt: string
  metrics: EvalMetric[]
  /** Rows = labeled outcome, columns = Siteline outcome. */
  confusion: Record<Outcome, Record<Outcome, number>>
  baselineConfusion?: Record<Outcome, Record<Outcome, number>>
  model?: string
}

export interface Integrations {
  claude: boolean
  claudeModel: string
  daytona: boolean
  photon: boolean
  voice: boolean
  imap: boolean
  publicUrl: boolean
  approverPhonesReal: Record<Owner, boolean>
  noReplySeconds: number
}

export type StepState = 'active' | 'done' | 'skipped' | 'failed'

/** Live progress from the triage pipeline, streamed over /api/events. */
export interface TriageStepEvent {
  jobId: string
  agreementId: string
  step: ParseStepId
  state: StepState
  detail: string
  sponsor: 'Daytona' | 'Anthropic Claude' | null
  elapsedMs: number
}

export type ParseStepId = 'upload' | 'sandbox' | 'parse' | 'extract' | 'verify' | 'rules' | 'teardown'

export interface ParseStep {
  id: ParseStepId
  label: string
  detail: string
  sponsor?: 'Daytona' | 'Anthropic Claude'
  ms: number
}
