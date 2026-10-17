import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/siteline/AppShell'
import { HomePage } from '@/pages/HomePage'
import { DemoProvider } from '@/state/demo'
import { DeskProvider } from '@/state/desk'

// Route-level code splitting: only Home ships in the first bundle.
const InboundPage = lazy(() => import('@/pages/InboundPage').then((m) => ({ default: m.InboundPage })))
const UploadPage = lazy(() => import('@/pages/UploadPage').then((m) => ({ default: m.UploadPage })))
const ReviewPage = lazy(() => import('@/pages/ReviewPage').then((m) => ({ default: m.ReviewPage })))
const ExportPage = lazy(() => import('@/pages/ExportPage').then((m) => ({ default: m.ExportPage })))
const PortfolioPage = lazy(() => import('@/pages/PortfolioPage').then((m) => ({ default: m.PortfolioPage })))
const EvalsPage = lazy(() => import('@/pages/EvalsPage').then((m) => ({ default: m.EvalsPage })))
const PlaybookPage = lazy(() => import('@/pages/PlaybookPage').then((m) => ({ default: m.PlaybookPage })))
const PriorityPage = lazy(() => import('@/pages/PriorityPage').then((m) => ({ default: m.PriorityPage })))

function PageFallback() {
  return <div className="wrap py-16 text-muted" role="status">Loading…</div>
}

export default function App() {
  return (
    <DemoProvider>
      <DeskProvider>
        <BrowserRouter>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<HomePage />} />
                <Route path="inbound" element={<InboundPage />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="sites" element={<PortfolioPage />} />
                <Route path="review/:agreementId" element={<ReviewPage />} />
                <Route path="review/:agreementId/export" element={<ExportPage />} />
                <Route path="data" element={<EvalsPage />} />
                <Route path="playbook" element={<PlaybookPage />} />
                <Route path="priority" element={<PriorityPage />} />
                <Route path="portfolio" element={<Navigate to="/sites" replace />} />
                <Route path="evals" element={<Navigate to="/data" replace />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </DeskProvider>
    </DemoProvider>
  )
}
