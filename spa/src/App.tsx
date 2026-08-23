import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useApp } from './context'
import Layout from './components/Layout'
import Login from './pages/Login'
import Forgot from './pages/Forgot'
import Reset from './pages/Reset'
import Dashboard from './pages/Dashboard'
import ResourceList from './pages/ResourceList'
import ResourceForm from './pages/ResourceForm'
import Calendar from './pages/Calendar'
import Routines from './pages/Routines'
import Reports from './pages/Reports'
import Profile from './pages/Profile'
import Alerts from './pages/Alerts'
import ChangePassword from './pages/ChangePassword'
import OpsHome from './pages/ops/OpsHome'
import OpsPortfolio from './pages/ops/OpsPortfolio'
import OpsProject from './pages/ops/OpsProject'
import OpsBoard from './pages/ops/OpsBoard'
import OpsRequests from './pages/ops/OpsRequests'
import OpsTime from './pages/ops/OpsTime'
import OpsNotifications from './pages/ops/OpsNotifications'
import OpsReports from './pages/ops/OpsReports'
import OpsToday from './pages/ops/OpsToday'
import OpsAI from './pages/ops/OpsAI'

function AppGate({ need, children }: { need: 'admin' | 'ops'; children: JSX.Element }) {
  const { user, app, setApp } = useApp()
  if (!user) return null
  if (!user.apps.includes(need)) return <Navigate to={user.apps.includes('ops') ? '/ops' : '/'} />
  if (app !== need) { setApp(need); return null }
  return children
}

export default function App() {
  const { user, loading, toasts } = useApp()
  const loc = useLocation()
  if (loading) return <div className="empty">Cargando…</div>
  const home = user?.apps?.includes('admin') ? '/' : '/ops'
  return (
    <>
      <Routes>
        <Route path="/login" element={user ? <Navigate to={home} /> : <Login />} />
        <Route path="/forgot-password" element={<Forgot />} />
        <Route path="/reset-password" element={<Reset />} />
        {!user && <Route path="*" element={<Navigate to="/login" state={{ from: loc.pathname }} />} />}
        {user && user.must_change_password && <Route path="*" element={<ChangePassword forced />} />}
        {user && !user.must_change_password && (
          <Route element={<Layout />}>
            <Route path="/profile" element={<Profile />} />
            <Route path="/change-password" element={<ChangePassword />} />
            <Route path="/" element={<AppGate need="admin"><Dashboard /></AppGate>} />
            <Route path="/calendar" element={<AppGate need="admin"><Calendar /></AppGate>} />
            <Route path="/routines" element={<AppGate need="admin"><Routines /></AppGate>} />
            <Route path="/reports" element={<AppGate need="admin"><Reports /></AppGate>} />
            <Route path="/alerts" element={<AppGate need="admin"><Alerts /></AppGate>} />
            <Route path="/r/:resource" element={<AppGate need="admin"><ResourceList /></AppGate>} />
            <Route path="/r/:resource/new" element={<AppGate need="admin"><ResourceForm /></AppGate>} />
            <Route path="/r/:resource/:id" element={<AppGate need="admin"><ResourceForm /></AppGate>} />
            <Route path="/ops" element={<AppGate need="ops"><OpsHome /></AppGate>} />
            <Route path="/ops/ai" element={<AppGate need="ops"><OpsAI /></AppGate>} />
            <Route path="/ops/today" element={<AppGate need="ops"><OpsToday /></AppGate>} />
            <Route path="/ops/portfolio" element={<AppGate need="ops"><OpsPortfolio /></AppGate>} />
            <Route path="/ops/projects/:id" element={<AppGate need="ops"><OpsProject /></AppGate>} />
            <Route path="/ops/board" element={<AppGate need="ops"><OpsBoard /></AppGate>} />
            <Route path="/ops/requests" element={<AppGate need="ops"><OpsRequests /></AppGate>} />
            <Route path="/ops/time" element={<AppGate need="ops"><OpsTime /></AppGate>} />
            <Route path="/ops/notifications" element={<AppGate need="ops"><OpsNotifications /></AppGate>} />
            <Route path="/ops/reports" element={<AppGate need="ops"><OpsReports /></AppGate>} />
            <Route path="/ops/client" element={<Navigate to="/ops" />} />
            <Route path="/ops/r/:resource" element={<AppGate need="ops"><ResourceList /></AppGate>} />
            <Route path="/ops/r/:resource/new" element={<AppGate need="ops"><ResourceForm /></AppGate>} />
            <Route path="/ops/r/:resource/:id" element={<AppGate need="ops"><ResourceForm /></AppGate>} />
            <Route path="*" element={<Navigate to={home} />} />
          </Route>
        )}
      </Routes>
      <div className="toasts">{toasts.map(t => <div key={t.id} className={'toast ' + t.kind}>{t.msg}</div>)}</div>
    </>
  )
}
