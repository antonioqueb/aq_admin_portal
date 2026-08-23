import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, fmtDate } from '../api'
import { useApp } from '../context'

/** Google Workspace: Gmail, Calendar, Meet, Drive, Docs y Sheets conectados a ambos portales. */
export default function GoogleIntegration() {
  const { user, toast, app, base } = useApp()
  const [sp] = useSearchParams()
  const [st, setSt] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const canConnect = user?.role === 'direccion' || user?.ops_role === 'platform_owner'
  const load = useCallback(() => api.get('/google/status').then(setSt).catch((e: any) => toast(e.message, 'err')), [toast])
  useEffect(() => { load(); if (sp.get('connected')) toast('Google conectado correctamente', 'ok'); if (sp.get('error')) toast('Google: ' + sp.get('error'), 'err') }, [load])  // eslint-disable-line
  const connect = async () => { try { const r = await api.get('/google/auth-url'); window.location.href = r.url } catch (e: any) { toast(e.message, 'err') } }
  const sync = async () => { setBusy(true); try { setSt(await api.post('/google/sync')); toast('Sincronización completada', 'ok') } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) } }
  const upd = async (a: any, vals: any) => { try { setSt(await api.put(`/google/accounts/${a.id}`, vals)) } catch (e: any) { toast(e.message, 'err') } }
  if (!st) return <div className="empty">Consultando…</div>
  return (
    <div>
      <div className="hero"><div><div className="tag">Integraciones autorizadas</div><h1>Google Workspace</h1><div className="pulse">Gmail · Calendar · Meet · Drive · Docs · Sheets → {st.pending.ops} pendientes en Operaciones · {st.pending.admin} en Administración</div></div>
        <div className="toolbar" style={{ margin: 0 }}>{canConnect && <button className="btn" onClick={connect}>{st.accounts.some((a: any) => a.state === 'conectada') ? 'Reconectar / otra cuenta' : 'Conectar cuenta de Google'}</button>}<button className="btn secondary" disabled={busy} onClick={sync}>{busy ? 'Sincronizando…' : 'Sincronizar ahora'}</button></div></div>
      {(!st.client_id_configured || !st.client_secret_configured) && <div className="alert err">Falta configuración OAuth: {!st.client_id_configured && 'GOOGLE_CLIENT_ID '} {!st.client_secret_configured && 'GOOGLE_CLIENT_SECRET'} — defínalos como variable de entorno del servidor o parámetro del sistema (sin comillas).</div>}
      <div className="grid cols-2">
        {st.accounts.map((a: any) => (
          <div className="card" key={a.id}>
            <h3>{a.name}</h3>
            <p><span className={'badge ' + (a.state === 'conectada' ? 'ok' : a.state === 'error' ? 'err' : '')}>{a.state}</span> {a.email && <b style={{ marginLeft: 8 }}>{a.email}</b>}</p>
            {a.last_error && <div className="alert err">{a.last_error}</div>}
            <div className="checklist">
              <label><input type="checkbox" checked={a.sync_gmail} disabled={!canConnect} onChange={e => upd(a, { sync_gmail: e.target.checked })} /><span>Gmail → bandeja enrutada (reglas + copiloto) · última: {a.last_gmail_sync ? fmtDate(a.last_gmail_sync) : '—'}</span></label>
              <label><input type="checkbox" checked={a.sync_calendar} disabled={!canConnect} onChange={e => upd(a, { sync_calendar: e.target.checked })} /><span>Calendar → reuniones de proyectos (próximas 3 semanas) · última: {a.last_calendar_sync ? fmtDate(a.last_calendar_sync) : '—'}</span></label>
              <label><input type="checkbox" checked={a.sync_meet} disabled={!canConnect} onChange={e => upd(a, { sync_meet: e.target.checked })} /><span>Meet → transcripciones a la reunión + propuestas del copiloto · última: {a.last_meet_sync ? fmtDate(a.last_meet_sync) : '—'}</span></label>
              <label><input type="checkbox" checked={a.sync_drive} disabled={!canConnect} onChange={e => upd(a, { sync_drive: e.target.checked })} /><span>Drive → notas de Gemini (Meet Recordings) · última: {a.last_drive_sync ? fmtDate(a.last_drive_sync) : '—'}</span></label>
            </div>
            {canConnect && <div className="field" style={{ marginTop: 8 }}><label>Consulta de Gmail</label><input type="text" defaultValue={a.gmail_query} onBlur={e => upd(a, { gmail_query: e.target.value })} /></div>}
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{a.messages} mensajes/eventos procesados</div>
            {canConnect && a.state === 'conectada' && <button className="btn link small" onClick={() => { if (confirm('¿Desconectar esta cuenta?')) upd(a, { disconnect: true }) }}>Desconectar</button>}
          </div>
        ))}
        <div className="card">
          <h3>Cómo fluye la información</h3>
          <ul style={{ fontSize: 13, lineHeight: 1.7 }}>
            <li><b>Sesiones nuevas</b> en Calendar con clientes → se crean como reuniones del proyecto (equipo, contacto del cliente, enlace de Meet, agenda).</li>
            <li><b>Resúmenes / transcripciones de Meet</b> (API de Meet, correos "Notes:" y documentos "Notas de Gemini" en Drive) → se adjuntan a la reunión, el copiloto propone acuerdos, preguntas y riesgos; el PM confirma.</li>
            <li><b>Correos</b> → según reglas y copiloto llegan a <b>Administración</b> (facturación, cobranza, pagos, legal, RH, prospectos) u <b>Operaciones</b> (solicitudes, incidentes, comunicación de proyecto). Se convierten con un clic o automáticamente si la regla lo indica.</li>
            <li><b>Salidas</b>: minuta de reunión a Google Docs y portafolio a Google Sheets (carpeta "AlphaOps" en Drive).</li>
          </ul>
          <div className="toolbar"><Link className="btn secondary small" to={`${base}/r/google_inbox`}>Abrir bandeja</Link><Link className="btn secondary small" to={`${base}/r/google_rules`}>Reglas de enrutamiento</Link>{app === 'ops' && <button className="btn secondary small" onClick={() => api.post('/google/export/portfolio').then(r => { toast('Portafolio exportado', 'ok'); window.open(r.url, '_blank') }).catch((e: any) => toast(e.message, 'err'))}>Exportar portafolio a Sheets</button>}</div>
        </div>
      </div>
    </div>
  )
}
