import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { addDays, api, fmtDate, fmtMoney, today } from '../api'
import { useApp } from '../context'

const KIND_LABEL: Record<string, string> = { facturacion: 'Facturación', cobranza: 'Cobranza', compromiso_pago: 'Compromiso de pago', pago: 'Pago', pendiente: 'Pendiente', proyecto: 'Proyecto', entregable: 'Entregable', prospecto: 'Prospecto', propuesta: 'Propuesta', contrato: 'Contrato', renovacion: 'Renovación', riesgo: 'Riesgo', incorporacion: 'Incorporación' }
const KIND_CLS: Record<string, string> = { facturacion: 'primary', cobranza: 'warn', compromiso_pago: 'warn', pago: 'err', pendiente: 'info', proyecto: 'info', entregable: 'info', prospecto: 'ok', propuesta: 'ok', contrato: 'err', renovacion: 'warn', riesgo: 'err', incorporacion: '' }

export default function Calendar() {
  const { toast } = useApp()
  const [from, setFrom] = useState(addDays(today(), -7))
  const [to, setTo] = useState(addDays(today(), 45))
  const [kind, setKind] = useState('')
  const [ev, setEv] = useState<any[]>([])
  useEffect(() => { api.calendar(from, to).then(r => setEv(r.events)).catch(e => toast(e.message, 'err')) }, [from, to, toast])
  const kinds = Array.from(new Set(ev.map(e => e.kind.split(':')[0])))
  const shown = ev.filter(e => !kind || e.kind.startsWith(kind))
  const days = Array.from(new Set(shown.map(e => e.date)))
  const t = today()
  return (
    <div>
      <div className="toolbar"><div><h1>Calendario de obligaciones</h1><div style={{ color: '#6b7280', fontSize: 12 }}>Vencimientos de contratos, renovaciones, facturación, cobranza, pagos, Contabilidad, avisos, permisos, licencias, dominios, pólizas, asambleas y fechas comprometidas con clientes.</div></div><span className="spacer" />
        <input type="date" value={from} onChange={e => setFrom(e.target.value)} style={{ width: 150 }} /><input type="date" value={to} onChange={e => setTo(e.target.value)} style={{ width: 150 }} />
        <select value={kind} onChange={e => setKind(e.target.value)} style={{ width: 'auto' }}><option value="">Todo</option>{kinds.map(k => <option key={k} value={k}>{KIND_LABEL[k] || k}</option>)}</select>
        <Link className="btn" to="/r/obligations/new">+ Nueva obligación</Link>
      </div>
      <div className="card">
        {days.length === 0 && <div className="empty">Sin eventos en el rango</div>}
        {days.map(d => (
          <div className="cal-day" key={d}>
            <div className={'d' + (d === t ? ' today' : '')}>{fmtDate(d)} {d < t && <span className="badge err">vencido</span>}{d === t && <span className="badge primary">hoy</span>}</div>
            {shown.filter(e => e.date === d).map((e, i) => {
              const k = e.kind.split(':')[0]
              return <div className="cal-ev" key={i}><span className={'badge ' + (KIND_CLS[k] || '')}>{KIND_LABEL[k] || e.kind}</span><Link to={`/r/${e.resource}/${e.id}`}>{e.title}</Link>{e.amount != null && <span className="meta" style={{ color: '#6b7280' }}>{fmtMoney(e.amount)}</span>}{e.responsible && <span style={{ color: '#6b7280', fontSize: 12 }}>· {e.responsible}</span>}{e.state && <span className="badge">{e.state}</span>}</div>
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
