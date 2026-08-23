import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'

const ROLE_LABEL: Record<string, string> = { direccion: 'Dirección', coordinacion: 'Coordinación administrativa', equipo: 'Equipo', consulta: 'Consulta' }

export default function Layout() {
  const { user, schema, logout } = useApp()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  useEffect(() => { api.alerts().then(r => setAlertCount(r.alerts.length)).catch(() => {}) }, [])
  if (!user || !schema) return null
  const resources = Object.values(schema.resources).filter(r => r.section).sort((a, b) => a.order - b.order)
  const bySection = (key: string) => resources.filter(r => r.section === key)
  return (
    <div className="app">
      <aside className={'sidebar' + (open ? ' open' : '')}>
        <div className="brand"><img src="/aq_admin_portal/static/description/icon.png" width={30} height={30} style={{ borderRadius: 6 }} alt="" /><div>AlphaQueb<small>Portal de control administrativo</small></div></div>
        <div className="section">Inicio</div>
        <NavLink to="/" end onClick={() => setOpen(false)}>Tablero de Dirección</NavLink>
        <NavLink to="/alerts" onClick={() => setOpen(false)}>Alertas y vencimientos {alertCount > 0 && <span className="badge err" style={{ marginLeft: 6 }}>{alertCount}</span>}</NavLink>
        <NavLink to="/calendar" onClick={() => setOpen(false)}>Calendario de obligaciones</NavLink>
        <NavLink to="/routines" onClick={() => setOpen(false)}>Rutina diaria / semanal / mensual</NavLink>
        {schema.sections.filter(s => s.key !== 'inicio').map(s => {
          const items = bySection(s.key)
          if (!items.length && s.key !== 'ritmo' && s.key !== 'admin') return null
          return (
            <div key={s.key}>
              <div className="section">{s.label}</div>
              {s.key === 'ritmo' && <NavLink to="/reports" onClick={() => setOpen(false)}>Resúmenes ejecutivos</NavLink>}
              {items.map(r => <NavLink key={r.key} to={'/r/' + r.key} onClick={() => setOpen(false)}>{r.label}</NavLink>)}
              {s.key === 'admin' && user.role === 'direccion' && <NavLink to="/users" onClick={() => setOpen(false)}>Usuarios del portal</NavLink>}
            </div>
          )
        })}
        <div className="foot">
          <div><b>{user.name}</b></div>
          <div style={{ opacity: .7 }}>{ROLE_LABEL[user.role]}</div>
          <div style={{ marginTop: 6, display: 'flex', gap: 10 }}>
            <a href="#" onClick={e => { e.preventDefault(); nav('/profile') }}>Mi perfil</a>
            <a href="#" onClick={e => { e.preventDefault(); logout().then(() => nav('/login')) }}>Salir</a>
          </div>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <button className="btn secondary small menu-toggle" onClick={() => setOpen(o => !o)}>☰</button>
          <div className="title">AlphaQueb Consulting · Control administrativo</div>
          <span className="badge primary">{ROLE_LABEL[user.role]}</span>
        </div>
        <div className="content"><Outlet /></div>
      </div>
    </div>
  )
}
