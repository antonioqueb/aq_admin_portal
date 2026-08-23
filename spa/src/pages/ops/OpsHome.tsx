import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fmtDate, ops } from '../../api'
import { useApp } from '../../context'

const STATE: Record<string, string> = { backlog: 'Backlog', por_hacer: 'Por hacer', en_progreso: 'En progreso', bloqueado: 'Bloqueado', desarrollo_completado: 'Dev completado', revision_tecnica: 'Revisión técnica', qa_interno: 'QA', correccion: 'Corrección', regresion: 'Regresión', listo_validacion: 'Listo p/ validar', validacion_cliente: 'Validación cliente', aceptado: 'Aceptado', listo_liberar: 'Listo p/ liberar', liberado: 'Liberado', verificado: 'Verificado', cerrado: 'Cerrado' }
const Item = ({ i }: { i: any }) => <li><Link to={`/ops/r/items/${i.id}`}>{i.name}</Link> {i.priority === '2' && <span className="badge err">crítica</span>}{i.waiting_client && <span className="badge warn">cliente</span>}<div className="meta">{i.project} · {STATE[i.state] || i.state}{i.due && ' · ' + fmtDate(i.due)}{i.blocked_reason && ' · ' + i.blocked_reason}</div></li>

export default function OpsHome() {
  const { user, schema, toast } = useApp()
  const external = !!(schema?.is_external || user?.is_external)
  if (external) return <ClientHome />
  return <MyWork toast={toast} />
}

function MyWork({ toast }: { toast: any }) {
  const [d, setD] = useState<any>(null)
  const nav = useNavigate()
  const load = useCallback(() => ops.mywork().then(setD).catch((e: any) => toast(e.message, 'err')), [toast])
  useEffect(() => { load() }, [load])
  if (!d) return <div className="empty">Preparando su agenda…</div>
  const stopTimer = async () => { await ops.timerStop(); toast('Temporizador detenido', 'ok'); load() }
  return (
    <div>
      <div className="hero">
        <div><div className="tag">Operaciones · agenda de ejecución</div><h1>Mi trabajo</h1><div className="pulse">{d.assigned.length} asignados · {d.today.length} para hoy · {d.blocked.length} bloqueados · {d.approvals.length} aprobaciones · {d.notifications_unread} notificaciones</div></div>
        <div className="toolbar" style={{ margin: 0 }}>
          {d.running_timer ? <div className="timer">⏱ {d.running_timer.item || d.running_timer.project || 'Temporizador'} <button className="btn small" onClick={stopTimer}>Detener</button></div> : <button className="btn secondary small" onClick={() => nav('/ops/time')}>⏱ Registrar tiempo</button>}
          <span className="badge primary">Semana: {d.hours_week.toFixed(1)} h registradas · {d.hours_pending.toFixed(0)} h pendientes</span>
        </div>
      </div>
      <div className="grid cols-3">
        <div className="card"><h3>Compromisos de hoy</h3><ul className="timeline">{d.today.map((i: any) => <Item key={i.id} i={i} />)}{!d.today.length && <li className="empty">Sin vencimientos hoy</li>}</ul></div>
        <div className="card"><h3>Esta semana</h3><ul className="timeline">{d.week.map((i: any) => <Item key={i.id} i={i} />)}{!d.week.length && <li className="empty">Nada más esta semana</li>}</ul></div>
        <div className="card"><h3>Siguientes acciones de proyectos</h3><ul className="timeline">{d.next_actions.map((p: any) => <li key={p.id}><Link to={`/ops/projects/${p.id}`}>{p.project}</Link> {p.missing && <span className="badge err">sin siguiente acción</span>}<div className="meta">{p.next_action || '—'} · {p.owner || 'sin responsable'} · {fmtDate(p.date)}</div></li>)}{!d.next_actions.length && <li className="empty">Todo con siguiente acción</li>}</ul></div>
        <div className="card"><h3>Bloqueados</h3><ul className="timeline">{d.blocked.map((i: any) => <Item key={i.id} i={i} />)}{!d.blocked.length && <li className="empty">Sin bloqueos</li>}</ul></div>
        <div className="card"><h3>Aprobaciones pendientes</h3><ul className="timeline">{d.approvals.map((a: any, k: number) => <li key={k}><Link to={a.kind === 'acceptance' ? `/ops/r/acceptances/${a.id}` : a.kind === 'decision' ? `/ops/r/decisions/${a.id}` : a.kind === 'release' ? `/ops/r/releases/${a.id}` : `/ops/r/timesheets/${a.id}`}>{a.name}</Link><div className="meta">{a.kind} · {a.project}{a.due && ' · ' + fmtDate(a.due)}</div></li>)}{!d.approvals.length && <li className="empty">Sin aprobaciones</li>}</ul></div>
        <div className="card"><h3>Solicitudes por responder</h3><ul className="timeline">{d.requests.map((r: any) => <li key={r.id}><Link to={`/ops/r/requests/${r.id}`}>{r.name}</Link> <span className={'badge ' + (r.urgency === 'critica' ? 'err' : r.urgency === 'alta' ? 'warn' : '')}>{r.urgency}</span><div className="meta">{r.org} · {r.state} · {r.age_days} d</div></li>)}{!d.requests.length && <li className="empty">Bandeja vacía</li>}</ul><Link to="/ops/requests">Abrir bandeja →</Link></div>
        <div className="card"><h3>Menciones</h3><ul className="timeline">{d.mentions.map((m: any) => <li key={m.id}><Link to={m.resource ? `/ops/r/${m.resource}/${m.res_id}` : '/ops/notifications'}>{m.title}</Link><div className="meta">{fmtDate(m.date)}</div></li>)}{!d.mentions.length && <li className="empty">Sin menciones</li>}</ul></div>
        <div className="card"><h3>Reuniones próximas</h3><ul className="timeline">{d.meetings.map((m: any) => <li key={m.id}><Link to={`/ops/r/meetings/${m.id}`}>{m.name}</Link><div className="meta">{m.project} · {m.date}</div></li>)}{!d.meetings.length && <li className="empty">Sin reuniones programadas</li>}</ul></div>
        <div className="card"><h3>Dependen de mí</h3><ul className="timeline">{d.depends_on_me.map((i: any) => <Item key={i.id} i={i} />)}{!d.depends_on_me.length && <li className="empty">Nadie espera por usted</li>}</ul></div>
        <div className="card"><h3>Sin movimiento (≥ 7 días)</h3><ul className="timeline">{d.stale.map((i: any) => <Item key={i.id} i={i} />)}{!d.stale.length && <li className="empty">Todo fluye</li>}</ul></div>
        <div className="card"><h3>Riesgos donde debo intervenir</h3><ul className="timeline">{d.risks.map((r: any) => <li key={r.id}><Link to={`/ops/r/raid/${r.id}`}>{r.name}</Link> <span className="badge">{r.type}</span><div className="meta">{r.project} · severidad {r.severity}{r.due && ' · ' + fmtDate(r.due)}</div></li>)}{!d.risks.length && <li className="empty">Sin riesgos asignados</li>}</ul></div>
        <div className="card"><h3>Incidentes</h3><ul className="timeline">{d.incidents.map((i: any) => <li key={i.id}><Link to={`/ops/r/incidents/${i.id}`}>{i.name}</Link> <span className={'badge ' + (i.severity === 'S1' ? 'err' : i.severity === 'S2' ? 'warn' : '')}>{i.severity}</span>{i.sla_breached && <span className="badge err">SLA</span>}<div className="meta">{i.project} · {i.step}</div></li>)}{!d.incidents.length && <li className="empty">Sin incidentes abiertos</li>}</ul></div>
        <div className="card"><h3>Trabajo asignado</h3><ul className="timeline">{d.assigned.slice(0, 15).map((i: any) => <Item key={i.id} i={i} />)}</ul><Link to="/ops/board?view=personal">Ver todo →</Link></div>
      </div>
    </div>
  )
}

function ClientHome() {
  const { toast, user } = useApp()
  const [d, setD] = useState<any>(null)
  const [answer, setAnswer] = useState<Record<number, string>>({})
  const [reason, setReason] = useState<Record<number, string>>({})
  const load = useCallback(() => ops.clientHome().then(setD).catch((e: any) => toast(e.message, 'err')), [toast])
  useEffect(() => { load() }, [load])
  if (!d) return <div className="empty">Cargando…</div>
  const decide = async (id: number, decision: string) => { try { await ops.decide(id, decision, reason[id]); toast('Decisión registrada (inmutable)', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  return (
    <div>
      <div className="hero"><div><div className="tag">{d.organization}</div><h1>Estado de sus proyectos</h1><div className="pulse">{d.projects.length} proyectos · {d.approvals.length} aprobaciones pendientes · {d.questions.length} preguntas por responder</div></div>
        <div className="toolbar" style={{ margin: 0 }}><Link className="btn" to="/ops/r/requests/new">+ Registrar solicitud</Link></div></div>
      <div className="grid cols-3">
        {d.projects.map((p: any) => <div className="card" key={p.id}><h2><span className={'health ' + p.health} />{p.name}</h2><div className="meta" style={{ color: 'var(--muted)', fontSize: 12 }}>{p.stage} · PM {p.pm || '—'}</div><p>Próximo hito: <b>{p.next_milestone || '—'}</b> {p.next_milestone_date && fmtDate(p.next_milestone_date)}</p>{p.in_validation > 0 && <span className="badge warn">{p.in_validation} entregables en su validación</span>}<div><Link to={`/ops/projects/${p.id}`}>Ver centro de mando →</Link></div></div>)}
      </div>
      <div className="grid cols-2">
        <div className="card"><h3>Aprobar o rechazar entregables</h3>{d.approvals.length === 0 && <div className="empty">Nada pendiente de su aprobación</div>}
          {d.approvals.map((a: any) => <div key={a.id} className="card tight" style={{ marginBottom: 8 }}><b>{a.name}</b> <span className="badge">{a.project}</span>{a.department && <span className="badge primary">{a.department}</span>}<div style={{ fontSize: 13, marginTop: 6 }}><b>Criterios:</b> {a.criteria || '—'}<br /><b>Evidencia:</b> {a.evidence || '—'}{a.due && <><br /><b>Responder antes de:</b> {fmtDate(a.due)}</>}</div>
            <input type="text" placeholder="Motivo (obligatorio para rechazar o solicitar cambios)" value={reason[a.id] || ''} onChange={e => setReason({ ...reason, [a.id]: e.target.value })} style={{ marginTop: 6 }} />
            <div className="toolbar" style={{ marginTop: 6 }}><button className="btn small" onClick={() => decide(a.id, 'aprobado')}>Aprobar</button><button className="btn secondary small" onClick={() => decide(a.id, 'cambios')}>Solicitar cambios</button><button className="btn danger small" onClick={() => decide(a.id, 'rechazado')}>Rechazar</button></div></div>)}
        </div>
        <div className="card"><h3>Preguntas por responder</h3>{d.questions.length === 0 && <div className="empty">Sin preguntas abiertas</div>}
          {d.questions.map((q: any) => <div key={q.id} style={{ marginBottom: 8 }}><b>{q.name}</b><div className="meta" style={{ fontSize: 12, color: 'var(--muted)' }}>{q.project} · {q.meeting}</div><div className="toolbar"><input type="text" placeholder="Su respuesta" value={answer[q.id] || ''} onChange={e => setAnswer({ ...answer, [q.id]: e.target.value })} /><button className="btn small" onClick={() => ops.answer(q.id, answer[q.id] || '').then(() => { toast('Respuesta enviada', 'ok'); load() })}>Responder</button></div></div>)}
        </div>
        <div className="card"><h3>Hitos y roadmap autorizado</h3><ul className="timeline">{d.milestones.map((m: any) => <li key={m.id}>{m.name} <span className="badge">{m.state}</span><div className="meta">{m.project} · {fmtDate(m.date)}</div></li>)}{d.roadmap.map((r: any) => <li key={'r' + r.id}><Link to={`/ops/r/items/${r.id}`}>{r.name}</Link> <span className="badge">{r.type}</span><div className="meta">{r.project} · {fmtDate(r.due)} · {STATE[r.state] || r.state}</div></li>)}</ul></div>
        <div className="card"><h3>Compromisos de su parte</h3><ul className="timeline">{d.commitments.map((c: any) => <li key={c.id}><Link to={`/ops/r/items/${c.id}`}>{c.name}</Link><div className="meta">{c.project} · {fmtDate(c.due)}</div></li>)}{!d.commitments.length && <li className="empty">Nada pendiente de su parte</li>}</ul></div>
        <div className="card"><h3>Mis solicitudes</h3><ul className="timeline">{d.requests.map((r: any) => <li key={r.id}><Link to={`/ops/r/requests/${r.id}`}>{r.name}</Link> <span className="badge">{r.state}</span><div className="meta">{fmtDate(r.date)} · {r.type}{r.response && ' · Respuesta: ' + r.response.slice(0, 80)}</div></li>)}{!d.requests.length && <li className="empty">Aún no ha registrado solicitudes</li>}</ul></div>
        <div className="card"><h3>Pruebas UAT en las que participa</h3><ul className="timeline">{d.tests.map((t: any) => <li key={t.id}><Link to={`/ops/r/test_cases/${t.id}`}>{t.name}</Link> <span className={'badge ' + (t.result === 'pass' ? 'ok' : t.result === 'fail' ? 'err' : '')}>{t.result}</span><div className="meta">{t.project}{t.department && ' · ' + t.department}</div></li>)}{!d.tests.length && <li className="empty">Sin pruebas asignadas</li>}</ul></div>
        <div className="card"><h3>Decisiones</h3><ul className="timeline">{d.decisions.map((x: any) => <li key={x.id}><Link to={`/ops/r/decisions/${x.id}`}>{x.name}</Link><div className="meta">{fmtDate(x.date)} · {x.decision?.slice(0, 100)}</div></li>)}</ul></div>
        <div className="card"><h3>Reuniones y próximas fechas</h3><ul className="timeline">{d.meetings.map((m: any) => <li key={m.id}><Link to={`/ops/r/meetings/${m.id}`}>{m.name}</Link><div className="meta">{m.project} · {m.date} · {m.state}</div></li>)}</ul></div>
        <div className="card"><h3>Riesgos que requieren su intervención</h3><ul className="timeline">{d.risks.map((r: any) => <li key={r.id}>{r.name}<div className="meta">{r.project} · severidad {r.severity} · {r.owner || 'por asignar'}</div></li>)}{!d.risks.length && <li className="empty">Ninguno</li>}</ul></div>
        <div className="card"><h3>Incidencias</h3><ul className="timeline">{d.incidents.map((i: any) => <li key={i.id}><Link to={`/ops/r/incidents/${i.id}`}>{i.name}</Link> <span className="badge">{i.severity}</span><div className="meta">{i.project} · {i.step}</div></li>)}{!d.incidents.length && <li className="empty">Sin incidencias</li>}</ul></div>
        <div className="card"><h3>Documentación autorizada</h3><ul className="timeline">{d.documents.map((x: any) => <li key={x.id}>{x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.name}</a> : x.name} <span className="badge">{x.type}</span><div className="meta">{x.project} · v{x.version}</div></li>)}{!d.documents.length && <li className="empty">Sin documentos compartidos</li>}</ul></div>
      </div>
      <p style={{ color: 'var(--mute2)', fontSize: 11 }}>Usted ve únicamente la información de {user?.organization_name} autorizada para su perfil.</p>
    </div>
  )
}
