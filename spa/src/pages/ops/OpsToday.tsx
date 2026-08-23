import { useCallback, useEffect, useState } from 'react'
import { fmtDate, ops, today } from '../../api'
import { useApp } from '../../context'
import { useActiveProject } from '../../project'
import ItemPeek from '../../components/ItemPeek'

/** Vista "Hoy": lo que debo atender hoy, con acciones táctiles de un toque (pensada para móvil). */
export default function OpsToday() {
  const { toast } = useApp()
  const active = useActiveProject()
  const [d, setD] = useState<any>(null)
  const [peek, setPeek] = useState<number | null>(null)
  const [tab, setTab] = useState<'hoy' | 'semana' | 'bloqueados' | 'todo'>('hoy')
  const load = useCallback(() => ops.mywork().then(setD).catch((e: any) => toast(e.message, 'err')), [toast])
  useEffect(() => { load() }, [load])
  if (!d) return <div className="empty">Cargando…</div>
  const f = (arr: any[]) => active ? arr.filter(i => i.project_id === active.id) : arr
  const lists: Record<string, any[]> = { hoy: f([...d.today, ...d.assigned.filter((i: any) => i.state === 'en_progreso' && !d.today.some((t: any) => t.id === i.id))]), semana: f(d.week), bloqueados: f(d.blocked), todo: f(d.assigned) }
  const rows = lists[tab]
  const act = async (i: any, vals: any) => {
    try { await ops.move(i.id, vals); toast('Listo', 'ok'); load() } catch (e: any) {
      if (String(e.message).includes('WIP') && confirm(e.message + '\n¿Forzar?')) { await ops.move(i.id, { ...vals, force_wip: true }); load() }
      else if (vals.state === 'bloqueado') { const r = prompt('Motivo del bloqueo:'); if (r) { await ops.move(i.id, { ...vals, blocked_reason: r }); load() } }
      else toast(e.message, 'err')
    }
  }
  return (
    <div>
      <div className="toolbar"><div><h1>Hoy</h1><div style={{ color: 'var(--muted)', fontSize: 12 }}>{fmtDate(today())}{active ? ' · ' + active.name : ''} · {d.hours_week.toFixed(1)} h esta semana</div></div><span className="spacer" />
        {d.running_timer ? <button className="btn small" onClick={() => ops.timerStop().then(load)}>⏱ Detener</button> : null}</div>
      <div className="chip-row">{(['hoy', 'semana', 'bloqueados', 'todo'] as const).map(t => <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t === 'hoy' ? `Hoy (${lists.hoy.length})` : t === 'semana' ? `Semana (${lists.semana.length})` : t === 'bloqueados' ? `Bloqueados (${lists.bloqueados.length})` : `Todo (${lists.todo.length})`}</button>)}</div>
      {rows.length === 0 && <div className="card empty">Nada pendiente aquí 🎉</div>}
      {rows.map(i => (
        <div className="today-card" key={i.id}>
          <div onClick={() => setPeek(i.id)} style={{ cursor: 'pointer' }}><b>{i.name}</b>{i.priority === '2' && <span className="badge err" style={{ marginLeft: 6 }}>crítica</span>}{i.waiting_client && <span className="badge warn" style={{ marginLeft: 6 }}>cliente</span>}
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{i.project} · {i.state}{i.due && ' · vence ' + fmtDate(i.due)}{i.blocked_reason && ' · ' + i.blocked_reason}</div></div>
          <div className="acts">
            {i.state !== 'en_progreso' && i.state !== 'bloqueado' && <button className="btn" onClick={() => act(i, { state: 'en_progreso' })}>▶ Iniciar</button>}
            {i.state === 'bloqueado' && <button className="btn" onClick={() => act(i, { state: 'en_progreso' })}>▶ Desbloquear</button>}
            {i.state === 'en_progreso' && <button className="btn" onClick={() => act(i, { state: i.type === 'tarea' || i.type === 'subtarea' ? 'cerrado' : 'desarrollo_completado' })}>✓ Terminar</button>}
            {i.state !== 'bloqueado' && <button className="btn secondary" onClick={() => act(i, { state: 'bloqueado' })}>⛔ Bloquear</button>}
            <button className="btn secondary" onClick={() => ops.timerStart({ item_id: i.id }).then(() => { toast('⏱ en curso', 'ok'); load() })}>⏱</button>
          </div>
        </div>
      ))}
      {peek && <ItemPeek id={peek} onClose={() => setPeek(null)} onChanged={load} />}
    </div>
  )
}
