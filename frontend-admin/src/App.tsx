import React, { Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import AdminLayout from './components/AdminLayout'
import LoginPage from './pages/Login'
import { useAuthStore } from './stores/auth'

// 代码分割：页面级懒加载，减少首次加载 JS 体积
const DashboardPage = React.lazy(() => import('./pages/Dashboard'))
const UserManagePage = React.lazy(() => import('./pages/UserManage'))
const CardManagePage = React.lazy(() => import('./pages/CardManage'))
const AIModelPage = React.lazy(() => import('./pages/AIModel'))
const SystemLogPage = React.lazy(() => import('./pages/SystemLog'))
const StatsPage = React.lazy(() => import('./pages/Stats'))
const AnnouncementPage = React.lazy(() => import('./pages/Announcement'))

// 懒加载时的统一 loading
function PageLoader() {
  return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
}

function AuthGuard({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useAuthStore(s => s.isLoggedIn)
  const hydrated = useAuthStore(s => s._hydrated)

  // zustand persist 还未从 localStorage 恢复完 → 显示 loading
  if (!hydrated) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f2f5' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!isLoggedIn) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <AuthGuard>
            <AdminLayout />
          </AuthGuard>
        }
      >
        <Route path="/" element={<Suspense fallback={<PageLoader />}><DashboardPage /></Suspense>} />
        <Route path="/users" element={<Suspense fallback={<PageLoader />}><UserManagePage /></Suspense>} />
        <Route path="/cards" element={<Suspense fallback={<PageLoader />}><CardManagePage /></Suspense>} />
        <Route path="/ai-model" element={<Suspense fallback={<PageLoader />}><AIModelPage /></Suspense>} />
        <Route path="/logs" element={<Suspense fallback={<PageLoader />}><SystemLogPage /></Suspense>} />
        <Route path="/stats" element={<Suspense fallback={<PageLoader />}><StatsPage /></Suspense>} />
        <Route path="/announcements" element={<Suspense fallback={<PageLoader />}><AnnouncementPage /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
