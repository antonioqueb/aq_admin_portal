import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { addDays, api, fmtDate, today } from '../api'
import { useApp } from '../context'

const TYPES: [string, string][] = [['semanal', 'Resumen ejecutivo semanal'], ['mensual', 'Reporte administrativo mensual'], ['integral', 'Reporte administrativo integral'], ['cierre_facturacion', 'Cierre de facturación'], ['conciliacion_horas', 'Conciliación de horas ejecutadas, facturadas y pagadas']]

export default function Reports() {
  const { toast, user } = useApp()
  const nav = useNavigate()
  const [type, setType] = useState('semanal')
  const [from, setFrom] = useState(addDays(today(), -6))
  const [to, setTo] = useState(today())
  const [items, setItems] = useState<any[]>([])
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => api.list('reports', { limit: 50, order: 'date_to desc' }).then(r => setItems(r.records)).catch(() => {}), [])
  useEffect(() => { load() }, [load])
  const gen = async () => {
    setBusy(true)
    try { const r = await api.generateReport(type, from, to); toast('Reporte generado', 'ok'); nav(`/r/reports/${r.record.id}`) } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <div>
      <h1>Resúmenes ejecutivos y reportes</h1>
      {(user?.role === 'direccion' || user?.role === 'coordinacion') && (
        <div className="card"><h2>Generar reporte</h2>
          <div className="toolbar">
            <select value={type} onChange={e => setType(e.target.value)} style={{ width: 'auto' }}>{TYPES.map(t => <option key={t[0]} value={t[0]}>{t[1]}</option>)}</select>
            <input type="date" value={from} onChange={e => setFrom(e.target.value)} style={{ width: 150 }} /><input type="date" value={to} onChange={e => setTo(e.target.value)} style={{ width: 150 }} />
            <button className="btn" disabled={busy} onClick={gen}>{busy ? 'Generando…' : 'Generar'}</button>
          </div>
          <div style={{ fontSize: 12, color: '#6b7280' }}>El reporte toma una fotografía de todos los controles (pendientes, avances, riesgos, facturación, cobranza, pagos, horas, prospectos, contratos) y puede entregarse a Dirección por correo desde la ficha.</div>
        </div>
      )}
      <div className="card"><h2>Reportes emitidos</h2>
        <div className="table-wrap"><table className="list"><thead><tr><th>Fecha</th><th>Tipo</th><th>Nombre</th><th>Preparó</th><th>Entregado</th></tr></thead>
          <tbody>{items.map(r => <tr key={r.id} className="row" onClick={() => nav(`/r/reports/${r.id}`)}><td>{fmtDate(r.date_to)}</td><td>{TYPES.find(t => t[0] === r.report_type)?.[1]}</td><td>{r.name}</td><td>{r.prepared_by_id?.name}</td><td>{r.sent_to_direction ? <span className="badge ok">{fmtDate(r.sent_date)}</span> : <span className="badge">no</span>}</td></tr>)}</tbody></table></div>
        {items.length === 0 && <div className="empty">Aún no hay reportes</div>}
      </div>
    </div>
  )
}
