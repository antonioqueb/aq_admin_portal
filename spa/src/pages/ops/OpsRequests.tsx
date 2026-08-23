import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fmtDate, ops } from '../../api'
import { useApp } from '../../context'
import { selLabel } from '../../components/Field'
import { useActiveProject } from '../../project'

const DET: [string, string][] = [['en_alcance', 'Incluida en el alcance'], ['soporte', 'Pertenece a soporte'], ['estimacion', 'Requiere estimación'], ['aprobacion_comercial', 'Necesita aprobación comercial'], ['urgente', 'Urgente por afectación productiva'], ['devolver', 'Devolver por falta de información']]

export default function OpsRequests() {
  const { rapi, schema, toast } = useApp()
  const nav = useNavigate()
  const [rows, setRows] = useState<any[]>([])
  const [state, setState] = useState('open')
  const [sel, setSel] = useState<any>(null)
  const [edit, setEdit] = useState<any>({})
  const [ai, setAi] = useState<any>(null)
  const res = schema?.resources.requests
  const active = useActiveProject()
  const load = useCallback(() => rapi.list('requests', { limit: 200, order: 'create_date desc', filters: state === 'open' ? { state: ['nueva', 'clasificada', 'analisis', 'esperando_info'] } : state === 'all' ? {} : { state }, domain: active ? [['project_id', '=', active.id]] : undefined }).then(r => setRows(r.records)).catch((e: any) => toast(e.message, 'err')), [rapi, state, toast, active])
  useEffect(() => { load() }, [load])
  const openReq = async (r: any) => { const f = await rapi.read('requests', r.id); setSel(f.record); setEdit({ request_type: f.record.request_type, scope_decision: f.record.scope_decision, impact: f.record.impact, missing_info: f.record.missing_info, response: f.record.response, project_id: f.record.project_id }); setAi(null) }
  const save = async () => { try { const r = await rapi.write('requests', sel.id, edit); setSel(r.record); toast('Guardado', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  const act = async (a: string) => { try { await save(); const r = await rapi.action('requests', sel.id, a); setSel(r.record); toast('Listo', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  const askAi = async () => { try { const r = await ops.ai(`requests/${sel.id}/scope`); setAi(r.analysis); if (r.analysis.classification && r.analysis.classification !== 'sin_clasificar') setEdit((e: any) => ({ ...e, request_type: e.request_type === 'sin_clasificar' ? r.analysis.classification : e.request_type })) } catch (e: any) { toast(e.message, 'err') } }
  if (!res) return <div className="empty">Sin acceso</div>
  return (
    <div>
      <div className="toolbar"><div><h1>Bandeja de solicitudes{active ? ` · ${active.name}` : ''}</h1><div style={{ color: 'var(--muted)', fontSize: 12 }}>Un solo embudo: cliente, empleado del cliente, reunión, correo, consultor, soporte, Dirección, incidente en producción, revisión de calidad.</div></div><span className="spacer" />
        <select value={state} onChange={e => setState(e.target.value)} style={{ width: 'auto' }}><option value="open">Abiertas</option><option value="convertida">Convertidas</option><option value="respondida">Respondidas</option><option value="rechazada">Rechazadas</option><option value="remitida_admin">Remitidas a Administración</option><option value="all">Todas</option></select>
        <button className="btn" onClick={() => nav('/ops/r/requests/new' + (active ? `?d.project_id=${active.id}&n.project_id=${encodeURIComponent(active.name)}` : ''))}>+ Nueva solicitud</button></div>
      <div className="two">
        <div className="card tight">
          <div className="table-wrap"><table className="list"><thead><tr><th>Solicitud</th><th>Organización</th><th>Origen</th><th>Clasificación</th><th>Urgencia</th><th>Estado</th><th>Fecha</th></tr></thead>
            <tbody>{rows.map(r => <tr key={r.id} className="row" onClick={() => openReq(r)} style={sel?.id === r.id ? { outline: '1px solid var(--primary)' } : {}}><td>{r.name}</td><td>{r.partner_id?.name}</td><td>{selLabel(res.fields.source, r.source)}</td><td>{selLabel(res.fields.request_type, r.request_type)}</td><td><span className={'badge ' + (r.urgency === 'critica' ? 'err' : r.urgency === 'alta' ? 'warn' : '')}>{r.urgency}</span></td><td><span className="badge">{r.state}</span></td><td>{fmtDate(r.create_date)}</td></tr>)}</tbody></table></div>
          {rows.length === 0 && <div className="empty">Sin solicitudes</div>}
        </div>
        <div>
          {!sel ? <div className="card empty">Seleccione una solicitud para clasificarla.</div> : (
            <div className="card">
              <h2>{sel.name}</h2>
              <div style={{ fontSize: 13, color: 'var(--muted)' }}>{sel.partner_id?.name} · {selLabel(res.fields.source, sel.source)} · {sel.requester_partner_id?.name || sel.requester_user_id?.name || ''} {sel.requester_department && '· ' + sel.requester_department}</div>
              <p style={{ whiteSpace: 'pre-wrap' }}>{sel.description}</p>
              {sel.potential_duplicate_ids?.length > 0 && <div className="alert err">Posibles duplicados: {sel.potential_duplicate_ids.map((d: any) => <Link key={d.id} to={`/ops/r/requests/${d.id}`} style={{ marginRight: 8 }}>{d.name}</Link>)}</div>}
              {ai && <div className="copilot"><h4>Copiloto · comparación con el alcance</h4><div><b>{ai.in_scope === true ? 'Parece incluida en el alcance' : ai.in_scope === false ? 'Parece fuera del alcance' : 'No concluyente'}</b> — {ai.reason}</div><div className="disclaimer">Propuesta; la determinación la registra una persona.</div></div>}
              <div className="field"><label>Proyecto</label><select value={edit.project_id?.id || ''} onChange={e => setEdit({ ...edit, project_id: e.target.value ? { id: Number(e.target.value), name: '' } : null })}><option value="">—</option>{[sel.project_id].filter(Boolean).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</select><div className="help">Para cambiar a otro proyecto use la ficha completa.</div></div>
              <div className="field"><label>Clasificación</label><select value={edit.request_type || ''} onChange={e => setEdit({ ...edit, request_type: e.target.value })}>{res.fields.request_type.selection!.map(s => <option key={s[0]} value={s[0]}>{s[1]}</option>)}</select></div>
              <div className="field"><label>Determinación</label><select value={edit.scope_decision || 'pendiente'} onChange={e => setEdit({ ...edit, scope_decision: e.target.value })}><option value="pendiente">Pendiente de análisis</option>{DET.map(d => <option key={d[0]} value={d[0]}>{d[1]}</option>)}</select></div>
              <div className="field"><label>Impacto identificado</label><textarea value={edit.impact || ''} onChange={e => setEdit({ ...edit, impact: e.target.value })} /></div>
              {edit.scope_decision === 'devolver' && <div className="field"><label>Información faltante</label><textarea value={edit.missing_info || ''} onChange={e => setEdit({ ...edit, missing_info: e.target.value })} /></div>}
              <div className="field"><label>Respuesta al solicitante</label><textarea value={edit.response || ''} onChange={e => setEdit({ ...edit, response: e.target.value })} /></div>
              <div className="toolbar">
                <button className="btn" onClick={save}>Guardar</button>
                <button className="btn secondary" onClick={askAi}>Comparar con alcance (IA)</button>
                <button className="btn secondary" onClick={() => act('action_classify')}>Clasificar</button>
              </div>
              <div className="toolbar">
                <button className="btn secondary small" onClick={() => act('action_convert_item')}>→ Elemento de trabajo</button>
                <button className="btn secondary small" onClick={() => act('action_convert_change')}>→ Cambio de alcance</button>
                <button className="btn secondary small" onClick={() => act('action_convert_incident')}>→ Incidente</button>
                <button className="btn secondary small" onClick={() => act('action_respond')}>Responder</button>
                <button className="btn danger small" onClick={() => act('action_reject')}>Rechazar</button>
                <Link className="btn link small" to={`/ops/r/requests/${sel.id}`}>Ficha completa</Link>
              </div>
              {(sel.item_id || sel.change_id || sel.incident_id) && <div className="alert ok">Convertida: {sel.item_id && <Link to={`/ops/r/items/${sel.item_id.id}`}>elemento {sel.item_id.name}</Link>}{sel.change_id && <Link to={`/ops/r/changes/${sel.change_id.id}`}>cambio {sel.change_id.name}</Link>}{sel.incident_id && <Link to={`/ops/r/incidents/${sel.incident_id.id}`}>incidente {sel.incident_id.name}</Link>}</div>}
              <p style={{ fontSize: 11, color: 'var(--mute2)' }}>Regla: el cliente nunca crea tareas; Operaciones analiza y convierte. Los cambios de alcance requieren estimación, impacto y autorización comercial en Administración.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
