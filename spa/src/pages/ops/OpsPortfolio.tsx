import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtDate, ops } from '../../api'
import { useApp } from '../../context'

const GROUPS: [string, string][] = [['client', 'Cliente'], ['pm', 'Project Manager'], ['service_type', 'Tipo de servicio'], ['stage', 'Etapa'], ['health', 'Salud'], ['priority', 'Prioridad'], ['risk', 'Riesgo'], ['client_dependent', 'Dependencia del cliente']]

export default function OpsPortfolio() {
  const { toast } = useApp()
  const [d, setD] = useState<any>(null)
  const [group, setGroup] = useState(() => localStorage.getItem('aq_pf_group') || 'client')
  const [saved, setSaved] = useState<any[]>([])
  const loadViews = () => ops.views('portfolio').then(r => setSaved(r.views)).catch(() => {})
  useEffect(() => { ops.portfolio().then(setD).catch((e: any) => toast(e.message, 'err')); loadViews() }, [toast])
  const grouped = useMemo(() => {
    if (!d) return []
    const m: Record<string, any[]> = {}
    d.projects.forEach((p: any) => { const k = String(p[group] ?? '—'); (m[k] = m[k] || []).push(p) })
    return Object.entries(m).sort()
  }, [d, group])
  if (!d) return <div className="empty">Construyendo la torre de control…</div>
  const A = d.answers
  const Q = ({ title, rows, render }: { title: string; rows: any[]; render: (r: any) => JSX.Element }) => (
    <div className="card tight"><h3>{title} <span className="badge" style={{ marginLeft: 6 }}>{rows.length}</span></h3>{rows.length === 0 ? <div style={{ color: 'var(--mute2)', fontSize: 12 }}>Nada que atender</div> : <ul className="timeline">{rows.slice(0, 8).map(render)}</ul>}</div>
  )
  const PL = (r: any) => <li key={r.id}><Link to={`/ops/projects/${r.id}`}><span className={'health ' + r.health} />{r.name}</Link><div className="meta">{r.client} · {r.pm || 'sin PM'}{r.health_reason ? ' · ' + r.health_reason : ''}</div></li>
  return (
    <div>
      <div className="hero"><div><div className="tag">Dirección de Operaciones · PMO</div><h1>Torre de control del portafolio</h1><div className="pulse">{d.projects.length} proyectos · {A.at_risk.length} en riesgo · {A.no_next_step.length} sin siguiente paso · {A.waiting_client.length} esperando al cliente</div></div>
        <div className="toolbar" style={{ margin: 0 }}><label style={{ fontSize: 12 }}>Agrupar por</label><select value={group} onChange={e => { setGroup(e.target.value); localStorage.setItem('aq_pf_group', e.target.value) }} style={{ width: 'auto' }}>{GROUPS.map(g => <option key={g[0]} value={g[0]}>{g[1]}</option>)}</select>
          <button className="btn secondary small" onClick={() => { const n = prompt('Nombre de la vista guardada'); if (n) ops.saveView({ name: n, resource: 'portfolio', view_mode: 'group', filters: { group }, shared: confirm('¿Compartir con el equipo?') }).then(loadViews) }}>Guardar vista</button>
          {saved.map(v => <span key={v.id}><button className="btn link small" onClick={() => setGroup(v.filters.group || 'client')}>{v.name}{v.shared && ' (equipo)'}</button>{v.mine && <button className="btn link small" onClick={() => ops.deleteView(v.id).then(loadViews)}>✕</button>}</span>)}</div></div>
      <h3>¿Dónde debe intervenir Dirección hoy?</h3>
      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <Q title="Proyectos en riesgo" rows={A.at_risk} render={PL} />
        <Q title="Sin siguiente paso" rows={A.no_next_step} render={PL} />
        <Q title="Esperando al cliente" rows={A.waiting_client} render={PL} />
        <Q title="Personas sobrecargadas" rows={A.overloaded} render={(o: any) => <li key={o.member}>{o.member} <span className="badge err">{o.load_pct}%</span><div className="meta">{o.planned} h planificadas / {o.available} h</div></li>} />
        <Q title="Liberaciones próximas (14 d)" rows={A.upcoming_releases} render={(r: any) => <li key={r.id}><Link to={`/ops/r/releases/${r.id}`}>{r.name}</Link> <span className="badge">{r.env}</span>{r.gate && <span className="badge err">incompleta</span>}<div className="meta">{r.project} · {r.planned} · {r.state}</div></li>} />
        <Q title="Entregables detenidos en validación" rows={A.stuck_validation} render={(i: any) => <li key={i.id}><Link to={`/ops/r/items/${i.id}`}>{i.name}</Link><div className="meta">{i.project} · {i.days} d en validación</div></li>} />
        <Q title="Consumo de horas ≥ 85 %" rows={A.over_hours} render={(r: any) => <li key={r.id}><Link to={`/ops/projects/${r.id}`}>{r.name}</Link> <span className="badge warn">{r.hours_pct}%</span><div className="meta">{r.hours_consumed} / {r.hours_authorized} h</div></li>} />
        <Q title="Incidentes que pueden afectar a otros clientes" rows={A.cross_client_incidents} render={(i: any) => <li key={i.id}><Link to={`/ops/r/incidents/${i.id}`}>{i.name}</Link> <span className="badge err">{i.severity}</span><div className="meta">{i.project}</div></li>} />
        <Q title="Intervención de Dirección" rows={A.direction_today} render={PL} />
      </div>
      {grouped.map(([k, rows]) => (
        <div className="card" key={k}>
          <h2>{GROUPS.find(g => g[0] === group)?.[1]}: {k === 'true' ? 'Sí' : k === 'false' ? 'No' : k} <span className="badge">{rows.length}</span></h2>
          <div className="table-wrap"><table className="list"><thead><tr><th>Proyecto</th><th>Cliente</th><th>PM</th><th>Etapa</th><th>Salud</th><th>Prio.</th><th>Riesgo</th><th>Cliente</th><th className="num">Equipo</th><th className="num">Horas</th><th>Próximo hito</th><th>Próxima decisión</th><th>Fin probable</th><th>Siguiente acción</th></tr></thead>
            <tbody>{rows.map((p: any) => <tr key={p.id} className="row"><td><Link to={`/ops/projects/${p.id}`}>{p.name}</Link>{p.commercial_restriction && <span className="badge err" style={{ marginLeft: 4 }}>restricción</span>}</td><td>{p.client}</td><td>{p.pm || '—'}</td><td><span className="badge">{p.stage}</span></td><td><span className={'health ' + p.health} />{p.health}</td><td>{p.priority === '2' ? <span className="badge err">crítica</span> : p.priority === '1' ? <span className="badge warn">alta</span> : 'normal'}</td><td>{p.risk}</td><td>{p.client_dependent ? <span className="badge warn">esperando</span> : '—'}</td><td className="num">{p.team}</td><td className="num">{p.hours_pct >= 85 ? <span className="badge err">{p.hours_pct}%</span> : p.hours_pct + '%'}</td><td>{p.next_milestone || '—'}<div className="meta" style={{ fontSize: 11, color: 'var(--muted)' }}>{fmtDate(p.next_milestone_date)}</div></td><td>{p.next_decision || '—'}</td><td>{fmtDate(p.probable_end)}{p.baseline_end && p.probable_end > p.baseline_end && <span className="badge warn" style={{ marginLeft: 4 }}>desviado</span>}</td><td>{p.has_next_action ? p.next_action : <span className="badge err">sin definir</span>}</td></tr>)}</tbody></table></div>
        </div>
      ))}
    </div>
  )
}
