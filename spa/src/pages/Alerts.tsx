import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate } from '../api'
import { useApp } from '../context'

const SEV: Record<string, [string, string]> = { '1': ['Info', 'info'], '2': ['Atención', 'warn'], '3': ['Urgente', 'err'], '4': ['Crítico', 'err'] }

export default function Alerts() {
  const { toast, user } = useApp()
  const [alerts, setAlerts] = useState<any[]>([])
  const [type, setType] = useState('')
  const load = useCallback(() => api.alerts().then(r => setAlerts(r.alerts)).catch(e => toast(e.message, 'err')), [toast])
  useEffect(() => { load() }, [load])
  const types = Array.from(new Set(alerts.map(a => a.type)))
  const shown = alerts.filter(a => !type || a.type === type)
  return (
    <div>
      <div className="toolbar"><div><h1>Alertas y vencimientos</h1><div style={{ color: '#6b7280', fontSize: 12 }}>Generadas automáticamente cada día a partir de los controles.</div></div><span className="spacer" />
        <select value={type} onChange={e => setType(e.target.value)} style={{ width: 'auto' }}><option value="">Todos los tipos</option>{types.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select>
        {(user?.role === 'direccion' || user?.role === 'coordinacion') && <button className="btn secondary" onClick={() => api.recomputeAlerts().then(() => { toast('Recalculado', 'ok'); load() })}>Recalcular ahora</button>}
      </div>
      <div className="card">
        {shown.length === 0 && <div className="empty">Sin alertas activas 🎉</div>}
        <ul className="timeline">
          {shown.map(a => (
            <li key={a.id} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span className={'badge ' + SEV[a.severity][1]}>{SEV[a.severity][0]}</span>
              <div style={{ flex: 1 }}>{a.resource ? <Link to={`/r/${a.resource}/${a.res_id}`}>{a.name}</Link> : a.name}<div className="meta">{a.type.replace(/_/g, ' ')} · {fmtDate(a.date)} {a.responsible && '· ' + a.responsible}</div></div>
              {(user?.role === 'direccion' || user?.role === 'coordinacion') && <button className="btn link small" onClick={() => api.dismissAlert(a.id).then(load)}>descartar</button>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
