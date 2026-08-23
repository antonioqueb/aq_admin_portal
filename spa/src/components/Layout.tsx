import { useCallback, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api, ops } from '../api'
import { useApp } from '../context'
import CommandPalette from './CommandPalette'

const ROLE_LABEL: Record<string, string> = { direccion: 'Dirección', coordinacion: 'Coordinación administrativa', equipo: 'Equipo', consulta: 'Consulta' }
const OPS_ROLE_LABEL: Record<string, string> = { platform_owner: 'Propietario de plataforma', ops_director: 'Dirección de Operaciones / PMO', pm: 'Project Manager', functional_lead: 'Líder funcional', tech_lead: 'Líder técnico', consultant: 'Consultor funcional', developer: 'Desarrollador', qa: 'QA / Tester', support: 'Soporte / Guardia', collaborator: 'Colaborador', partner: 'Socio / subcontratista', client_sponsor: 'Patrocinador', client_po: 'Product Owner', client_validator: 'Validador departamental', client_requester: 'Solicitante', observer: 'Observador / Auditor', admin_liaison: 'Enlace administrativo' }
const initials = (n: string) => n.split(' ').filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase()
export const OpsIcon = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 2l8 4.5v9L12 20l-8-4.5v-9L12 2z" /><path d="M12 7v5l3.5 2" /><circle cx="12" cy="12" r="1" fill="currentColor" />
  </svg>
)

export default function Layout() {
  const { user, schema, logout, app, setApp, toast } = useApp()
  const [offline, setOffline] = useState(!navigator.onLine)
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)          // siempre oculto al abrir el portal
  const [palette, setPalette] = useState(false)
  const [count, setCount] = useState(0)
  const [activeProject, setActiveProject] = useState<{ id: number; name: string } | null>(() => { try { return JSON.parse(localStorage.getItem('aq_active_project') || 'null') } catch { return null } })
  const isOps = app === 'ops'
  const external = !!(isOps && (schema?.is_external || user?.is_external))
  useEffect(() => {
    if (isOps) ops.notifications().then(r => setCount(r.unread)).catch(() => {})
    else api.alerts().then(r => setCount(r.alerts.length)).catch(() => {})
  }, [loc.pathname, isOps])
  useEffect(() => { setOpen(false) }, [loc.pathname])
  useEffect(() => {
    const on = () => setOffline(false), off = () => setOffline(true)
    window.addEventListener('online', on); window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])
  useEffect(() => {
    if (!isOps) return
    let since: string | undefined
    const tick = async () => { try { const r = await ops.live(since); since = r.now; setCount(r.unread); r.fresh.forEach((n: any) => toast(`${n.title}`, n.priority === '4' ? 'err' : 'info')) } catch {} }
    const id = setInterval(tick, 45000)
    return () => clearInterval(id)
  }, [isOps, toast])
  useEffect(() => { const h = () => { try { setActiveProject(JSON.parse(localStorage.getItem('aq_active_project') || 'null')) } catch {} }; window.addEventListener('aq:project', h); return () => window.removeEventListener('aq:project', h) }, [])
  const onKey = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette(p => !p) }
    if (e.key === 'Escape') setOpen(false)
  }, [])
  useEffect(() => { window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [onKey])
  if (!user || !schema) return <div className="empty">Su cuenta no tiene acceso a esta aplicación.</div>
  const resources = Object.values(schema.resources).filter(r => r.section).sort((a, b) => a.order - b.order)
  const bySection = (key: string) => resources.filter(r => r.section === key)
  const switchApp = (a: 'admin' | 'ops') => { setApp(a); nav(a === 'ops' ? '/ops' : '/') }
  const titles: Record<string, string> = { '/': 'Tablero de Dirección', '/alerts': 'Alertas', '/calendar': 'Calendario', '/routines': 'Rutina', '/reports': 'Reportes', '/profile': 'Mi perfil', '/change-password': 'Contraseña',
    '/ops': external ? 'Portal del cliente' : 'Mi trabajo', '/ops/portfolio': 'Torre de control', '/ops/board': 'Tablero de trabajo', '/ops/requests': 'Solicitudes', '/ops/time': 'Tiempo y capacidad', '/ops/notifications': 'Notificaciones', '/ops/reports': 'Reportes operativos', '/ops/client': 'Portal del cliente' }
  const current = loc.pathname.includes('/r/') ? schema.resources[loc.pathname.split('/r/')[1].split('/')[0]]?.label : loc.pathname.startsWith('/ops/projects/') ? 'Centro de mando' : titles[loc.pathname]
  const roleLabel = isOps ? OPS_ROLE_LABEL[user.ops_role || ''] : ROLE_LABEL[user.role]
  return (
    <div className="shell" data-app={app}>
      <div className="bgfx" aria-hidden="true" />
      {offline && <div className="alert err" style={{ borderRadius: 0, margin: 0, textAlign: 'center' }}>Sin conexión: se muestra la última información conocida; los cambios se rechazarán hasta recuperar la red.</div>}
      <header className="topbar">
        <button className={'burger' + (open ? ' on' : '')} onClick={() => setOpen(o => !o)} aria-label="Menú"><span /><span /><span /></button>
        <a className="toplogo" href="#" onClick={e => { e.preventDefault(); nav(isOps ? '/ops' : '/') }}><img src="/aq_admin_portal/static/description/logo.png" alt="AlphaQueb" /></a>
        {user.apps.length > 1 ? (
          <div className="appswitch" role="tablist" aria-label="Aplicación">
            <button role="tab" aria-selected={!isOps} className={!isOps ? 'on' : ''} onClick={() => switchApp('admin')}>Administración</button>
            <button role="tab" aria-selected={isOps} className={isOps ? 'on' : ''} onClick={() => switchApp('ops')}><OpsIcon size={14} /> Operaciones</button>
          </div>
        ) : <div className="appname">{isOps ? <><OpsIcon size={14} /> Operaciones</> : 'Administración'}</div>}
        <div className="crumb">
          {isOps && <span className="ctx"><i>◆</i>{user.organization_name || 'AlphaQueb'}{activeProject && <> <i>/</i> <b onClick={() => nav(`/ops/projects/${activeProject.id}`)} style={{ cursor: 'pointer' }}>{activeProject.name}</b> <a href="#" onClick={e => { e.preventDefault(); localStorage.removeItem('aq_active_project'); window.dispatchEvent(new Event('aq:project')) }} title="Quitar proyecto activo">✕</a></>}</span>}
          {current && <><i>/</i><b>{current}</b></>}
        </div>
        <button className="palette-btn" onClick={() => setPalette(true)}><span>⌕</span> Buscar o ir a… <kbd>⌘K</kbd></button>
        <button className="bell" onClick={() => nav(isOps ? '/ops/notifications' : '/alerts')} aria-label="Notificaciones">{isOps ? '🔔' : '⚠'}{count > 0 && <em>{count > 99 ? '99+' : count}</em>}</button>
        <div className="avatar" title={user.name} onClick={() => nav('/profile')}>{initials(user.name)}<small>{roleLabel}</small></div>
      </header>

      <div className={'drawer-bg' + (open ? ' on' : '')} onClick={() => setOpen(false)} />
      <aside className={'drawer' + (open ? ' on' : '')} aria-hidden={!open}>
        <div className="drawer-head"><img src="/aq_admin_portal/static/description/logo.png" alt="" /><span className="badge primary">{isOps ? 'Operaciones' : 'Administración'}</span><button className="x" onClick={() => setOpen(false)} aria-label="Cerrar">✕</button></div>
        <nav>
          {!isOps && (<>
            <div className="section">Inicio</div>
            <NavLink to="/" end>Tablero de Dirección</NavLink>
            <NavLink to="/alerts">Alertas y vencimientos</NavLink>
            <NavLink to="/calendar">Calendario de obligaciones</NavLink>
            <NavLink to="/routines">Rutina diaria / semanal / mensual</NavLink>
            {schema.sections.filter(s => s.key !== 'inicio').map(s => { const items = bySection(s.key); if (!items.length && s.key !== 'ritmo') return null; return (
              <div key={s.key}><div className="section">{s.label}</div>{s.key === 'ritmo' && <NavLink to="/reports">Resúmenes ejecutivos</NavLink>}{items.map(r => <NavLink key={r.key} to={'/r/' + r.key}>{r.label}</NavLink>)}</div>) })}
          </>)}
          {isOps && external && (<>
            <div className="section">Su organización</div>
            <NavLink to="/ops" end>Inicio · estado de sus proyectos</NavLink>
            <NavLink to="/ops/r/requests">Mis solicitudes</NavLink>
            <NavLink to="/ops/r/acceptances">Validaciones y aprobaciones</NavLink>
            <NavLink to="/ops/r/milestones">Hitos y roadmap</NavLink>
            <NavLink to="/ops/r/meetings">Reuniones y minutas</NavLink>
            <NavLink to="/ops/r/decisions">Decisiones</NavLink>
            <NavLink to="/ops/r/incidents">Incidencias</NavLink>
            <NavLink to="/ops/r/documents">Documentación autorizada</NavLink>
            <NavLink to="/ops/notifications">Notificaciones</NavLink>
          </>)}
          {isOps && !external && (<>
            <div className="section">Operaciones</div>
            <NavLink to="/ops" end>Mi trabajo</NavLink>
            {user.ops_role !== 'admin_liaison' && <NavLink to="/ops/portfolio">Torre de control del portafolio</NavLink>}
            {user.ops_role !== 'admin_liaison' && <NavLink to="/ops/board">Tablero de trabajo (vistas)</NavLink>}
            {user.ops_role !== 'admin_liaison' && <NavLink to="/ops/requests">Bandeja de solicitudes</NavLink>}
            {user.ops_role !== 'admin_liaison' && <NavLink to="/ops/time">Tiempo y capacidad</NavLink>}
            <NavLink to="/ops/notifications">Centro de notificaciones</NavLink>
            {user.ops_role !== 'admin_liaison' && <NavLink to="/ops/reports">Reportes operativos</NavLink>}
            {schema.sections.map(s => { const items = bySection(s.key); if (!items.length) return null; return (
              <div key={s.key}><div className="section">{s.label}</div>{items.map(r => <NavLink key={r.key} to={'/ops/r/' + r.key}>{r.label}</NavLink>)}</div>) })}
          </>)}
        </nav>
        <div className="drawer-foot">
          <div><b>{user.name}</b><div className="dim">{roleLabel}</div></div>
          <div className="links"><a href="#" onClick={e => { e.preventDefault(); nav('/profile') }}>Mi perfil</a><a href="#" onClick={e => { e.preventDefault(); logout().then(() => nav('/login')) }}>Salir</a></div>
        </div>
      </aside>

      <main className="content fade"><Outlet /></main>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  )
}
