import { useEffect, useState } from 'react'
import { addDays, ops, today } from '../../api'
import { useApp } from '../../context'

const K = ({ v, l, cls }: { v: any; l: string; cls?: string }) => <div className={'kpi ' + (cls || '')}><div className="v">{v}</div><div className="l">{l}</div></div>

export default function OpsReports() {
  const { toast } = useApp()
  const [from, setFrom] = useState(addDays(today(), -30)); const [to, setTo] = useState(today())
  const [k, setK] = useState<any>(null)
  useEffect(() => { ops.kpis(from, to).then(setK).catch((e: any) => toast(e.message, 'err')) }, [from, to, toast])
  if (!k) return <div className="empty">Calculando indicadores…</div>
  const w = (v: number, bad: number, inv = false) => (inv ? v > bad : v < bad) ? 'warn' : 'ok'
  return (
    <div>
      <div className="toolbar"><div><h1>Reportes operativos</h1><div style={{ color: 'var(--muted)', fontSize: 12 }}>Medimos flujo, predictibilidad, calidad, valor aceptado y tiempo de respuesta — no cantidad de tareas.</div></div><span className="spacer" /><input type="date" value={from} onChange={e => setFrom(e.target.value)} style={{ width: 150 }} /><input type="date" value={to} onChange={e => setTo(e.target.value)} style={{ width: 150 }} /></div>
      <h3>Entrega y plan</h3>
      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        <K v={k.milestone_compliance_pct + '%'} l={`Cumplimiento de hitos (${k.milestones_validated} validados)`} cls={w(k.milestone_compliance_pct, 80)} />
        <K v={(k.plan_deviation_days > 0 ? '+' : '') + k.plan_deviation_days + ' d'} l="Desviación promedio del plan" cls={k.plan_deviation_days > 5 ? 'err' : 'ok'} />
        <K v={k.predictability_pct + '%'} l="Predictibilidad de entrega (vs. línea base)" cls={w(k.predictability_pct, 70)} />
        <K v={k.cycle_time_days + ' d'} l={`Tiempo de ciclo · lead time ${k.lead_time_days} d`} />
        <K v={k.blocked_hours + ' h'} l={`Tiempo bloqueado (${k.blocked_items} elementos)`} cls={k.blocked_items ? 'warn' : 'ok'} />
        <K v={k.aging_avg_days + ' d'} l={`Antigüedad promedio · ${k.aging_over_30} > 30 d`} cls={k.aging_over_30 ? 'warn' : 'ok'} />
        <K v={k.unplanned_pct + '%'} l="Trabajo no planificado" cls={w(k.unplanned_pct, 20, true)} />
        <K v={k.scope_changes} l="Cambios de alcance en el periodo" />
      </div>
      <h3>Cliente y aceptación</h3>
      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        <K v={k.waiting_client_avg_days + ' d'} l={`Tiempo esperando al cliente (${k.waiting_client_items} elementos)`} cls={w(k.waiting_client_avg_days, 5, true)} />
        <K v={k.acceptance_avg_days + ' d'} l={`Tiempo de aceptación (${k.acceptances} validaciones · ${k.acceptance_approved_pct}% aprobadas)`} />
        <K v={k.client_response_hours + ' h'} l={`Tiempo de respuesta a solicitudes (${k.client_requests})`} />
        <K v={k.client_participation_pct + '%'} l="Participación del cliente en validaciones" cls={w(k.client_participation_pct, 70)} />
      </div>
      <h3>Capacidad y esfuerzo</h3>
      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        <K v={k.capacity_load_pct + '%'} l={`Carga de capacidad · ${k.overloaded_people} personas sobreasignadas`} cls={k.overloaded_people ? 'err' : 'ok'} />
        <K v={k.estimated_vs_real_pct + '%'} l="Horas reales vs estimadas" cls={k.estimated_vs_real_pct > 110 ? 'err' : 'ok'} />
        <K v={k.rework_pct + '%'} l="Retrabajo" cls={w(k.rework_pct, 15, true)} />
        <K v={`${k.defects_internal} / ${k.defects_production}`} l="Defectos internos / en producción" cls={k.defects_production ? 'err' : 'ok'} />
      </div>
      <h3>Liberaciones, incidentes y salud</h3>
      <div className="grid cols-4">
        <K v={k.release_success_pct + '%'} l={`Éxito de liberaciones (${k.releases})`} cls={w(k.release_success_pct, 90)} />
        <K v={`S1 ${k.incidents_by_severity.S1} · S2 ${k.incidents_by_severity.S2} · S3 ${k.incidents_by_severity.S3} · S4 ${k.incidents_by_severity.S4}`} l="Incidentes por severidad" cls={k.incidents_by_severity.S1 ? 'err' : ''} />
        <K v={k.sla_compliance_pct + '%'} l="Cumplimiento de SLA" cls={w(k.sla_compliance_pct, 90)} />
        <K v={`${k.portfolio_health.verde} · ${k.portfolio_health.amarillo} · ${k.portfolio_health.rojo}`} l="Salud del portafolio (verde · amarillo · rojo)" cls={k.portfolio_health.rojo ? 'err' : 'ok'} />
      </div>
    </div>
  )
}
