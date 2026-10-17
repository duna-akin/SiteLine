import type { Agreement, AgreementStatus, EvalResults, InboundEmail } from '@/types'

export const statusLabel: Record<AgreementStatus, string> = {
  triaging: 'Triaging',
  awaiting_approval: 'Awaiting approval',
  ready_to_export: 'Ready to export',
  sent_to_site: 'Sent to site',
  executed: 'Executed',
}

// Fictional sites and numbers for the demo.
export const agreements: Agreement[] = [
  {
    id: 'site-07', siteNumber: '07', siteName: 'Larkspur Cancer Institute', city: 'Madison, WI',
    status: 'awaiting_approval', daysOpen: 12, changes: 14,
    stuckClauses: ['indemnification', 'subject_injury', 'data_privacy', 'publication'],
    outcomeMix: { accept: 3, fallback: 4, escalate: 4, human_review: 2, novel: 1 },
    source: 'upload', receivedAt: '2026-10-16T09:12:00',
  },
  {
    id: 'site-03', siteNumber: '03', siteName: 'Bellwether Oncology Group', city: 'Raleigh, NC',
    status: 'ready_to_export', daysOpen: 41, changes: 9, stuckClauses: [],
    outcomeMix: { accept: 5, fallback: 3, escalate: 1, human_review: 0, novel: 0 },
    source: 'upload', receivedAt: '2026-09-05T14:30:00',
  },
  {
    id: 'site-11', siteNumber: '11', siteName: 'Ironwood University Medical Center', city: 'Tempe, AZ',
    status: 'awaiting_approval', daysOpen: 128, changes: 22, stuckClauses: ['intellectual_property', 'publication'],
    outcomeMix: { accept: 9, fallback: 6, escalate: 5, human_review: 1, novel: 1 },
    source: 'email', receivedAt: '2026-06-10T08:02:00',
  },
  {
    id: 'site-02', siteNumber: '02', siteName: 'Cedar Hollow Cancer Center', city: 'Boise, ID',
    status: 'executed', daysOpen: 74, changes: 6, stuckClauses: [],
    outcomeMix: { accept: 4, fallback: 2, escalate: 0, human_review: 0, novel: 0 },
    source: 'upload', receivedAt: '2026-08-03T11:45:00',
  },
  {
    id: 'site-15', siteNumber: '15', siteName: 'Tidewater Research Hospital', city: 'Norfolk, VA',
    status: 'triaging', daysOpen: 3, changes: 17, stuckClauses: [],
    outcomeMix: { accept: 0, fallback: 0, escalate: 0, human_review: 0, novel: 0 },
    source: 'email', receivedAt: '2026-10-13T16:20:00',
  },
  {
    id: 'site-09', siteNumber: '09', siteName: 'Granite Peak Health', city: 'Billings, MT',
    status: 'awaiting_approval', daysOpen: 167, changes: 19, stuckClauses: ['indemnification', 'governing_law', 'payment_terms'],
    outcomeMix: { accept: 7, fallback: 5, escalate: 6, human_review: 1, novel: 0 },
    source: 'upload', receivedAt: '2026-05-02T10:00:00',
  },
  {
    id: 'site-05', siteNumber: '05', siteName: 'Marrowstone Clinical Partners', city: 'Tacoma, WA',
    status: 'sent_to_site', daysOpen: 58, changes: 11, stuckClauses: ['confidentiality'],
    outcomeMix: { accept: 6, fallback: 3, escalate: 2, human_review: 0, novel: 0 },
    source: 'upload', receivedAt: '2026-08-19T09:30:00',
  },
  {
    id: 'site-13', siteNumber: '13', siteName: 'Saltmarsh Cancer Alliance', city: 'Savannah, GA',
    status: 'awaiting_approval', daysOpen: 96, changes: 15, stuckClauses: ['subject_injury', 'data_privacy'],
    outcomeMix: { accept: 6, fallback: 4, escalate: 3, human_review: 2, novel: 0 },
    source: 'email', receivedAt: '2026-07-12T13:10:00',
  },
  {
    id: 'site-01', siteNumber: '01', siteName: 'Northgate Regional Oncology', city: 'Duluth, MN',
    status: 'executed', daysOpen: 88, changes: 8, stuckClauses: [],
    outcomeMix: { accept: 5, fallback: 3, escalate: 0, human_review: 0, novel: 0 },
    source: 'upload', receivedAt: '2026-07-20T15:00:00',
  },
  {
    id: 'site-12', siteNumber: '12', siteName: 'Riverbend Cancer Care', city: 'Dayton, OH',
    status: 'triaging', daysOpen: 1, changes: 12, stuckClauses: [],
    outcomeMix: { accept: 0, fallback: 0, escalate: 0, human_review: 0, novel: 0 },
    source: 'email', receivedAt: '2026-10-15T19:41:00',
  },
]

export const inboundEmails: InboundEmail[] = [
  {
    id: 'em-1', from: 'contracts@riverbend.example', siteName: 'Riverbend Cancer Care (Site 12)',
    subject: 'NSO-417 CTA – our redline v2', attachment: 'NSO-417_CTA_Site12_v2.docx',
    receivedAt: '2026-10-15T19:41:00', triaged: false,
  },
  {
    id: 'em-2', from: 'osp@tidewater.example', siteName: 'Tidewater Research Hospital (Site 15)',
    subject: 'Re: CTA for NSO-417', attachment: 'Tidewater_CTA_markup.docx',
    receivedAt: '2026-10-13T16:20:00', triaged: false,
  },
  {
    id: 'em-3', from: 'legal@saltmarsh.example', siteName: 'Saltmarsh Cancer Alliance (Site 13)',
    subject: 'Updated agreement with comments', attachment: 'Saltmarsh_NSO417_redline.docx',
    receivedAt: '2026-07-12T13:10:00', triaged: true,
  },
]

export const INBOUND_ADDRESS = 'redlines@siteline.demo'

// Placeholder eval numbers for the UI. Replace with real numbers when the harness runs.
export const evalResults: EvalResults = {
  runId: 'eval-2026-10-17-0412',
  harness: 'Chalk Agent Evals',
  datasetName: 'cta-redlines-labeled-v1',
  labeledChanges: 150,
  shouldEscalate: 38,
  parallelSandboxes: 12,
  finishedAt: '2026-10-17T04:12:00',
  metrics: [
    {
      key: 'unsafe', label: 'Unsafe accept rate', lowerIsBetter: true, unit: '%', target: '0',
      description: 'Should escalate, but was accepted or countered',
      siteline: 0, baseline: 18.4,
    },
    {
      key: 'recall', label: 'Escalation recall', lowerIsBetter: false, unit: '%', target: 'As high as possible',
      description: 'Labeled escalations that were escalated',
      siteline: 94.7, baseline: 76.3,
    },
    {
      key: 'accuracy', label: 'Triage accuracy', lowerIsBetter: false, unit: '%', target: 'Report both',
      description: 'Outcome matches the label',
      siteline: 91.3, baseline: 72.0,
    },
    {
      key: 'quote', label: 'Quote pass rate', lowerIsBetter: false, unit: '%', target: '≈ 100%',
      description: 'Extracted quote found verbatim in the redline',
      siteline: 99.3, baseline: 81.3,
    },
    {
      key: 'latency', label: 'Upload → decision list', lowerIsBetter: true, unit: 's', target: '< 30 s',
      description: '14-change demo file, end to end',
      siteline: 18.4, baseline: 11.2,
    },
  ],
  confusion: {
    accept: { accept: 41, fallback: 2, escalate: 1, human_review: 1, novel: 0 },
    fallback: { accept: 2, fallback: 33, escalate: 1, human_review: 1, novel: 0 },
    escalate: { accept: 0, fallback: 0, escalate: 36, human_review: 2, novel: 0 },
    human_review: { accept: 0, fallback: 1, escalate: 1, human_review: 17, novel: 0 },
    novel: { accept: 0, fallback: 0, escalate: 0, human_review: 1, novel: 10 },
  },
}
