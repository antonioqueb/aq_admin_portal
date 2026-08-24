import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, fmtDate, fmtMoney, today } from '../api'
import { useApp } from '../context'

const Kpi = ({ v, l, cls, to }: { v: any; l: string; cls?: string; to?: string }) => {
  const nav = useNavigate()
  return <div className={'kpi ' + (cls || '')} style={{ cursor: to ? 'pointer' : 'default' }} onClick={() => to && nav(to)}><div className="v">{v}</div><div className="l">{l}</div></div>
}
const SEV: Record<string, string> = { '1': 'info', '2': 'warn', '3': 'err', '4': 'err' }

export default function Dashboard() {
  const { toast, user } = useApp()
  const [d, setD] = useState<any>(null)
  const [from, setFrom] = useState(today().slice(0, 8) + '01')
  const [to, setTo] = useState(today())
  useEffect(() => { api.dashboard(from, to).then(setD).catch(e => toast(e.message, 'err')) }, [from, to, toast])
  if (!d) return <div className="empty">Calculando tablero…</div>
  const s = d.summary, k = d.kpis, L = d.lists
  const warn = (n: number) => n > 0 ? 'warn' : 'ok'
  const err = (n: number) => n > 0 ? 'err' : 'ok'
  return (
    <div>
      <div className="hero">
        <div><div className="tag">Alphaqueb Consulting</div><h1>Estado real de la empresa</h1><div className="pulse">Actualizado hoy {fmtDate(d.period.today)} · {s.alerts_active} alertas activas · {s.overdue_agreements} pendientes vencidos</div></div>
        <div className="toolbar" style={{ margin: 0 }}>
        <label style={{ fontSize: 12 }}>Periodo</label><input type="date" value={from} onChange={e => setFrom(e.target.value)} style={{ width: 150 }} /><input type="date" value={to} onChange={e => setTo(e.target.value)} style={{ width: 150 }} />
        {(user?.role === 'direccion' || user?.role === 'coordinacion') && <button className="btn secondary small" onClick={() => api.recomputeAlerts().then(() => { toast('Alertas recalculadas', 'ok'); api.dashboard(from, to).then(setD) })}>Recalcular alertas</button>}
        </div>
      </div>

      <h3>Proyectos y pendientes</h3>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Kpi v={s.active_projects} l="Proyectos activos" to="/r/projects" />
        <Kpi v={s.paused_projects} l="Proyectos pausados" to="/r/projects?f.stage=pausado" />
        <Kpi v={s.stale_projects} l="Proyectos sin actividad reciente" cls={warn(s.stale_projects)} to="/r/projects?f.is_stale=true" />
        <Kpi v={s.projects_without_next_action} l="Proyectos sin siguiente acción" cls={warn(s.projects_without_next_action)} />
        <Kpi v={s.open_agreements} l="Pendientes abiertos" to="/r/agreements" />
        <Kpi v={s.overdue_agreements} l="Pendientes vencidos" cls={err(s.overdue_agreements)} to="/r/agreements?f.is_overdue=true" />
        <Kpi v={s.critical_pending} l="Pendientes críticos" cls={err(s.critical_pending)} />
        <Kpi v={s.deliverables_pending_acceptance} l="Entregables sin aceptación" cls={warn(s.deliverables_pending_acceptance)} to="/r/deliverables?f.state=entregado" />
      </div>
      <h3>Facturación, cobranza y pagos</h3>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Kpi v={fmtMoney(s.invoiced_amount_period)} l={`Facturación del periodo (${s.invoices_issued_period} emitidas / ${s.invoices_scheduled_period} programadas)`} to="/r/invoices" />
        <Kpi v={s.invoices_late} l="Facturas atrasadas" cls={err(s.invoices_late)} to="/r/invoices?f.is_late=true" />
        <Kpi v={s.invoices_on_hold} l="Facturas detenidas (requieren validación)" cls={warn(s.invoices_on_hold)} to="/r/invoices?f.state=detenida" />
        <Kpi v={fmtMoney(s.collected_period)} l="Cobrado en el periodo" cls="ok" />
        <Kpi v={fmtMoney(s.receivable_total)} l={`Cuentas por cobrar (${s.receivable_count})`} to="/r/receivables" />
        <Kpi v={fmtMoney(s.receivable_overdue)} l={`Cartera vencida (${s.receivable_overdue_count})`} cls={err(s.receivable_overdue_count)} to="/r/receivables?f.state=vencida" />
        <Kpi v={fmtMoney(s.payable_total)} l="Cuentas por pagar" to="/r/payables" />
        <Kpi v={s.payable_pending_authorization} l={`Pagos sin autorizar · vencido ${fmtMoney(s.payable_overdue)}`} cls={warn(s.payable_pending_authorization)} to="/r/payables?f.authorization_state=pendiente" />
      </div>
      <h3>Horas, prospectos, contratos y riesgos</h3>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Kpi v={s.hours_unbilled.toFixed(1) + ' h'} l="Trabajo ejecutado sin facturar" cls={warn(s.hours_unbilled)} to="/r/hours" />
        <Kpi v={s.hours_unregistered.toFixed(1) + ' h'} l="Trabajo sin registro" cls={warn(s.hours_unregistered)} />
        <Kpi v={s.buckets_near_depletion} l="Bolsas por agotarse / excedidas" cls={warn(s.buckets_near_depletion)} to="/r/hours?f.near_depletion=true" />
        <Kpi v={s.changes_pending} l={`Cambios sin autorizar · ${s.changes_unauthorized_executed} ejecutados sin autorización`} cls={warn(s.changes_pending + s.changes_unauthorized_executed)} to="/r/changes" />
        <Kpi v={s.prospects_open} l={`Prospectos abiertos · ${s.prospects_abandoned} sin seguimiento`} cls={warn(s.prospects_abandoned)} to="/r/prospects" />
        <Kpi v={s.legal_missing} l={`Documentos legales faltantes · ${s.legal_expiring} por vencer · ${s.legal_expired} vencidos`} cls={warn(s.legal_missing + s.legal_expired)} to="/r/legal" />
        <Kpi v={s.renewals_30d + s.obligations_30d} l={`Renovaciones y obligaciones a 30 días · ${s.obligations_overdue} vencidas`} cls={warn(s.obligations_overdue)} to="/calendar" />
        <Kpi v={s.risks_open} l={`Riesgos abiertos · ${s.risks_high} altos`} cls={warn(s.risks_high)} to="/r/risks" />
      </div>
      <h3>Indicadores de operación</h3>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Kpi v={k.invoices_on_time_pct + '%'} l="Facturas emitidas a tiempo" cls={k.invoices_on_time_pct < 80 ? 'warn' : 'ok'} />
        <Kpi v={k.collected_on_time_pct + '%'} l="Facturas cobradas en fecha" cls={k.collected_on_time_pct < 80 ? 'warn' : 'ok'} />
        <Kpi v={k.overdue_portfolio_pct + '%'} l="Cartera vencida sobre total" cls={k.overdue_portfolio_pct > 20 ? 'err' : 'ok'} />
        <Kpi v={k.avg_collection_days + ' d'} l="Tiempo promedio de cobranza" />
        <Kpi v={k.executed_vs_billed_pct + '%'} l="Trabajo facturado vs ejecutado" cls={k.executed_vs_billed_pct < 80 ? 'warn' : 'ok'} />
        <Kpi v={k.projects_with_next_action_pct + '%'} l="Proyectos con siguiente acción definida" cls={k.projects_with_next_action_pct < 100 ? 'warn' : 'ok'} />
        <Kpi v={`${k.deliverables_accepted}/${k.deliverables_total}`} l="Entregables aceptados" />
        <Kpi v={`${k.contracts_current} / ${k.contracts_missing}`} l="Contratos vigentes / faltantes" cls={warn(k.contracts_missing)} />
        <Kpi v={k.prospects_without_followup} l="Prospectos sin seguimiento" cls={warn(k.prospects_without_followup)} />
        <Kpi v={k.avg_admin_response_days + ' d'} l="Tiempo de respuesta administrativo (cierre de pendientes)" />
        <Kpi v={`${k.complete_closures}/${k.closed_projects}`} l="Cierres documentales completos" />
        <Kpi v={s.admin_backlog} l="Carga administrativa pendiente (rutinas atrasadas)" cls={warn(s.admin_backlog)} to="/routines" />
      </div>
      {k.overdue_by_member.length > 0 && <div className="card tight"><b>Pendientes vencidos por responsable:</b> {k.overdue_by_member.map((x: any) => <span key={x.member} className="badge err" style={{ marginLeft: 6 }}>{x.member}: {x.count}</span>)}</div>}

      <div className="two">
        <div>
          <div className="card">
            <h2>Proyectos activos</h2>
            <div className="table-wrap"><table className="list"><thead><tr><th>Proyecto</th><th>Cliente</th><th>Responsable</th><th>Siguiente acción</th><th>Fecha</th><th>Sin act.</th><th>Fact.</th><th>Cobr.</th></tr></thead>
              <tbody>{L.active_projects.map((p: any) => <tr key={p.id} className="row"><td><Link to={`/r/projects/${p.id}`}>{p.name}</Link>{p.requires_direction && <span className="badge err" style={{ marginLeft: 4 }}>Dirección</span>}</td><td>{p.client}</td><td>{p.responsible || '—'}</td><td>{p.next_action || <span className="badge warn">sin definir</span>}</td><td>{fmtDate(p.next_action_date)}</td><td className={p.is_stale ? 'num' : 'num'}>{p.is_stale ? <span className="badge err">{p.days_without_activity} d</span> : p.days_without_activity + ' d'}</td><td><span className="badge">{p.billing_status}</span></td><td><span className="badge">{p.collection_status}</span></td></tr>)}</tbody></table></div>
          </div>
          <div className="card">
            <h2>Pendientes críticos</h2>
            {L.critical_pending.length === 0 ? <div className="empty">Sin pendientes críticos</div> : <ul className="timeline">{L.critical_pending.map((a: any) => <li key={a.id}><Link to={`/r/agreements/${a.id}`}>{a.name}</Link> <span className="meta">· {a.project || '—'} · {a.executor || 'sin responsable'} · {a.days_overdue} d de atraso {a.escalated && <span className="badge err">escalado</span>}</span></li>)}</ul>}
          </div>
          <div className="card">
            <h2>Cartera por cobrar</h2>
            <div className="table-wrap"><table className="list"><thead><tr><th>Factura</th><th>Cliente</th><th className="num">Saldo</th><th>Vence</th><th className="num">Vencido</th><th>Compromiso</th><th>Riesgo</th></tr></thead>
              <tbody>{L.receivables.map((r: any) => <tr key={r.id}><td><Link to={`/r/receivables/${r.id}`}>{r.name}</Link></td><td>{r.client}</td><td className="num">{fmtMoney(r.balance)}</td><td>{fmtDate(r.due_date)}</td><td className="num">{r.days_overdue > 0 ? <span className="badge err">{r.days_overdue} d</span> : '—'}</td><td>{fmtDate(r.promised)}</td><td><span className={'badge ' + (r.risk === 'critico' || r.risk === 'alto' ? 'err' : r.risk === 'medio' ? 'warn' : 'ok')}>{r.risk}</span></td></tr>)}</tbody></table></div>
          </div>
          <div className="card">
            <h2>Trabajo ejecutado sin facturar · horas por proyecto</h2>
            <div className="table-wrap"><table className="list"><thead><tr><th>Proyecto</th><th className="num">Contratadas</th><th className="num">Ejecutadas</th><th className="num">Facturadas</th><th className="num">Sin facturar</th></tr></thead>
              <tbody>{L.hours_by_project.map((h: any) => <tr key={h.project}><td>{h.project}</td><td className="num">{h.contracted}</td><td className="num">{h.executed}</td><td className="num">{h.billed}</td><td className="num">{h.unbilled > 0 ? <span className="badge warn">{h.unbilled.toFixed(1)}</span> : '0'}</td></tr>)}</tbody></table></div>
          </div>
        </div>
        <div>
          <div className="card">
            <h2>Alertas activas ({L.alerts.length})</h2>
            <ul className="timeline">{L.alerts.slice(0, 20).map((a: any) => <li key={a.id}><span className={'badge ' + SEV[a.severity]}>{a.severity === '4' ? 'Crítico' : a.severity === '3' ? 'Urgente' : 'Atención'}</span> <Link to={a.resource ? `/r/${a.resource}/${a.res_id}` : '/alerts'}>{a.name}</Link></li>)}</ul>
            <Link to="/alerts">Ver todas →</Link>
          </div>
          <div className="card"><h2>Próximos entregables</h2><ul className="timeline">{L.upcoming_deliverables.map((d: any) => <li key={d.id}><Link to={`/r/deliverables/${d.id}`}>{d.name}</Link><div className="meta">{d.project} · {fmtDate(d.due_date)} · {d.state}</div></li>)}{L.upcoming_deliverables.length === 0 && <li className="empty">Sin entregables próximos</li>}</ul></div>
          <div className="card"><h2>Prospectos y próximas acciones</h2><ul className="timeline">{L.prospects.map((p: any) => <li key={p.id}><Link to={`/r/prospects/${p.id}`}>{p.name}</Link> {p.abandoned && <span className="badge err">sin seguimiento</span>}<div className="meta">{p.stage} · {p.next_action || 'sin acción'} · {fmtDate(p.followup_date)} · {p.responsible || '—'}</div></li>)}</ul></div>
          <div className="card"><h2>Renovaciones y vencimientos</h2><ul className="timeline">{L.renewals.map((v: any) => <li key={v.id}><Link to={`/r/vendors/${v.id}`}>{v.name} · {v.service}</Link><div className="meta">{fmtDate(v.renewal_date)} · {fmtMoney(v.cost)} {v.critical && <span className="badge err">crítico</span>}</div></li>)}{L.obligations.map((o: any) => <li key={'o' + o.id}><Link to={`/r/obligations/${o.id}`}>{o.name}</Link><div className="meta">{fmtDate(o.date)} · {o.type} · {o.responsible || '—'}</div></li>)}</ul></div>
          <div className="card"><h2>Riesgos contractuales y documentos</h2><ul className="timeline">{L.contract_risks.map((l: any) => <li key={l.id}><Link to={`/r/legal/${l.id}`}>{l.name}</Link><div className="meta">{l.category} · {l.status} · riesgo {l.risk}</div></li>)}{L.risks.map((r: any) => <li key={'r' + r.id}><Link to={`/r/risks/${r.id}`}>{r.name}</Link><div className="meta">severidad {r.severity} · {r.state} · {r.responsible}</div></li>)}</ul></div>
        </div>
      </div>
    </div>
  )
}
