import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtDate, ops } from '../api'
import { useApp } from '../context'
import { STATES } from './WorkViews'
import Many2one from './Many2one'

/** Panel lateral ("peek") de un elemento: esenciales editables, acciones de un toque, subtareas tipo checklist y comentarios. */
export default function ItemPeek({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { rapi, toast, user, schema } = useApp()
  const external = !!(schema?.is_external || user?.is_external)
  const [rec, setRec] = useState<any>(null)
  const [children, setChildren] = useState<any[]>([])
  const [comments, setComments] = useState<any[]>([])
  const [sub, setSub] = useState('')
  const [note, setNote] = useState('')
  const [edit, setEdit] = useState<any>({})
  const load = useCallback(() => {
    rapi.read('items', id).then(r => { setRec(r.record); setEdit({}) }).catch((e: any) => toast(e.message, 'err'))
    rapi.list('items', { domain: [['parent_id', '=', id]], limit: 100, fields: 'name,state,assignee_id,date_due', order: 'id asc' }).then(r => setChildren(r.records)).catch(() => {})
    rapi.list('comments', { domain: [['item_id', '=', id]], limit: 30, order: 'create_date desc', fields: 'body,author_user_id,create_date,internal' }).then(r => setComments(r.records)).catch(() => {})
  }, [id, rapi, toast])
  useEffect(() => { load() }, [load])
  useEffect(() => { const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h) }, [onClose])
  if (!rec) return <div className="peek-bg" onClick={onClose}><aside className="peek" onClick={e => e.stopPropagation()}><div className="empty">Cargando…</div></aside></div>
  const v = (f: string) => (f in edit ? edit[f] : rec[f])
  const save = async (vals?: any) => { const payload = vals || edit; if (!Object.keys(payload).length) return; try { const r = await rapi.write('items', id, payload); setRec(r.record); setEdit({}); onChanged() } catch (e: any) { toast(e.message, 'err') } }
  const move = async (vals: any) => { try { await ops.move(id, vals); load(); onChanged() } catch (e: any) { if (String(e.message).includes('WIP') && confirm(e.message + '\n¿Forzar?')) { await ops.move(id, { ...vals, force_wip: true }); load(); onChanged() } else if (vals.state === 'bloqueado') { const r = prompt('Motivo del bloqueo:'); if (r) { await ops.move(id, { ...vals, blocked_reason: r }); load(); onChanged() } } else toast(e.message, 'err') } }
  const addSub = async () => { if (!sub.trim()) return; try { await rapi.create('items', { name: sub.trim(), project_id: rec.project_id?.id, parent_id: id, item_type: 'subtarea', state: 'por_hacer', assignee_id: rec.assignee_id?.id }); setSub(''); load() } catch (e: any) { toast(e.message, 'err') } }
  const toggleSub = async (c: any) => { try { await ops.move(c.id, { state: c.state === 'cerrado' ? 'por_hacer' : 'cerrado' }); load() } catch (e: any) { toast(e.message, 'err') } }
  const sendNote = async () => { if (!note.trim()) return; try { await rapi.create('comments', { item_id: id, body: note, internal: !external }); setNote(''); load() } catch (e: any) { toast(e.message, 'err') } }
  const done = children.filter(c => c.state === 'cerrado').length
  const st = rec.state
  return (
    <div className="peek-bg" onClick={onClose}>
      <aside className="peek" onClick={e => e.stopPropagation()}>
        <div className="peek-head">
          <span className="badge">{rec.item_type}</span><span className="badge primary">{rec.project_id?.name}</span>
          <span className="spacer" style={{ flex: 1 }} />
          <Link className="btn link small" to={`/ops/r/items/${id}`}>Ficha completa ↗</Link>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        <input className="peek-title" type="text" value={v('name') || ''} onChange={e => setEdit({ ...edit, name: e.target.value })} onBlur={() => save()} disabled={external} />
        {!external && <div className="touch-actions">
          {['backlog', 'por_hacer', 'bloqueado'].includes(st) && <button className="btn small" onClick={() => move({ state: 'en_progreso' })}>▶ Iniciar</button>}
          {st === 'en_progreso' && <button className="btn small" onClick={() => move({ state: rec.item_type === 'tarea' || rec.item_type === 'subtarea' ? 'cerrado' : 'desarrollo_completado' })}>✓ Terminar</button>}
          {st !== 'bloqueado' && !['cerrado', 'cancelado'].includes(st) && <button className="btn secondary small" onClick={() => move({ state: 'bloqueado' })}>⛔ Bloquear</button>}
          {st === 'bloqueado' && <button className="btn secondary small" onClick={() => move({ state: 'en_progreso' })}>Desbloquear</button>}
          <button className="btn secondary small" onClick={() => ops.timerStart({ item_id: id }).then(() => toast('Temporizador iniciado', 'ok')).catch((e: any) => toast(e.message, 'err'))}>⏱</button>
        </div>}
        <div className="grid cols-2" style={{ gap: 8 }}>
          <div className="field"><label>Estado</label><select value={v('state')} disabled={external} onChange={e => move({ state: e.target.value })}>{STATES.map(s => <option key={s[0]} value={s[0]}>{s[1]}</option>)}</select></div>
          <div className="field"><label>Responsable</label>{external ? <input type="text" value={rec.assignee_id?.name || '—'} disabled /> : <Many2one model="aq.portal.member" value={v('assignee_id')} onChange={x => save({ assignee_id: x ? x.id : false })} />}</div>
          <div className="field"><label>Fecha comprometida</label><input type="date" value={v('date_due') || ''} disabled={external} onChange={e => setEdit({ ...edit, date_due: e.target.value || false })} onBlur={() => { if ('date_due' in edit) { const r = rec.date_due ? prompt('Motivo de la reprogramación:') : ''; if (r !== null) save({ date_due: edit.date_due, reschedule_reason: r || undefined }); else setEdit({}) } }} /></div>
          <div className="field"><label>Estimación (h)</label><input type="number" step="0.5" value={v('estimate_hours') ?? ''} disabled={external} onChange={e => setEdit({ ...edit, estimate_hours: parseFloat(e.target.value) || 0 })} onBlur={() => save()} /></div>
        </div>
        <div className="field"><label>Criterios de aceptación</label><textarea value={v('acceptance_criteria') || ''} disabled={external} onChange={e => setEdit({ ...edit, acceptance_criteria: e.target.value })} onBlur={() => save()} /></div>
        {rec.description && <div className="field"><label>Descripción</label><div className="html-content" style={{ maxHeight: 180 }} dangerouslySetInnerHTML={{ __html: rec.description }} /></div>}
        {rec.blocked_reason && st === 'bloqueado' && <div className="alert err">Bloqueado: {rec.blocked_reason}</div>}
        <h3>Subtareas {children.length > 0 && <span className="badge">{done}/{children.length}</span>}</h3>
        {children.length > 0 && <div className="progress" style={{ marginBottom: 6 }}><div style={{ width: (done / children.length * 100) + '%' }} /></div>}
        <div className="checklist">{children.map(c => <label key={c.id}><input type="checkbox" checked={c.state === 'cerrado'} disabled={external} onChange={() => toggleSub(c)} /><span className={c.state === 'cerrado' ? 'done' : ''}>{c.name}{c.assignee_id && <small style={{ color: 'var(--muted)' }}> · {c.assignee_id.name}</small>}{c.date_due && <small style={{ color: 'var(--muted)' }}> · {fmtDate(c.date_due)}</small>}</span></label>)}</div>
        {!external && <input className="quick" type="text" placeholder="+ Subtarea y Enter…" value={sub} onChange={e => setSub(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addSub() }} />}
        <h3 style={{ marginTop: 12 }}>Comunicación</h3>
        <div className="toolbar"><input type="text" placeholder={external ? 'Mensaje al equipo…' : 'Comentario (usa @Nombre para mencionar)'} value={note} onChange={e => setNote(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendNote() }} /><button className="btn small" onClick={sendNote}>Enviar</button></div>
        <ul className="timeline">{comments.map(c => <li key={c.id}><div className="meta">{c.author_user_id?.name || 'OdooBot'} · {fmtDate(c.create_date)}{c.internal && <span className="badge" style={{ marginLeft: 6 }}>interno</span>}</div>{c.body}</li>)}{!comments.length && <li className="empty">Sin comentarios</li>}</ul>
      </aside>
    </div>
  )
}
