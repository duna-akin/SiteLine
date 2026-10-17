import { lazy } from 'react'
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
const SitesPage = lazy(() => import('@/pages/SitesPage').then((m) => ({ default: m.SitesPage })))
const DataPage = lazy(() => import('@/pages/DataPage').then((m) => ({ default: m.DataPage })))
const PlaybookPage = lazy(() => import('@/pages/PlaybookPage').then((m) => ({ default: m.PlaybookPage })))

export default function App() {
  return (
    <DemoProvider>
      <DeskProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<HomePage />} />
              <Route path="inbound" element={<InboundPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route path="sites" element={<SitesPage />} />
              <Route path="review/:agreementId" element={<ReviewPage />} />
              <Route path="review/:agreementId/export" element={<ExportPage />} />
              <Route path="data" element={<DataPage />} />
              <Route path="playbook" element={<PlaybookPage />} />
              <Route path="priority" element={<Navigate to={{ pathname: '/playbook', hash: '#priority' }} replace />} />
              <Route path="portfolio" element={<Navigate to="/sites" replace />} />
              <Route path="evals" element={<Navigate to={{ pathname: '/data', hash: '#evals' }} replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </DeskProvider>
    </DemoProvider>
  )
}
