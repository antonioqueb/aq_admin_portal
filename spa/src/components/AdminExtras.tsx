import { useState } from 'react'
import { api } from '../api'
import { useApp } from '../context'
import Many2one from './Many2one'

const EVENTS: [string, string][] = [['contract_active', 'Contrato activo'], ['contract_suspended', 'Contrato suspendido'], ['scope_authorized', 'Alcance comercial autorizado'], ['hours_authorized', 'Bolsa de horas autorizada'], ['commercial_condition', 'Condición comercial vigente'], ['payment_confirmed', 'Pago confirmado'], ['payment_restriction', 'Restricción por falta de pago'], ['contract_expiring', 'Contrato próximo a vencer']]

/** Administración → Operaciones: solo señales autorizadas (nunca facturas, bancos, tarifas ni márgenes). */
export default function AdminExtras({ resource, record }: { resource: string; record: any }) {
  const { user, toast } = useApp()
  const [type, setType] = useState('hours_authorized')
  const [hours, setHours] = useState(''); const [ref, setRef] = useState(''); const [changeId, setChangeId] = useState('')
  const [opsProject, setOpsProject] = useState<any>(null)
  const [last, setLast] = useState<any>(null)
  if (resource !== 'projects' || user?.role !== 'direccion' || !user.apps.includes('ops')) return null
  const send = async () => {
    try {
      const payload: any = { project: record.name }
      if (hours) payload.hours = parseFloat(hours); if (ref) payload.ref = ref; if (changeId) payload.change_id = parseInt(changeId)
      const r = await api.emitEvent({ event_type: type, admin_project_id: record.id, ops_project_id: opsProject?.id, payload })
      setLast(r.event); toast(r.event.state === 'procesado' ? 'Señal enviada a Operaciones' : 'Evento registrado: ' + (r.event.error || r.event.state), r.event.state === 'procesado' ? 'ok' : 'err')
    } catch (e: any) { toast(e.message, 'err') }
  }
  return (
    <div className="card" style={{ borderColor: 'var(--purple-bright)' }}>
      <h3>Señal a Operaciones (intercambio de eventos autorizados)</h3>
      <div className="grid cols-4">
        <div className="field"><label>Evento</label><select value={type} onChange={e => setType(e.target.value)}>{EVENTS.map(e => <option key={e[0]} value={e[0]}>{e[1]}</option>)}</select></div>
        <div className="field"><label>Proyecto en Operaciones</label><Many2one model="aq.ops.project" value={opsProject} onChange={setOpsProject} /></div>
        {(type === 'hours_authorized' || type === 'scope_authorized') && <div className="field"><label>Horas</label><input type="number" value={hours} onChange={e => setHours(e.target.value)} /></div>}
        {type === 'scope_authorized' && <><div className="field"><label>Referencia comercial</label><input type="text" value={ref} onChange={e => setRef(e.target.value)} /></div><div className="field"><label>ID del cambio en Operaciones</label><input type="number" value={changeId} onChange={e => setChangeId(e.target.value)} /></div></>}
      </div>
      <div className="toolbar"><button className="btn" onClick={send}>Enviar señal</button>{last && <span className={'badge ' + (last.state === 'procesado' ? 'ok' : 'err')}>{last.summary} · {last.state}</span>}</div>
      <p style={{ fontSize: 11, color: 'var(--mute2)' }}>Operaciones recibe únicamente la proyección (p. ej. "120 h autorizadas", "restricción comercial"); nunca facturas, cuentas bancarias, tarifas ni márgenes. Los cambios autorizados desde Control de cambios se proyectan automáticamente.</p>
    </div>
  )
}
