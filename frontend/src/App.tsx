import React from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { ConfigProvider, theme, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppLayout from './components/Layout'
import LoginPage from './pages/Login'
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
import LogsPage from './pages/Logs'
import ContentCheckPage from './pages/ContentCheck'
import TopicRecommendPage from './pages/TopicRecommend'
import UserCenterPage from './pages/UserCenter'
import AdminPage from './pages/Admin'
import { useAuthStore } from './stores/auth'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useAuthStore(s => s.isLoggedIn)
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const role = useAuthStore(s => s.role)
  const isLoggedIn = useAuthStore(s => s.isLoggedIn)
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }
  if (role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

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
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/admin" element={
              <AdminRoute>
                <AppLayout>
                  <AdminPage />
                </AppLayout>
              </AdminRoute>
            } />
            <Route path="*" element={
              <ProtectedRoute>
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
                    <Route path="/logs" element={<LogsPage />} />
                    <Route path="/content-check" element={<ContentCheckPage />} />
                    <Route path="/topics" element={<TopicRecommendPage />} />
                    <Route path="/user-center" element={<UserCenterPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </AppLayout>
              </ProtectedRoute>
            } />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}
