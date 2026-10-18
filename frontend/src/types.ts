export type Outcome = 'accept' | 'counter' | 'escalate' | 'human_review'

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

/** A number a playbook position decides by, e.g. the 10% standard start-up fee. */
export interface PlaybookLimit {
  value: number
  unit: string
  label: string
}

export interface PlaybookRule {
  id: string
  outcome: Exclude<Outcome, 'human_review'>
  /** Template; {name} placeholders name the position's limits. */
  when: string
}

/** One negotiable issue: the form's standard, the counter and the escalation trigger, all enforced. */
export interface PlaybookPosition {
  id: string
  issue: string
  /** Where the form agreement states it, e.g. "§6.3". */
  form: string
  fields: string[]
  standard: string
  counter: string
  escalate: string
  rationale: string
  talkingPoints: string[]
  limits: Record<string, PlaybookLimit>
  rules: PlaybookRule[]
}

export interface PlaybookClause {
  clauseType: ClauseType
  label: string
  owner: Owner
  summary: string
  positions: PlaybookPosition[]
}

export interface Playbook {
  name: string
  clauses: PlaybookClause[]
}

export interface PlaybookLogEntry {
  at: number
  by: string
  summary: string
  /** Open suggestions the save or reset re-decided. */
  moved?: number
}

/** An open suggestion a playbook edit would re-decide. */
export interface PlaybookChange {
  agreementId: string
  changeId: string
  section: string
  from: { outcome: Outcome; ruleId: string; owner: Owner }
  to: { outcome: Outcome; ruleId: string; owner: Owner }
}

export interface PlaybookSettings {
  playbook: Playbook
  log: PlaybookLogEntry[]
  /** Rule IDs older decisions may carry → the rule that replaced each. */
  aliases: Record<string, string>
}

export interface ExtractedValue {
  field: string
  value: string
  /** Verbatim quote the model gave for this value, and whether it was found in the redline. */
  quote?: string
  verified?: boolean
}

/** A run of paragraph text: plain, inserted or deleted by the site. */
export interface Segment {
  type: 'text' | 'ins' | 'del'
  text: string
  author?: string
}

/** One paragraph of the whole redline, changed or not, as parsed from Word. */
export interface DocParagraph {
  index: number
  /** Word style ID: 'Title', 'Heading1', 'Heading2' or '' for body text. */
  style: string
  heading: boolean
  segments: Segment[]
}

/** Reply digits the approver can text or press on a call. */
export type ApprovalReply = 1 | 2 | 3

export type ApprovalChannel = 'imessage' | 'voice'

/** How the text and call actually went out: through Photon / Twilio, or only simulated in Siteline. */
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
  /** Where the paragraph sits in the whole document (DocParagraph.index). */
  paragraph?: number
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
  /** Set when extraction failed; the change goes to human review. */
  extractionError?: string | null
  cached?: boolean
}

export type PriorityLevel = 'high' | 'elevated' | 'standard' | 'unknown'

/** One figure the model read from the contract (or the study plan), with its quote. */
export interface PriorityFigure {
  field: 'enrollment_target_subjects' | 'enrollment_period_months' | 'per_patient_amount_usd'
  value: string
  quote: string
  verified: boolean
}

/** Value lost per week the site is held up (risk-adjusted NPV of the trial delay), computed by the backend. */
export interface SitePriority {
  level: PriorityLevel
  moneyAtRiskPerWeek: number | null
  patientsPerWeek?: number
  shareOfPlanned?: number
  shareOfEnrollmentRate?: number
  trialDelayDaysPerWeek?: number
  trialDayValueUsd?: number
  lostSalesPerTrialDayUsd?: number
  trialCostPerDayUsd?: number
  reason: string
  source?: 'contract' | 'study plan' | null
  figures: PriorityFigure[]
}

/** The leniency a decision was made with: share of the gap between standard and escalate floor. */
export interface Leniency {
  level: PriorityLevel
  share: number
  days: number
  bucket: string
  moneyAtRiskPerWeek: number | null
}

export interface Confirmation {
  by: string
  at: number
}

export interface Decision extends Change {
  override?: Override
  approval: ApprovalStatus
  leniency?: Leniency | null
  /** A person signed off on this suggestion; export waits for every one. */
  confirmation?: Confirmation | null
}

export interface PriorityConfig {
  plannedEnrollment: number
  /** Value lost per week of site delay: at or above high → high, at or above elevated → elevated. */
  thresholds: { high: number; elevated: number }
  /** Upper bounds of the first two days-waiting buckets, e.g. [30, 90]. */
  daysBuckets: [number, number]
  /** Share of the gap per level, one per days-waiting bucket, each 0 to maxShare. */
  leniency: Record<'high' | 'elevated' | 'standard', [number, number, number]>
  /** Inputs to the value of one day of trial delay (see backend priority.py). */
  costOfDelay: CostOfDelay
}

export interface CostOfDelay {
  trialEnrollmentMonths: number
  salesPerDayUsd: number
  probabilityOfApproval: number
  yearsToLaunch: number
  discountRate: number
  trialCostPerDayUsd: number
}

export interface PriorityBand {
  field: string
  clause: ClauseType
  label: string
  unit: string
  standard: number
  floor: number
  ruleId: string
}

export interface PriorityConfigChange {
  at: number
  by: string
  old: PriorityConfig
  new: PriorityConfig
}

export interface PrioritySettings {
  config: PriorityConfig
  bands: PriorityBand[]
  maxShare: number
  weeksPerMonth: number
  /** Where each cost-of-delay default comes from. */
  costSources: Record<keyof CostOfDelay, string>
  log: PriorityConfigChange[]
}

export interface RedecidedChange {
  agreementId: string
  changeId: string
  section: string
  from: { outcome: Outcome; ruleId: string }
  to: { outcome: Outcome; ruleId: string }
}

export interface EscalationQueueItem {
  agreementId: string
  siteNumber: string
  siteName: string
  priority: Pick<SitePriority, 'level' | 'moneyAtRiskPerWeek' | 'reason'>
  decision: Decision
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
  priority?: SitePriority
  /** Days since the site's current redline arrived (drives leniency with the priority). */
  daysWaiting?: number
  /** Decisions a person has signed off on, and suggestions still waiting for that. */
  confirmed?: number
  toConfirm?: number
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

/** Approvers are shown by role, never by name. */
export interface Approver {
  owner: Owner
  /** "Legal approver" */
  title: string
  /** The function behind the role, e.g. "Contracts counsel" */
  role: string
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
  /** Where confirmed agreements' precedents and final documents are kept. */
  precedentStore?: 'postgres' | 'json'
  documentStore?: 's3' | 'local'
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
  sponsor: 'Daytona' | 'OpenAI' | null
  elapsedMs: number
}

export type ParseStepId = 'upload' | 'sandbox' | 'parse' | 'extract' | 'verify' | 'rules' | 'teardown'

export interface ParseStep {
  id: ParseStepId
  label: string
  detail: string
  sponsor?: 'Daytona' | 'OpenAI'
  ms: number
}
