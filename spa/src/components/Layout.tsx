import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import CommandPalette from './CommandPalette'

const ROLE_LABEL: Record<string, string> = { direccion: 'Dirección', coordinacion: 'Coordinación administrativa', equipo: 'Equipo', consulta: 'Consulta' }
const initials = (n: string) => n.split(' ').filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase()

export default function Layout() {
  const { user, schema, logout } = useApp()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)          // siempre oculto al abrir el portal
  const [palette, setPalette] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  useEffect(() => { api.alerts().then(r => setAlertCount(r.alerts.length)).catch(() => {}) }, [loc.pathname])
  useEffect(() => { setOpen(false) }, [loc.pathname])  // se cierra al navegar
  const onKey = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(p => !p) }
    if (e.key === 'Escape') { setOpen(false) }
  }, [])
  useEffect(() => { window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [onKey])
  if (!user || !schema) return null
  const resources = Object.values(schema.resources).filter(r => r.section).sort((a, b) => a.order - b.order)
  const bySection = (key: string) => resources.filter(r => r.section === key)
  const current = loc.pathname.startsWith('/r/') ? schema.resources[loc.pathname.split('/')[2]]?.label : ({ '/': 'Tablero de Dirección', '/alerts': 'Alertas', '/calendar': 'Calendario', '/routines': 'Rutina', '/reports': 'Reportes', '/profile': 'Mi perfil', '/change-password': 'Contraseña' } as any)[loc.pathname]
  return (
    <div className="shell">
      <div className="bgfx" aria-hidden="true" />
      <header className="topbar">
        <button className={'burger' + (open ? ' on' : '')} onClick={() => setOpen(o => !o)} aria-label="Menú"><span /><span /><span /></button>
        <a className="toplogo" href="#" onClick={e => { e.preventDefault(); nav('/') }}><img src="/aq_admin_portal/static/description/logo.png" alt="AlphaQueb" /></a>
        <div className="crumb"><span>Control administrativo</span>{current && <><i>/</i><b>{current}</b></>}</div>
        <button className="palette-btn" onClick={() => setPalette(true)}><span>⌕</span> Buscar o ir a… <kbd>⌘K</kbd></button>
        <button className="bell" onClick={() => nav('/alerts')} aria-label="Alertas">⚠{alertCount > 0 && <em>{alertCount > 99 ? '99+' : alertCount}</em>}</button>
        <div className="avatar" title={user.name} onClick={() => nav('/profile')}>{initials(user.name)}<small>{ROLE_LABEL[user.role]}</small></div>
      </header>

      <div className={'drawer-bg' + (open ? ' on' : '')} onClick={() => setOpen(false)} />
      <aside className={'drawer' + (open ? ' on' : '')} aria-hidden={!open}>
        <div className="drawer-head"><img src="/aq_admin_portal/static/description/logo.png" alt="" /><button className="x" onClick={() => setOpen(false)} aria-label="Cerrar">✕</button></div>
        <nav>
          <div className="section">Inicio</div>
          <NavLink to="/" end>Tablero de Dirección</NavLink>
          <NavLink to="/alerts">Alertas y vencimientos {alertCount > 0 && <span className="badge err">{alertCount}</span>}</NavLink>
          <NavLink to="/calendar">Calendario de obligaciones</NavLink>
          <NavLink to="/routines">Rutina diaria / semanal / mensual</NavLink>
          {schema.sections.filter(s => s.key !== 'inicio').map(s => {
            const items = bySection(s.key)
            if (!items.length && s.key !== 'ritmo') return null
            return (
              <div key={s.key}>
                <div className="section">{s.label}</div>
                {s.key === 'ritmo' && <NavLink to="/reports">Resúmenes ejecutivos</NavLink>}
                {items.map(r => <NavLink key={r.key} to={'/r/' + r.key}>{r.label}</NavLink>)}
              </div>
            )
          })}
        </nav>
        <div className="drawer-foot">
          <div><b>{user.name}</b><div className="dim">{ROLE_LABEL[user.role]}</div></div>
          <div className="links"><a href="#" onClick={e => { e.preventDefault(); nav('/profile') }}>Mi perfil</a><a href="#" onClick={e => { e.preventDefault(); logout().then(() => nav('/login')) }}>Salir</a></div>
        </div>
      </aside>

      <main className="content fade"><Outlet /></main>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  )
}
