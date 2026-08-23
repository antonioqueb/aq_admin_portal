import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, ops, today } from '../../api'
import { useApp } from '../../context'
import { useActiveProject } from '../../project'
import Many2one from '../../components/Many2one'

/** Generador y mapa de sesiones: folio automático, evento con Meet e invitación, histórico completo por proyecto. */
export default function OpsSessions() {
  const { toast, user, schema } = useApp()
  const active = useActiveProject()
  const [d, setD] = useState<any>(null)
  const [form, setForm] = useState<any>({ project: null, type: '', date: today(), time: '10:00', duration: '', extra: '', agenda: '' })
  const [busy, setBusy] = useState(false)
  const [group, setGroup] = useState<'fecha' | 'proyecto'>('proyecto')
  const [inbox, setInbox] = useState<any[]>([])
  const external = !!(schema?.is_external || user?.is_external)
  const owner = ['platform_owner', 'ops_director'].includes(user?.ops_role || '')
  const { rapi } = useApp()
  const load = useCallback(() => { api.get('/ops/sessions/map', active ? { project_id: active.id } : {}).then(setD).catch((e: any) => toast(e.message, 'err')); rapi.list('google_inbox', { limit: 30, order: 'date desc', filters: { category: 'meeting_notes' } }).then(r => setInbox(r.records)).catch(() => {}) }, [toast, active, rapi])
  useEffect(() => { load(); if (active && !form.project) setForm((f: any) => ({ ...f, project: { id: active.id, name: active.name } })) }, [load])  // eslint-disable-line
  const gen = async () => {
    if (!form.project || !form.type) { toast('Elija proyecto y tipo de sesión', 'err'); return }
    setBusy(true)
    try {
      const r = await api.post('/ops/sessions/generate', { project_id: form.project.id, type_id: Number(form.type), start: `${form.date}T${form.time}:00`, duration: form.duration ? Number(form.duration) : undefined, extra_emails: form.extra.split(/[,;\s]+/).filter((x: string) => x.includes('@')), agenda: form.agenda || undefined })
      toast(`Sesión creada: ${r.meeting.name} · invitaciones enviadas`, 'ok')
      if (r.meeting.meet) navigator.clipboard?.writeText(r.meeting.meet)
      load()
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  const processAi = async (id: number) => { try { await api.post(`/ops/r/meetings/${id}/action/action_process_ai`); toast('Procesada: resumen, Doc, correo y actividades', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  const grouped = useMemo(() => {
    if (!d) return []
    if (group === 'fecha') return [['Todas las sesiones', d.sessions]] as [string, any[]][]
    const m: Record<string, any[]> = {}
    d.sessions.forEach((s: any) => { (m[s.project] = m[s.project] || []).push(s) })
    return Object.entries(m)
  }, [d, group])
  if (!d) return <div className="empty">Cargando mapa de sesiones…</div>
  return (
    <div>
      <div className="hero"><div><div className="tag">Sesiones · nomenclatura y secuencia históricas</div><h1>Sesiones{active ? ` · ${active.name}` : ''}</h1><div className="pulse">{d.sessions.length} sesiones registradas · {d.sessions.filter((s: any) => s.processed).length} procesadas con IA · {d.sessions.filter((s: any) => s.state === 'realizada' && !s.has_transcript && !s.processed).length} históricas sin transcripción (pendiente futuro)</div></div>
        <div className="toolbar" style={{ margin: 0 }}>
          {!external && <button className="btn secondary small" onClick={() => api.post('/ops/sessions/export').then(r => { toast('Mapa exportado', 'ok'); window.open(r.url, '_blank') }).catch((e: any) => toast(e.message, 'err'))}>Descargar mapa (Sheets)</button>}
          {owner && <button className="btn secondary small" onClick={() => { if (confirm('¿Importar el histórico de Calendar (12 meses)? Es idempotente.')) api.post('/ops/sessions/import-history', { months: 12 }).then(r => { toast(`Histórico: ${JSON.stringify(r.stats)}`, 'ok'); load() }).catch((e: any) => toast(e.message, 'err')) }}>Importar histórico</button>}
        </div></div>
      {!external && (
        <div className="card" style={{ borderColor: 'var(--primary)' }}>
          <h3>Generar sesión (folio, Meet e invitación automáticos)</h3>
          <div className="grid cols-4">
            <div className="field"><label>Proyecto</label><Many2one model="aq.ops.project" value={form.project} onChange={v => setForm({ ...form, project: v })} resource="projects" /></div>
            <div className="field"><label>Tipo de sesión</label><select value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}><option value="">—</option>{d.types.map((t: any) => <option key={t.id} value={t.id}>{t.name} · {t.duration} min</option>)}</select></div>
            <div className="field"><label>Fecha</label><input type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} /></div>
            <div className="field"><label>Hora (CDMX)</label><input type="time" value={form.time} onChange={e => setForm({ ...form, time: e.target.value })} /></div>
            <div className="field"><label>Duración (min, opcional)</label><input type="number" value={form.duration} onChange={e => setForm({ ...form, duration: e.target.value })} placeholder="según tipo" /></div>
            <div className="field" style={{ gridColumn: 'span 2' }}><label>Invitados adicionales (correos; el equipo y los contactos del cliente van solos)</label><input type="text" value={form.extra} onChange={e => setForm({ ...form, extra: e.target.value })} placeholder="grupo@cliente.com, otra@persona.com" /></div>
            <div className="field"><label>&nbsp;</label><button className="btn" style={{ width: '100%' }} disabled={busy} onClick={gen}>{busy ? 'Creando…' : '⚡ Generar sesión'}</button></div>
          </div>
          <div className="field"><label>Agenda (opcional; si se omite, la del tipo)</label><textarea value={form.agenda} onChange={e => setForm({ ...form, agenda: e.target.value })} /></div>
          {form.project && <div style={{ fontSize: 12, color: 'var(--muted)' }}>Folio siguiente: <b>{(() => { const p = d.projects.find((x: any) => x.project === form.project.name); const t = d.types.find((x: any) => x.id === Number(form.type)); if (!p) return '—'; return p.po ? `${p.po}-${p.prefix || ''}-Sesión #${(p.seq || 0) + 1} - ${t?.name || '…'}` : `SESIÓN #${(p.seq || 0) + 1}– ${p.prefix || '…'}– ${(t?.name || '…').toUpperCase()} | ${form.date.split('-').reverse().join('/')}` })()}</b> · Al terminar: transcripción → resumen ejecutivo IA en tu plantilla de Docs → correo → actividades creadas.</div>}
        </div>
      )}
      {inbox.length > 0 && !external && (
        <div className="card">
          <h3>Transcripciones y notas recibidas (bandeja de reuniones)</h3>
          <div className="table-wrap"><table className="list"><thead><tr><th>Fecha</th><th>Sesión</th><th>Origen</th><th>Proyecto</th><th>Estado</th><th>Documentos</th><th></th></tr></thead><tbody>
            {inbox.map((m: any) => <tr key={m.id} className="row"><td>{fmtDate(m.date)}</td><td><Link to={`/ops/r/google_inbox/${m.id}`}>{m.subject}</Link></td><td>{m.source}</td><td>{m.project_id?.name || <span className="badge warn">sin proyecto</span>}</td><td><span className={'badge ' + (m.state === 'convertido' ? 'ok' : m.state === 'procesado' ? 'info' : '')}>{m.state}</span></td><td>{m.summary_doc_url && <a href={m.summary_doc_url} target="_blank" rel="noreferrer">Mi documento</a>}</td><td>{m.state === 'nuevo' && <button className="btn secondary small" onClick={() => rapi.action('google_inbox', m.id, 'action_process_notes').then(() => { toast('Procesada', 'ok'); load() }).catch((e: any) => toast(e.message, 'err'))}>Procesar</button>}</td></tr>)}
          </tbody></table></div>
        </div>
      )}
      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        {d.projects.map((p: any) => <div className="kpi" key={p.project}><div className="v">{p.total}</div><div className="l">{p.project} · serie {p.prefix || '—'} #{p.seq}{p.po ? ` · ${p.po}` : ''} · {p.processed} con IA{p.pending_transcript ? ` · ${p.pending_transcript} sin transcripción` : ''}</div></div>)}
      </div>
      <div className="viewbar"><button className={group === 'proyecto' ? 'on' : ''} onClick={() => setGroup('proyecto')}>Por proyecto</button><button className={group === 'fecha' ? 'on' : ''} onClick={() => setGroup('fecha')}>Cronológico</button></div>
      {grouped.map(([k, rows]) => (
        <div className="card" key={k}>
          <h2>{k} <span className="badge">{rows.length}</span></h2>
          <div className="table-wrap"><table className="list"><thead><tr><th>#</th><th>Sesión</th><th>Fecha</th><th>Tipo</th><th>Estado</th><th>IA</th><th>Acuerdos</th><th>Enlaces</th>{!external && <th></th>}</tr></thead>
            <tbody>{rows.map((s: any) => <tr key={s.id} className="row">
              <td>{s.folio || '—'}</td>
              <td><Link to={`/ops/r/meetings/${s.id}`}>{s.name}</Link>{s.imported && <span className="badge" style={{ marginLeft: 4 }}>histórico</span>}</td>
              <td>{fmtDate(s.date)}</td><td>{s.type}</td><td><span className={'badge ' + (s.state === 'realizada' || s.state === 'minuta_enviada' ? 'ok' : '')}>{s.state}</span></td>
              <td>{s.processed ? <span className="badge ok">procesada</span> : s.has_transcript ? <span className="badge warn">con transcripción</span> : <span className="badge">sin transcripción</span>}</td>
              <td>{s.agreements || 0}</td>
              <td>{s.meet && <a href={s.meet} target="_blank" rel="noreferrer">Meet</a>} {s.doc && <a href={s.doc} target="_blank" rel="noreferrer" style={{ marginLeft: 6 }}>Doc</a>}</td>
              {!external && <td>{!s.processed && s.has_transcript && <button className="btn secondary small" onClick={() => processAi(s.id)}>Procesar IA</button>}</td>}
            </tr>)}</tbody></table></div>
        </div>
      ))}
    </div>
  )
}
