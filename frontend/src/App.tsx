import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, theme, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppLayout from './components/Layout'
import DashboardPage from './pages/Dashboard'
import AccountMatrixPage from './pages/AccountMatrix'
import DiscoveryPage from './pages/Discovery'
import ContentLibraryPage from './pages/ContentLibrary'
import DraftWorkshopPage from './pages/DraftWorkshop'
import ImageWorkshopPage from './pages/ImageWorkshop'
import PublishCenterPage from './pages/PublishCenter'
import AutomationPage from './pages/Automation'
import MonitorPage from './pages/Monitor'
import SettingsPage from './pages/Settings'
import AntiCrawlPage from './pages/AntiCrawl'
import TaskCenterPage from './pages/TaskCenter'
import KOLPage from './pages/KOL'
import QuickWorkPage from './pages/QuickWork'
import MyContentPage from './pages/MyContent'

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: { colorPrimary: '#ff4757', borderRadius: 8 },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <AppLayout>
            <Routes>
              <Route path="/" element={<QuickWorkPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/accounts" element={<AccountMatrixPage />} />
              <Route path="/discovery" element={<DiscoveryPage />} />
              <Route path="/content" element={<MyContentPage />} />
              <Route path="/library" element={<Navigate to="/content" replace />} />
              <Route path="/drafts" element={<Navigate to="/content" replace />} />
              <Route path="/images" element={<ImageWorkshopPage />} />
              <Route path="/publish" element={<PublishCenterPage />} />
              <Route path="/automation" element={<AutomationPage />} />
              <Route path="/monitor" element={<MonitorPage />} />
              <Route path="/kol" element={<KOLPage />} />
              <Route path="/anti-crawl" element={<AntiCrawlPage />} />
              <Route path="/tasks" element={<TaskCenterPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </AppLayout>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}
