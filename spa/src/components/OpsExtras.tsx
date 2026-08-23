import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ops } from '../api'
import { useApp } from '../context'
import { STATES } from './WorkViews'

const INC_STEPS = ['reportado', 'clasificado', 'contencion', 'diagnostico', 'correccion', 'pruebas', 'liberacion', 'verificacion', 'comunicacion', 'rca', 'prevencion', 'cerrado']
const INC_LABEL: Record<string, string> = { reportado: 'Reporte', clasificado: 'Severidad', contencion: 'Contención', diagnostico: 'Diagnóstico', correccion: 'Corrección', pruebas: 'Pruebas', liberacion: 'Liberación', verificacion: 'Verificación', comunicacion: 'Comunicación', rca: 'Causa raíz', prevencion: 'Prevención', cerrado: 'Cerrado' }

export default function OpsExtras({ resource, record, reload }: { resource: string; record: any; reload: () => void }) {
  const { toast, user, schema, rapi } = useApp()
  const [ai, setAi] = useState<any>(null)
  const [reason, setReason] = useState('')
  const [agreements, setAgreements] = useState<any[]>([])
  const external = !!(schema?.is_external || user?.is_external)
  useEffect(() => { if (resource === 'meetings') rapi.list('agreements', { domain: [['meeting_id', '=', record.id]], limit: 100 }).then(r => setAgreements(r.records)).catch(() => {}) }, [resource, record.id, rapi])
  const run = async (fn: () => Promise<any>, ok?: string) => { try { const r = await fn(); if (ok) toast(ok, 'ok'); return r } catch (e: any) { toast(e.message, 'err') } }
  const Copilot = ({ text }: { text: any }) => text ? <div className="copilot"><h4>Copiloto · propuesta (no vinculante)</h4><div style={{ whiteSpace: 'pre-wrap' }}>{typeof text === 'string' ? text : JSON.stringify(text, null, 2)}</div><div className="disclaimer">La IA no aprueba, no cambia alcance ni fechas, no acepta entregables, no cierra incidentes.</div></div> : null

  if (resource === 'projects') return <div className="alert info" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>Centro de mando del proyecto (objetivo, hitos, salud, horas, riesgos, decisiones, validaciones, reporte y accesos) <Link className="btn small" to={`/ops/projects/${record.id}`}>Abrir centro de mando</Link>{schema?.ai_available === false && !external && <span style={{ fontSize: 11, color: 'var(--muted)' }}>· IA en modo heurístico (configure DeepSeek)</span>}</div>

  if (resource === 'acceptances') {
    if (record.decision !== 'pendiente') return <div className="alert ok">Validación decidida el {record.decided_at} por {record.validator_user_id?.name} · huella {String(record.signature_hash || '').slice(0, 16)}… (registro inmutable)</div>
    const canDecide = external ? ['client_sponsor', 'client_po', 'client_validator'].includes(user?.ops_role || '') : ['platform_owner', 'ops_director', 'pm'].includes(user?.ops_role || '')
    if (!canDecide) return <div className="alert info">Pendiente de decisión del validador {record.validator_partner_id?.name || ''}{record.department && ` (${record.department})`}.</div>
    return <div className="card" style={{ borderColor: 'var(--primary)' }}><h3>Aceptación electrónica</h3><p style={{ fontSize: 13 }}><b>Criterios:</b> {record.criteria || '—'}<br /><b>Evidencia:</b> {record.evidence || '—'}</p><input type="text" placeholder="Motivo (obligatorio para cambios o rechazo)" value={reason} onChange={e => setReason(e.target.value)} /><div className="toolbar" style={{ marginTop: 8 }}><button className="btn" onClick={() => run(() => ops.decide(record.id, 'aprobado', reason), 'Aprobado · registro inmutable').then(reload)}>Aprobar</button><button className="btn secondary" onClick={() => run(() => ops.decide(record.id, 'cambios', reason), 'Cambios solicitados').then(reload)}>Solicitar cambios</button><button className="btn danger" onClick={() => run(() => ops.decide(record.id, 'rechazado', reason), 'Rechazado').then(reload)}>Rechazar</button></div></div>
  }

  if (resource === 'meetings' && !external) return (
    <div className="card" style={{ borderColor: 'var(--purple-bright)' }}>
      {(record.google_event_id || record.meet_code) && <div className="alert info">Sincronizada con Google Calendar{record.meet_code && ` · Meet ${record.meet_code}`}{record.google_doc_url && <> · <a href={record.google_doc_url} target="_blank" rel="noreferrer">Minuta en Docs</a></>}</div>}
      <div className="toolbar"><h3 style={{ margin: 0 }}>Copiloto de reunión</h3><span className="spacer" /><button className="btn secondary small" onClick={() => run(() => ops.ai(`meetings/${record.id}/summarize`), 'Propuestas generadas · confirme las que procedan').then(r => { if (r) { setAi(r.proposals?.summary || r.proposals); reload(); rapi.list('agreements', { domain: [['meeting_id', '=', record.id]], limit: 100 }).then(x => setAgreements(x.records)) } })}>Resumir y proponer acuerdos</button></div>
      <Copilot text={ai} />
      {agreements.length > 0 && <><h3>Acuerdos y compromisos</h3>{agreements.map(a => <div key={a.id} className="wl"><span style={{ flex: 1 }}>{a.name} <span className="badge">{a.kind}</span>{a.proposed_by_ai && <span className="badge primary">IA</span>}{a.is_contractual && <span className="badge warn">posible compromiso contractual → control de cambios</span>}</span><span style={{ fontSize: 12, color: 'var(--muted)' }}>{a.owner_id?.name || a.owner_partner_id?.name || '—'} · {a.due_date || 'sin fecha'}</span>{a.confirmed ? <span className="badge ok">confirmado{a.item_id && ' · tarea'}</span> : <button className="btn small" onClick={() => run(() => rapi.action('agreements', a.id, 'action_confirm'), 'Confirmado: tarea/cambio creado').then(() => rapi.list('agreements', { domain: [['meeting_id', '=', record.id]], limit: 100 }).then(x => setAgreements(x.records)))}>Confirmar</button>}</div>)}</>}
      <p style={{ fontSize: 11, color: 'var(--mute2)' }}>La transcripción es evidencia histórica; la decisión validada es la fuente operativa. Ninguna minuta reemplaza una decisión formal ni crea compromisos contractuales.</p>
    </div>)

  if (resource === 'items') {
    const idx = STATES.findIndex(s => s[0] === record.state)
    return <div className="card tight">
      <div className="step-flow">{STATES.map((s, i) => <span key={s[0]} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{s[1]}</span>)}</div>
      {!external && <div className="toolbar" style={{ marginTop: 8 }}>
        <button className="btn secondary small" onClick={() => run(() => ops.timerStart({ item_id: record.id }), 'Temporizador iniciado')}>▶ Temporizador</button>
        <button className="btn secondary small" onClick={() => run(() => ops.ai(`items/${record.id}/tests`), 'Casos de prueba propuestos (pestaña Casos de prueba)').then(reload)}>Proponer casos de prueba (IA)</button>
        <button className="btn secondary small" onClick={() => run(() => ops.ai(`items/${record.id}/dependencies`)).then(r => r && setAi(r.suggestions.length ? 'Dependencias sugeridas: ' + r.suggestions.map((s: any) => s.name).join(', ') : 'Sin dependencias sugeridas'))}>Sugerir dependencias (IA)</button>
        {record.state === 'por_hacer' || record.state === 'backlog' ? <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'en_progreso' }), 'En progreso').then(reload)}>Iniciar</button> : null}
        {record.state === 'en_progreso' && <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'desarrollo_completado' }), 'Desarrollo completado (no es entregado)').then(reload)}>Desarrollo completado</button>}
        {record.state === 'desarrollo_completado' && <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'revision_tecnica' })).then(reload)}>→ Revisión técnica</button>}
        {record.state === 'revision_tecnica' && <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'qa_interno' })).then(reload)}>→ QA interno</button>}
        {record.state === 'qa_interno' && <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'regresion' })).then(reload)}>→ Regresión</button>}
        {record.accepted && record.state === 'aceptado' && <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'listo_liberar' })).then(reload)}>→ Listo para liberar</button>}
        {record.state === 'verificado' && <button className="btn small" onClick={() => run(() => ops.move(record.id, { state: 'cerrado' })).then(reload)}>Cerrar</button>}
      </div>}
      <Copilot text={ai} />
      {record.waiting_client && <div className="alert info">Esperando al cliente desde {record.waiting_client_since}</div>}
    </div>
  }

  if (resource === 'requests' && !external) return <div className="alert info" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>Clasifique en la bandeja con determinación y conversión guiada. <Link className="btn small" to="/ops/requests">Abrir bandeja</Link><button className="btn secondary small" onClick={() => run(() => ops.ai(`requests/${record.id}/scope`)).then(r => r && setAi(`${r.analysis.in_scope === true ? 'Parece en alcance' : r.analysis.in_scope === false ? 'Parece fuera de alcance' : 'No concluyente'} — ${r.analysis.reason}`))}>Comparar con alcance (IA)</button><div style={{ width: '100%' }}><Copilot text={ai} /></div></div>

  if (resource === 'incidents') {
    const idx = INC_STEPS.indexOf(record.step)
    return <div className="card tight"><div className="step-flow">{INC_STEPS.map((s, i) => <span key={s} className={i < idx ? 'done' : i === idx ? 'now' : ''}>{i + 1}. {INC_LABEL[s]}</span>)}</div>
      <div className="toolbar" style={{ marginTop: 8 }}>{record.sla_breached && <span className="badge err">SLA incumplido</span>}<span className="badge">respuesta {record.sla_response_hours} h · resolución {record.sla_resolution_hours} h</span>{!external && <button className="btn secondary small" onClick={() => run(() => ops.ai(`incidents/${record.id}/summary`)).then(r => r && setAi(r.text))}>Resumir historial (IA)</button>}</div><Copilot text={ai} /></div>
  }

  if (resource === 'releases') {
    const gate = [['backup_verified', 'Respaldo / punto de recuperación verificado', !!record.backup_verified], ['owner_id', 'Responsable del despliegue', !!record.owner_id], ['test_evidence', 'Evidencia de pruebas', !!record.test_evidence], ['approved_by_id', 'Aprobación', !!record.approved_by_id], ['rollback_plan', 'Plan de reversión', !!record.rollback_plan], ['post_verification', 'Verificación posterior (tras desplegar)', !!record.post_verification]] as [string, string, boolean][]
    return <div className="card tight"><h3>Compuerta de liberación {record.env_type === 'prod' && <span className="badge err">producción</span>}</h3><div className="checklist">{gate.map(g => <label key={g[0]}><input type="checkbox" checked={g[2]} readOnly /><span className={g[2] ? 'done' : ''}>{g[1]}</span></label>)}</div>{record.gate_missing && <div className="alert err">Falta: {record.gate_missing}</div>}{record.review_item_id && <div className="alert ok">Revisión post-liberación creada: {record.review_item_id.name}</div>}</div>
  }

  if (resource === 'decisions') return <div className={'alert ' + (record.state === 'aprobada' ? 'ok' : 'info')}>{record.state === 'aprobada' ? `Decisión aprobada v${record.version} · inmutable. Para modificarla cree una nueva versión.` : `Decisión propuesta v${record.version}. Al aprobarse queda inmutable y versionada.`}{record.replaces_id && <> · reemplaza a <Link to={`/ops/r/decisions/${record.replaces_id.id}`}>{record.replaces_id.name}</Link></>}</div>

  if (resource === 'changes') return <div className="alert info">Flujo: solicitud → clasificación → análisis → estimación e impacto → <b>autorización comercial en Administración</b> → backlog → ejecución → prueba → aceptación → evento facturable. Estado actual: <b>{record.state}</b>{record.commercial_ref && ` · ref. comercial ${record.commercial_ref}`}</div>

  if (resource === 'timesheets' && record.running) return <div className="alert info">Temporizador en curso desde {record.timer_start} <button className="btn small" onClick={() => run(() => ops.timerStop(), 'Detenido').then(reload)}>Detener</button></div>
  return null
}
