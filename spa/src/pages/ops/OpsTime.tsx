import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtDate, ops, today } from '../../api'
import { useApp } from '../../context'
import Many2one from '../../components/Many2one'
import { useActiveProject } from '../../project'

const CATS: [string, string][] = [['analisis', 'Análisis'], ['configuracion', 'Configuración'], ['desarrollo', 'Desarrollo'], ['pruebas', 'Pruebas'], ['reunion', 'Reunión'], ['soporte', 'Soporte'], ['capacitacion', 'Capacitación'], ['documentacion', 'Documentación'], ['gestion', 'Gestión'], ['no_planificado', 'No planificado'], ['interno', 'Interno']]
const weekOf = (d: string) => { const x = new Date(d + 'T00:00:00'); const day = (x.getDay() + 6) % 7; x.setDate(x.getDate() - day + 3); const y = x.getFullYear(); const jan4 = new Date(y, 0, 4); const w = 1 + Math.round(((x.getTime() - jan4.getTime()) / 86400000 - 3 + ((jan4.getDay() + 6) % 7)) / 7); return `${y}-W${String(w).padStart(2, '0')}` }

export default function OpsTime() {
  const { rapi, toast, user } = useApp()
  const active = useActiveProject()
  const [week, setWeek] = useState(weekOf(today()))
  const [d, setD] = useState<any>(null)
  const [form, setForm] = useState<any>({ date: today(), hours: 1, category: 'desarrollo', billable: true, description: '', project_id: active ? { id: active.id, name: active.name } : null, item_id: null, justification: '' })
  const [timerItem, setTimerItem] = useState<any>(null)
  const [running, setRunning] = useState<any>(null)
  const [fc, setFc] = useState<any[]>([])
  useEffect(() => { ops.capacityForecast(4).then(r => setFc(r.forecast)).catch(() => {}) }, [])
  const load = useCallback(() => ops.week(week).then(r => { setD(r); setRunning(r.entries.find((e: any) => e.running) || null) }).catch((e: any) => toast(e.message, 'err')), [week, toast])
  useEffect(() => { load() }, [load])
  const shift = (n: number) => { const [y, w] = week.split('-W').map(Number); const jan4 = new Date(y, 0, 4); const monday = new Date(jan4); monday.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7) + (w - 1 + n) * 7); setWeek(weekOf(monday.toISOString().slice(0, 10))) }
  const add = async () => { try { await rapi.create('timesheets', { ...form, member_id: user?.member_id, project_id: form.project_id?.id || null, item_id: form.item_id?.id || null }); toast('Tiempo registrado', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  const submitWeek = async () => { const ids = d.entries.filter((e: any) => e.state === 'borrador').map((e: any) => e.id); for (const id of ids) await rapi.action('timesheets', id, 'action_submit').catch(() => {}); toast('Semana enviada a aprobación', 'ok'); load() }
  const approve = async () => { try { const r = await ops.approveWeek(week); toast(`${r.approved} registros aprobados · horas facturables enviadas a Administración`, 'ok'); load() } catch (e: any) { toast(e.message, 'err') } }
  const canApprove = ['platform_owner', 'ops_director', 'pm', 'functional_lead', 'tech_lead'].includes(user?.ops_role || '')
  if (!d) return <div className="empty">Cargando…</div>
  const entries = active ? d.entries.filter((e: any) => e.project_id?.id === active.id) : d.entries
  const total = entries.reduce((s: number, e: any) => s + e.hours, 0)
  const byDay: Record<string, any[]> = {}; entries.forEach((e: any) => { (byDay[e.date] = byDay[e.date] || []).push(e) })
  return (
    <div>
      <div className="hero"><div><div className="tag">Tiempo real y capacidad futura</div><h1>Tiempo y capacidad</h1><div className="pulse">Semana {week} · {fmtDate(d.start)} → {fmtDate(d.end)} · {total.toFixed(1)} h registradas{active ? ' · ' + active.name : ''}</div></div>
        <div className="toolbar" style={{ margin: 0 }}><button className="btn secondary small" onClick={() => shift(-1)}>‹</button><button className="btn secondary small" onClick={() => setWeek(weekOf(today()))}>Hoy</button><button className="btn secondary small" onClick={() => shift(1)}>›</button><button className="btn secondary small" onClick={submitWeek}>Enviar semana</button>{canApprove && <button className="btn small" onClick={approve}>Aprobar semana</button>}</div></div>
      <div className="grid cols-2">
        <div className="card"><h3>Temporizador</h3>
          {running ? <div className="timer">⏱ corriendo · {running.item_id?.name || running.project_id?.name || running.description} <button className="btn small" onClick={() => ops.timerStop().then(() => { toast('Detenido', 'ok'); load() })}>Detener</button></div>
            : <div><div className="field"><label>Elemento (opcional)</label><Many2one model="aq.ops.item" value={timerItem} onChange={setTimerItem} resource="items" /></div><button className="btn" onClick={() => ops.timerStart({ item_id: timerItem?.id }).then(() => { toast('Temporizador iniciado', 'ok'); load() }).catch((e: any) => toast(e.message, 'err'))}>▶ Iniciar</button></div>}
          <h3 style={{ marginTop: 16 }}>Captura manual</h3>
          <div className="grid cols-2">
            <div className="field"><label>Fecha</label><input type="date" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} /></div>
            <div className="field"><label>Horas</label><input type="number" step="0.25" value={form.hours} onChange={e => setForm({ ...form, hours: parseFloat(e.target.value) })} /></div>
            <div className="field"><label>Proyecto</label><Many2one model="aq.ops.project" value={form.project_id} onChange={v => setForm({ ...form, project_id: v })} resource="projects" /></div>
            <div className="field"><label>Elemento</label><Many2one model="aq.ops.item" value={form.item_id} onChange={v => setForm({ ...form, item_id: v })} resource="items" /></div>
            <div className="field"><label>Clasificación</label><select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>{CATS.map(c => <option key={c[0]} value={c[0]}>{c[1]}</option>)}</select></div>
            <div className="field"><label>Facturable</label><label className="check"><input type="checkbox" checked={form.billable} onChange={e => setForm({ ...form, billable: e.target.checked })} /> Sí</label></div>
          </div>
          <div className="field"><label>Descripción</label><input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></div>
          {!form.project_id && !form.item_id && <div className="field"><label>Justificación (sin proyecto ni entregable)</label><input type="text" value={form.justification} onChange={e => setForm({ ...form, justification: e.target.value })} /></div>}
          <button className="btn" onClick={add}>Registrar</button>
        </div>
        <div className="card"><h3>Capacidad y carga · semana {week}</h3>
          {d.capacity.length === 0 && <div className="empty">Sin capacidad registrada. <Link to="/ops/r/capacity/new">Definir capacidad</Link></div>}
          {d.capacity.map((c: any) => <div key={c.id} className="wl"><span style={{ width: 160 }}>{c.member}<div style={{ fontSize: 10, color: 'var(--muted)' }}>{c.specialty}</div></span><div className="bar"><div className={c.overallocated ? 'over' : ''} style={{ width: Math.min(c.load_pct, 100) + '%' }} /></div><span style={{ width: 200, textAlign: 'right', fontSize: 12 }}>{c.planned} h plan / {c.available} h · {c.logged} h reg. {c.overallocated && <span className="badge err">sobreasignado</span>}</span></div>)}
          <p style={{ fontSize: 11, color: 'var(--mute2)' }}>Capacidad = horas disponibles − vacaciones/indisponibilidad. Carga = esfuerzo restante de elementos asignados que vencen en la semana. Tarifas y costos permanecen en Administración.</p>
          <Link className="btn secondary small" to="/ops/r/capacity">Gestionar capacidad y ausencias</Link>
        </div>
      </div>
      <div className="card"><h3>Planeación predictiva de capacidad · próximas 4 semanas</h3>
        <div className="table-wrap"><table className="list"><thead><tr><th>Integrante</th>{fc[0]?.weeks.map((w: any) => <th key={w.week} className="num">{w.week}</th>)}</tr></thead>
          <tbody>{fc.map(r => <tr key={r.member_id}><td>{r.member}</td>{r.weeks.map((w: any) => <td key={w.week} className="num"><span className={'badge ' + (w.overallocated ? 'err' : w.load_pct >= 80 ? 'warn' : 'ok')}>{w.load_pct}%</span><div style={{ fontSize: 10, color: 'var(--muted)' }}>{w.planned}/{w.available} h · {w.items}</div></td>)}</tr>)}</tbody></table></div>
        {fc.length === 0 && <div className="empty">Sin datos de pronóstico</div>}
        <div className="toolbar" style={{ marginTop: 8 }}><a className="btn secondary small" href={ops.icsUrl()}>📅 Suscribir calendario (ICS)</a><span style={{ fontSize: 11, color: 'var(--mute2)' }}>Compromisos, hitos, reuniones, validaciones y liberaciones en su calendario.</span></div>
      </div>
      <div className="card"><h3>Registros de la semana</h3>
        {Object.keys(byDay).sort().map(day => <div key={day} className="cal-day"><div className="d">{fmtDate(day)} · {byDay[day].reduce((s, e) => s + e.hours, 0).toFixed(1)} h</div>
          {byDay[day].map((e: any) => <div key={e.id} className="cal-ev"><span className="badge">{e.category}</span><Link to={`/ops/r/timesheets/${e.id}`}>{e.description || e.item_id?.name || e.project_id?.name || 'Sin descripción'}</Link><span style={{ color: 'var(--muted)', fontSize: 12 }}>{e.member_id?.name} · {e.project_id?.name || '—'} · {e.hours} h {e.billable ? '' : '· no facturable'}</span><span className={'badge ' + (e.state === 'aprobado' ? 'ok' : e.state === 'rechazado' ? 'err' : '')}>{e.state}</span>{e.unjustified && <span className="badge err">sin justificación</span>}</div>)}</div>)}
        {entries.length === 0 && <div className="empty">Sin registros esta semana{active ? ' en ' + active.name : ''}</div>}
      </div>
    </div>
  )
}
