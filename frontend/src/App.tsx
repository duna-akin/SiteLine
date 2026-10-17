import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/siteline/AppShell'
import { InboxPage } from '@/pages/InboxPage'
import { DemoProvider } from '@/state/demo'

// Route-level code splitting: only the inbox ships in the first bundle.
const UploadPage = lazy(() => import('@/pages/UploadPage').then((m) => ({ default: m.UploadPage })))
const ReviewPage = lazy(() => import('@/pages/ReviewPage').then((m) => ({ default: m.ReviewPage })))
const ExportPage = lazy(() => import('@/pages/ExportPage').then((m) => ({ default: m.ExportPage })))
const PortfolioPage = lazy(() => import('@/pages/PortfolioPage').then((m) => ({ default: m.PortfolioPage })))
const EvalsPage = lazy(() => import('@/pages/EvalsPage').then((m) => ({ default: m.EvalsPage })))
const PlaybookPage = lazy(() => import('@/pages/PlaybookPage').then((m) => ({ default: m.PlaybookPage })))

function PageFallback() {
  return <div className="wrap py-16 text-muted" role="status">Loading…</div>
}

export default function App() {
  return (
    <DemoProvider>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<InboxPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route path="review/:agreementId" element={<ReviewPage />} />
              <Route path="review/:agreementId/export" element={<ExportPage />} />
              <Route path="portfolio" element={<PortfolioPage />} />
              <Route path="evals" element={<EvalsPage />} />
              <Route path="playbook" element={<PlaybookPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </DemoProvider>
  )
}
