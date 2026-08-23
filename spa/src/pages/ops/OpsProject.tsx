import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fmtDate, ops } from '../../api'
import { useApp } from '../../context'
import WorkViews from '../../components/WorkViews'

export default function OpsProject() {
  const { id } = useParams()
  const { toast, user, schema } = useApp()
  const [d, setD] = useState<any>(null)
  const [tab, setTab] = useState<'resumen' | 'trabajo'>('resumen')
  const [view, setView] = useState(localStorage.getItem('aq_board_view') || 'kanban')
  const [ai, setAi] = useState<string>('')
  const external = !!(schema?.is_external || user?.is_external)
  const load = useCallback(() => ops.command(Number(id)).then(r => { setD(r); localStorage.setItem('aq_active_project', JSON.stringify({ id: r.project.id, name: r.project.name })); window.dispatchEvent(new Event('aq:project')) }).catch((e: any) => toast(e.message, 'err')), [id, toast])
  useEffect(() => { load() }, [load])
  if (!d) return <div className="empty">Abriendo el centro de mando…</div>
  const p = d.project
  const H = ({ k, v }: { k: string; v: string }) => <span className="badge" style={{ marginRight: 4 }}><span className={'health ' + v} />{k}</span>
  const askAi = async (kind: 'explain' | 'next-action') => { try { const r = await ops.ai(`projects/${p.id}/${kind}`); setAi(r.text + (r.ai ? '' : '  (heurística local: active DeepSeek en Integraciones para análisis con IA)')) } catch (e: any) { toast(e.message, 'err') } }
  return (
    <div>
      <div className="hero">
        <div><div className="tag">{p.client} · {p.service_type} · {p.methodology}</div><h1><span className={'health ' + p.health} />{p.name}</h1><div className="pulse">{p.stage_label} · PM {p.pm || '—'} · {p.health_reason}</div>
          <div style={{ marginTop: 8 }}><H k="Alcance" v={p.health_dims.alcance} /><H k="Tiempo" v={p.health_dims.tiempo} />{!external && <H k="Capacidad" v={p.health_dims.capacidad} />}<H k="Calidad" v={p.health_dims.calidad} /><H k="Cliente" v={p.health_dims.cliente} />{p.commercial_restriction && <span className="badge err">restricción comercial</span>}{p.contract_state !== 'sin_dato' && <span className="badge">{p.contract_state}</span>}</div></div>
        <div className="toolbar" style={{ margin: 0 }}><Link className="btn secondary small" to={`/ops/r/projects/${p.id}`}>Editar ficha</Link>{!external && <button className="btn secondary small" onClick={() => askAi('explain')}>¿Por qué está en {p.health}?</button>}{!external && <button className="btn secondary small" onClick={() => askAi('next-action')}>Sugerir siguiente acción</button>}</div>
      </div>
      {ai && <div className="copilot"><h4>Copiloto · propuesta (no vinculante)</h4><div style={{ whiteSpace: 'pre-wrap' }}>{ai}</div><div className="disclaimer">La IA solo propone: no aprueba, no cambia alcance ni fechas, no acepta entregables.</div></div>}
      <div className="tabs"><button className={tab === 'resumen' ? 'active' : ''} onClick={() => setTab('resumen')}>Resumen (2 minutos)</button><button className={tab === 'trabajo' ? 'active' : ''} onClick={() => setTab('trabajo')}>Trabajo · {d.counts.open} abiertos</button></div>
      {tab === 'trabajo' && <WorkViews items={d.board} sprints={d.sprints} reload={load} view={view} setView={v => { setView(v); localStorage.setItem('aq_board_view', v) }} projectMode />}
      {tab === 'resumen' && (<>
        <div className="grid cols-4" style={{ marginBottom: 14 }}>
          {!external && <div className={'kpi ' + (p.hours.pct >= 85 ? 'err' : p.hours.pct >= 70 ? 'warn' : 'ok')}><div className="v">{p.hours.pct}%</div><div className="l">Bolsa autorizada: {p.hours.consumed} / {p.hours.authorized} h · restan {p.hours.remaining} h · aprobadas {p.hours.approved} h</div></div>}
          <div className={'kpi ' + (p.next_action ? 'ok' : 'err')}><div className="v" style={{ fontSize: 18 }}>{p.next_action || 'Sin definir'}</div><div className="l">Próximo compromiso · {p.next_action_owner || '—'} · {fmtDate(p.next_action_date)}</div></div>
          <div className="kpi"><div className="v" style={{ fontSize: 18 }}>{d.milestones.find((m: any) => m.state !== 'validado')?.name || '—'}</div><div className="l">Próximo hito · {fmtDate(d.milestones.find((m: any) => m.state !== 'validado')?.date)}</div></div>
          <div className={'kpi ' + (d.in_validation.length ? 'warn' : '')}><div className="v">{d.in_validation.length}</div><div className="l">Entregables en validación</div></div>
          {p.forecast && <div className={'kpi ' + (p.forecast.depletion && p.date_end_current && p.forecast.depletion < p.date_end_current ? 'err' : '')}><div className="v" style={{ fontSize: 18 }}>{p.forecast.depletion ? fmtDate(p.forecast.depletion) : '—'}</div><div className="l">Pronóstico de agotamiento · {p.forecast.burn_rate_week.toFixed(1)} h/sem · fin por velocidad {fmtDate(p.forecast.end_by_velocity) || '—'}</div></div>}
          <div className="kpi"><div className="v">{d.counts.requests}</div><div className="l">Solicitudes abiertas</div></div>
          <div className={'kpi ' + (d.counts.incidents ? 'err' : '')}><div className="v">{d.counts.incidents}</div><div className="l">Incidentes abiertos</div></div>
          <div className="kpi"><div className="v">{d.counts.changes}</div><div className="l">Cambios de alcance en curso</div></div>
          <div className={'kpi ' + (d.blocked.length ? 'err' : '')}><div className="v">{external ? d.counts.releases : d.blocked.length}</div><div className="l">{external ? 'Liberaciones próximas' : 'Elementos bloqueados'}</div></div>
        </div>
        <div className="grid cols-3">
          <div className="card"><h3>Objetivo y alcance vigente (v{p.scope_version})</h3><p>{p.objective || '—'}</p><div className="mono" style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font-body)', fontSize: 13 }}>{p.scope || 'Sin alcance documentado'}</div><div className="meta" style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>Inicio {fmtDate(p.date_start)} · fin línea base {fmtDate(p.date_end_baseline) || '—'} · fin vigente {fmtDate(p.date_end_current) || '—'} · probable {fmtDate(p.date_end_probable) || '—'}</div></div>
          <div className="card"><h3>Equipo</h3><p><b>PM:</b> {p.pm || '—'}<br /><b>Líder funcional:</b> {p.functional_lead || '—'}<br /><b>Líder técnico:</b> {p.tech_lead || '—'}</p>{!external && <p><b>Equipo interno:</b> {p.team.join(', ') || '—'}</p>}<p><b>Equipo del cliente:</b> {p.client_team.join(', ') || '—'}<br /><b>Responsables de validación:</b> {p.validators.join(', ') || '—'}</p>{p.escalation_path && <p><b>Ruta de escalación:</b> {p.escalation_path}</p>}</div>
          <div className="card"><h3>Hitos</h3><ul className="timeline">{d.milestones.map((m: any) => <li key={m.id}><Link to={`/ops/r/milestones/${m.id}`}>{m.name}</Link> <span className={'badge ' + (m.state === 'validado' ? 'ok' : m.state === 'listo_validacion' ? 'warn' : '')}>{m.state}</span>{m.enables_billing && <span className="badge primary">facturable</span>}<div className="meta">{fmtDate(m.date)}{m.baseline && m.deviation !== 0 && <span className={'badge ' + (m.deviation > 0 ? 'err' : 'ok')} style={{ marginLeft: 6 }}>{m.deviation > 0 ? '+' : ''}{m.deviation} d vs. línea base</span>}</div></li>)}</ul></div>
          <div className="card"><h3>Riesgos principales</h3><ul className="timeline">{d.risks.map((r: any) => <li key={r.id}><Link to={`/ops/r/raid/${r.id}`}>{r.name}</Link> <span className="badge">{r.type}</span> <span className={'badge ' + (r.severity >= 6 ? 'err' : r.severity >= 4 ? 'warn' : '')}>sev {r.severity}</span>{r.requires_client && <span className="badge warn">cliente</span>}</li>)}{!d.risks.length && <li className="empty">Sin riesgos abiertos</li>}</ul></div>
          <div className="card"><h3>Decisiones pendientes y vigentes</h3><ul className="timeline">{d.decisions.map((x: any) => <li key={x.id}><Link to={`/ops/r/decisions/${x.id}`}>{x.name}</Link> <span className={'badge ' + (x.state === 'aprobada' ? 'ok' : 'warn')}>{x.state} v{x.version}</span><div className="meta">{fmtDate(x.date)}</div></li>)}{p.next_decision && <li><b>Próxima decisión:</b> {p.next_decision}</li>}{!d.decisions.length && !p.next_decision && <li className="empty">Sin decisiones pendientes</li>}</ul></div>
          <div className="card"><h3>Entregables en validación</h3><ul className="timeline">{d.in_validation.map((i: any) => <li key={i.id}><Link to={`/ops/r/items/${i.id}`}>{i.name}</Link><div className="meta">{i.validator || 'validador por asignar'} · {i.days} d</div></li>)}{!d.in_validation.length && <li className="empty">Nada en validación</li>}</ul>{!external && d.blocked.length > 0 && <><h3 style={{ marginTop: 12 }}>Bloqueados</h3><ul className="timeline">{d.blocked.map((i: any) => <li key={i.id}><Link to={`/ops/r/items/${i.id}`}>{i.name}</Link><div className="meta">{i.reason} · {i.hours} h</div></li>)}</ul></>}</div>
          <div className="card"><h3>Último reporte de estado</h3>{d.last_report ? <><div><Link to={`/ops/r/status_reports/${d.last_report.id}`}>{d.last_report.name}</Link> <span className={'badge ' + (d.last_report.health === 'verde' ? 'ok' : d.last_report.health === 'rojo' ? 'err' : 'warn')}>{d.last_report.health}</span></div><div className="html-content" style={{ maxHeight: 220, marginTop: 6 }} dangerouslySetInnerHTML={{ __html: d.last_report.summary || '' }} /></> : <div className="empty">Sin reportes</div>}</div>
          <div className="card"><h3>Documentación y ambientes</h3><ul className="timeline">{d.documents.map((x: any) => <li key={x.id}>{x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.name}</a> : <Link to={`/ops/r/documents/${x.id}`}>{x.name}</Link>} <span className="badge">{x.type}</span> <span className="badge ok">v{x.version} vigente</span></li>)}{d.environments.map((e: any) => <li key={'e' + e.id}>{e.url ? <a href={e.url} target="_blank" rel="noreferrer">{e.name}</a> : e.name} <span className="badge primary">{e.type}</span> <span className="meta">{e.version}</span></li>)}{d.links.map((l: any) => <li key={'l' + l.id}><a href={l.url} target="_blank" rel="noreferrer">{l.name}</a> <span className="badge">{l.type}</span></li>)}</ul></div>
          {!external && <div className="card"><h3>Actividad reciente</h3><ul className="timeline">{d.activity.map((a: any, k: number) => <li key={k}><div className="meta">{fmtDate(a.date)} · {a.user || 'sistema'} · {a.action}</div>{a.summary}</li>)}{!d.activity.length && <li className="empty">Sin actividad registrada</li>}</ul></div>}
          <div className="card"><h3>Accesos rápidos</h3><div className="toolbar"><Link className="btn secondary small" to={`/ops/r/requests/new?d.project_id=${p.id}&n.project_id=${encodeURIComponent(p.name)}`}>+ Solicitud</Link>{!external && <><Link className="btn secondary small" to={`/ops/r/items/new?d.project_id=${p.id}&n.project_id=${encodeURIComponent(p.name)}`}>+ Elemento</Link><Link className="btn secondary small" to={`/ops/r/meetings/new?d.project_id=${p.id}&n.project_id=${encodeURIComponent(p.name)}`}>+ Reunión</Link><Link className="btn secondary small" to={`/ops/r/raid/new?d.project_id=${p.id}&n.project_id=${encodeURIComponent(p.name)}`}>+ Riesgo</Link><Link className="btn secondary small" to={`/ops/r/incidents/new?d.project_id=${p.id}&n.project_id=${encodeURIComponent(p.name)}`}>+ Incidente</Link><Link className="btn secondary small" to={`/ops/r/releases/new?d.project_id=${p.id}&n.project_id=${encodeURIComponent(p.name)}`}>+ Liberación</Link></>}</div></div>
        </div>
      </>)}
    </div>
  )
}
