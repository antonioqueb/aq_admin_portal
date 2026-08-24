import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, ops, today } from '../../api'
import { useApp } from '../../context'
import { useActiveProject } from '../../project'
import SessionWizard from '../../components/SessionWizard'

/** Generador y mapa de sesiones: folio automático, evento con Meet e invitación, histórico completo por proyecto. */
export default function OpsSessions() {
  const { toast, user, schema } = useApp()
  const active = useActiveProject()
  const [d, setD] = useState<any>(null)
  const [created, setCreated] = useState<any>(null)
  const [group, setGroup] = useState<'fecha' | 'proyecto'>('proyecto')
  const [inbox, setInbox] = useState<any[]>([])
  const external = !!(schema?.is_external || user?.is_external)
  const owner = ['platform_owner', 'ops_director'].includes(user?.ops_role || '')
  const { rapi } = useApp()
  const load = useCallback(() => { api.get('/ops/sessions/map', active ? { project_id: active.id } : {}).then(setD).catch((e: any) => toast(e.message, 'err')); rapi.list('google_inbox', { limit: 30, order: 'date desc', filters: { category: 'meeting_notes' } }).then(r => setInbox(r.records)).catch(() => {}) }, [toast, active, rapi])
  useEffect(() => { load() }, [load])  // eslint-disable-line
  const processAi = async (id: number) => { try { await api.post(`/ops/r/meetings/${id}/action/action_process_ai`); toast('Procesada: resumen, documento, correo y actividades', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  const copy = async (text: string, what: string) => { try { await navigator.clipboard.writeText(text); toast(`${what} copiado al portapapeles`, 'ok') } catch { toast('Copie manualmente: ' + text, 'info') } }
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
      {!external && <SessionWizard types={d.types} projects={d.projects} defaultProject={active} onCreated={(m: any) => { setCreated(m); if (m.meet) navigator.clipboard?.writeText(m.meet).catch(() => {}); toast('Sesión creada · liga copiada', 'ok'); load() }} />}
      {created && (
        <div className="card" style={{ borderColor: 'var(--primary)' }}>
          <h3>Sesión lista · {created.name}</h3>
          <div className="share-row">
            <input type="text" readOnly value={created.meet || ''} onFocus={e => e.currentTarget.select()} />
            <button className="btn" onClick={() => copy(created.meet, 'Enlace de Meet')}>📋 Copiar liga</button>
            <a className="btn secondary" href={created.meet} target="_blank" rel="noreferrer">Abrir Meet</a>
          </div>
          <div className="field" style={{ marginTop: 10 }}><label>Mensaje listo para WhatsApp o chat compartido</label><textarea rows={9} value={created.share_text || ''} onChange={e => setCreated({ ...created, share_text: e.target.value })} /></div>
          <div className="toolbar">
            <button className="btn" onClick={() => copy(created.share_text, 'Mensaje')}>📋 Copiar mensaje</button>
            <a className="btn secondary" href={`https://wa.me/?text=${encodeURIComponent(created.share_text || '')}`} target="_blank" rel="noreferrer">Compartir por WhatsApp</a>
            <a className="btn secondary" href={`mailto:?subject=${encodeURIComponent(created.name)}&body=${encodeURIComponent(created.share_text || '')}`}>Enviar por correo</a>
            <Link className="btn secondary" to={`/ops/r/meetings/${created.id}`}>Abrir sesión</Link>
            <button className="btn link" onClick={() => setCreated(null)}>Cerrar</button>
          </div>
        </div>
      )}
      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        {d.projects.map((p: any) => <div className="kpi" key={p.project}><div className="v">{p.total}</div><div className="l">{p.project} · serie {p.prefix || '—'} #{p.seq}{p.po ? ` · ${p.po}` : ''} · {p.processed} con IA{p.pending_transcript ? ` · ${p.pending_transcript} sin transcripción` : ''}</div></div>)}
      </div>
      <div className="viewbar"><button className={group === 'proyecto' ? 'on' : ''} onClick={() => setGroup('proyecto')}>Por proyecto</button><button className={group === 'fecha' ? 'on' : ''} onClick={() => setGroup('fecha')}>Cronológico</button></div>
      {grouped.map(([k, rows]) => (
        <div className="card" key={k}>
          <h2>{k} <span className="badge">{rows.length}</span></h2>
          <div className="table-wrap"><table className="list"><thead><tr><th>#</th><th>Sesión</th><th>Fecha</th><th>Tipo</th><th>Estado</th><th>IA</th><th>Seguimiento</th><th>Enlaces</th>{!external && <th></th>}</tr></thead>
            <tbody>{rows.map((s: any) => <tr key={s.id} className="row">
              <td>{s.folio || '—'}</td>
              <td><Link to={`/ops/r/meetings/${s.id}`}>{s.name}</Link>{s.imported && <span className="badge" style={{ marginLeft: 4 }}>histórico</span>}</td>
              <td>{fmtDate(s.date)}</td><td>{s.type}</td><td><span className={'badge ' + (s.state === 'realizada' || s.state === 'minuta_enviada' ? 'ok' : '')}>{s.state}</span></td>
              <td>{s.processed ? <span className="badge ok">procesada</span> : s.has_transcript ? <span className="badge warn">con transcripción</span> : <span className="badge">sin transcripción</span>}</td>
              <td>{s.followups ? <span className="badge ok" title={s.followups_log || ''}>{s.followups} elementos</span> : (s.agreements ? `${s.agreements} acuerdos` : '—')}</td>
              <td>{s.meet && <a href={s.meet} target="_blank" rel="noreferrer">Meet</a>} {s.doc && <a href={s.doc} target="_blank" rel="noreferrer" style={{ marginLeft: 6 }}>Doc</a>}</td>
              {!external && <td>{!s.processed && s.has_transcript && <button className="btn secondary small" onClick={() => processAi(s.id)}>Procesar IA</button>}</td>}
            </tr>)}</tbody></table></div>
        </div>
      ))}
    </div>
  )
}
