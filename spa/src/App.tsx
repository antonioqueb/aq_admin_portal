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
import Users from './pages/Users'
import Profile from './pages/Profile'
import Alerts from './pages/Alerts'
import ChangePassword from './pages/ChangePassword'

export default function App() {
  const { user, loading, toasts } = useApp()
  const loc = useLocation()
  if (loading) return <div className="empty">Cargando…</div>
  return (
    <>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
        <Route path="/forgot-password" element={<Forgot />} />
        <Route path="/reset-password" element={<Reset />} />
        {!user && <Route path="*" element={<Navigate to="/login" state={{ from: loc.pathname }} />} />}
        {user && user.must_change_password && <Route path="*" element={<ChangePassword forced />} />}
        {user && !user.must_change_password && (
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/routines" element={<Routines />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/users" element={<Users />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/change-password" element={<ChangePassword />} />
            <Route path="/r/:resource" element={<ResourceList />} />
            <Route path="/r/:resource/new" element={<ResourceForm />} />
            <Route path="/r/:resource/:id" element={<ResourceForm />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Route>
        )}
      </Routes>
      <div className="toasts">{toasts.map(t => <div key={t.id} className={'toast ' + t.kind}>{t.msg}</div>)}</div>
    </>
  )
}
