import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtDate, ops } from '../../api'
import { useApp } from '../../context'

const CAT: Record<string, [string, string]> = { accion_requerida: ['Acción requerida', 'err'], aprobacion: ['Aprobación', 'warn'], bloqueo: ['Bloqueo', 'err'], riesgo: ['Riesgo', 'warn'], incidente: ['Incidente', 'err'], mencion: ['Mención', 'info'], cambio_fecha: ['Cambio de fecha', 'warn'], dependencia_liberada: ['Dependencia liberada', 'ok'], cliente_respondio: ['Cliente respondió', 'info'], entregable_aceptado: ['Entregable aceptado', 'ok'], recordatorio: ['Recordatorio', ''], resumen: ['Resumen', ''] }

export default function OpsNotifications() {
  const { toast } = useApp()
  const [d, setD] = useState<any>(null)
  const [all, setAll] = useState(false)
  const [cat, setCat] = useState('')
  const load = useCallback(() => ops.notifications(all).then(setD).catch((e: any) => toast(e.message, 'err')), [all, toast])
  useEffect(() => { load() }, [load])
  if (!d) return <div className="empty">Cargando…</div>
  const rows = d.notifications.filter((n: any) => !cat || n.category === cat)
  return (
    <div>
      <div className="toolbar"><div><h1>Centro de notificaciones</h1><div style={{ color: 'var(--muted)', fontSize: 12 }}>Con prioridad y acción directa. También llegan por correo en el resumen diario/semanal; integraciones con Teams/Slack/WhatsApp preparadas en Configuración → Integraciones.</div></div><span className="spacer" />
        <select value={cat} onChange={e => setCat(e.target.value)} style={{ width: 'auto' }}><option value="">Todas las categorías</option>{Object.entries(CAT).map(([k, v]) => <option key={k} value={k}>{v[0]}</option>)}</select>
        <label className="check"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} /> Incluir leídas</label>
        <a className="btn secondary small" href={ops.icsUrl()}>📅 Calendario ICS</a>
        <button className="btn secondary small" onClick={() => ops.notifReadAll().then(load)}>Marcar todo leído</button></div>
      <div className="card">
        {rows.length === 0 && <div className="empty">Sin notificaciones</div>}
        {rows.map((n: any) => <div key={n.id} className={'notif' + (n.read ? '' : ' unread')}>
          <span className={'badge ' + CAT[n.category]?.[1]}>{CAT[n.category]?.[0] || n.category}</span>
          <div className="t">{n.resource ? <Link to={`/ops/r/${n.resource}/${n.res_id}`} onClick={() => ops.notifUpdate(n.id, { read: true })}>{n.title}</Link> : n.title}{n.body && <div style={{ fontSize: 12, color: 'var(--muted)' }}>{n.body}</div>}<div className="meta" style={{ fontSize: 11, color: 'var(--mute2)' }}>{fmtDate(n.date)} {n.date.slice(11, 16)} · prioridad {n.priority}</div></div>
          {n.action_required && !n.done && <button className="btn secondary small" onClick={() => ops.notifUpdate(n.id, { done: true }).then(load)}>Atendida</button>}
          {!n.read && <button className="btn link small" onClick={() => ops.notifUpdate(n.id, { read: true }).then(load)}>leída</button>}
        </div>)}
      </div>
    </div>
  )
}
