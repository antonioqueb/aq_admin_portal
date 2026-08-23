import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { addDays, fmtDate, ops, today } from '../api'
import { useApp } from '../context'

export const STATES: [string, string][] = [['backlog', 'Backlog'], ['por_hacer', 'Por hacer'], ['en_progreso', 'En progreso'], ['bloqueado', 'Bloqueado'], ['desarrollo_completado', 'Dev completado'], ['revision_tecnica', 'Revisión técnica'], ['qa_interno', 'QA interno'], ['correccion', 'Corrección'], ['regresion', 'Regresión'], ['listo_validacion', 'Listo p/ validación'], ['validacion_cliente', 'Validación cliente'], ['aceptado', 'Aceptado'], ['listo_liberar', 'Listo p/ liberar'], ['liberado', 'Liberado'], ['verificado', 'Verificado'], ['cerrado', 'Cerrado']]
const VIEWS: [string, string][] = [['backlog', 'Backlog'], ['kanban', 'Kanban'], ['sprint', 'Sprints'], ['list', 'Lista'], ['calendar', 'Calendario'], ['timeline', 'Cronograma'], ['gantt', 'Gantt'], ['workload', 'Carga'], ['deps', 'Dependencias'], ['roadmap', 'Roadmap'], ['deliverable', 'Por entregable'], ['client', 'Por cliente'], ['personal', 'Personal']]
const CLIENT_VIEWS = ['list', 'calendar', 'roadmap', 'deliverable']

export default function WorkViews({ items, sprints, reload, view, setView, projectMode }: { items: any[]; sprints?: any[]; reload: () => void; view: string; setView: (v: string) => void; projectMode?: boolean }) {
  const { toast, user, schema } = useApp()
  const nav = useNavigate()
  const external = !!(schema?.is_external || user?.is_external)
  const [drag, setDrag] = useState<any>(null)
  const [over, setOver] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const views = VIEWS.filter(v => !external || CLIENT_VIEWS.includes(v[0])).filter(v => projectMode || !['sprint'].includes(v[0]))
  const rows = useMemo(() => items.filter(i => !q || (i.name + ' ' + (i.assignee || '') + ' ' + (i.project || '')).toLowerCase().includes(q.toLowerCase())), [items, q])
  const move = async (i: any, vals: any) => {
    try { await ops.move(i.id, vals); reload() } catch (e: any) {
      if (String(e.message).includes('WIP') && confirm(e.message + '\n¿Forzar de todos modos?')) { try { await ops.move(i.id, { ...vals, force_wip: true }); reload() } catch (e2: any) { toast(e2.message, 'err') } }
      else if (String(e.message).includes('Reprogramación')) { const reason = prompt('Motivo de la reprogramación:'); if (reason) { try { await ops.move(i.id, { ...vals, reason }); reload() } catch (e3: any) { toast(e3.message, 'err') } } }
      else if (vals.state === 'bloqueado') { const r = prompt('Motivo del bloqueo:'); if (r) { try { await ops.move(i.id, { ...vals, blocked_reason: r }); reload() } catch (e4: any) { toast(e4.message, 'err') } } }
      else toast(e.message, 'err')
    }
  }
  const open = (i: any) => nav(`/ops/r/items/${i.id}`)
  const Card = ({ i }: { i: any }) => (
    <div className={'kcard p' + i.priority + (i.waiting_client ? ' wc' : '')} draggable={!external} onDragStart={() => setDrag(i)} onClick={() => open(i)}>
      <div>{i.name}</div>
      <div className="m"><span>{i.type}</span>{i.assignee && <span>@{i.assignee}</span>}{i.due && <span>{fmtDate(i.due)}</span>}{i.estimate ? <span>{i.estimate}h</span> : null}{i.milestone && <span>◆ {i.milestone}</span>}{i.waiting_client && <span>⏳ cliente</span>}{!projectMode && i.project && <span>{i.project}</span>}</div>
    </div>
  )
  const byState = (s: string) => rows.filter(i => i.state === s).sort((a, b) => a.rank - b.rank)
  const t = today()
  return (
    <div>
      <div className="viewbar">{views.map(v => <button key={v[0]} className={view === v[0] ? 'on' : ''} onClick={() => setView(v[0])}>{v[1]}</button>)}<input type="text" placeholder="Filtrar…" value={q} onChange={e => setQ(e.target.value)} style={{ width: 180, marginLeft: 'auto' }} /></div>
      {view === 'kanban' && (
        <div className="kanban">
          {STATES.filter(s => !external || !['backlog', 'por_hacer', 'en_progreso', 'bloqueado', 'desarrollo_completado', 'revision_tecnica', 'qa_interno', 'correccion', 'regresion'].includes(s[0])).map(([s, l]) => (
            <div key={s} className={'kcol' + (over === s ? ' over' : '')} onDragOver={e => { e.preventDefault(); setOver(s) }} onDragLeave={() => setOver(null)} onDrop={() => { if (drag && drag.state !== s) move(drag, { state: s }); setDrag(null); setOver(null) }}>
              <h4>{l}<span>{byState(s).length}</span></h4>
              {byState(s).map(i => <Card key={i.id} i={i} />)}
            </div>))}
        </div>
      )}
      {view === 'backlog' && (
        <div className="card tight">{rows.filter(i => ['backlog', 'por_hacer'].includes(i.state)).sort((a, b) => a.rank - b.rank).map((i, idx, arr) => (
          <div key={i.id} className="wl" style={{ cursor: 'pointer' }}>
            <span className="badge">{idx + 1}</span><span style={{ flex: 1 }} onClick={() => open(i)}>{i.name} <span className="badge">{i.type}</span>{i.priority === '2' && <span className="badge err">crítica</span>}</span>
            <span style={{ color: 'var(--muted)', fontSize: 12 }}>{i.assignee || '—'} · {i.estimate || 0}h</span>
            {!external && <><button className="btn link small" disabled={idx === 0} onClick={() => move(i, { rank: arr[idx - 1].rank - 1 })}>▲</button><button className="btn link small" disabled={idx === arr.length - 1} onClick={() => move(i, { rank: arr[idx + 1].rank + 1 })}>▼</button><button className="btn secondary small" onClick={() => move(i, { state: 'en_progreso' })}>Iniciar</button></>}
          </div>))}{rows.filter(i => ['backlog', 'por_hacer'].includes(i.state)).length === 0 && <div className="empty">Backlog vacío</div>}</div>
      )}
      {view === 'sprint' && (
        <div className="grid cols-2">{(sprints || []).map(s => <div key={s.id} className="card" onDragOver={e => e.preventDefault()} onDrop={() => { if (drag) move(drag, { sprint_id: s.id }); setDrag(null) }}><h2>{s.name} <span className="badge">{s.state}</span></h2><div style={{ color: 'var(--muted)', fontSize: 12 }}>{fmtDate(s.start)} → {fmtDate(s.end)} · {s.goal}</div><div className="progress" style={{ margin: '6px 0' }}><div style={{ width: (s.items ? s.done / s.items * 100 : 0) + '%' }} /></div><div className="meta" style={{ fontSize: 12 }}>{s.done}/{s.items} · {s.committed} h comprometidas / {s.capacity} h</div>{rows.filter(i => i.sprint === s.name).map(i => <Card key={i.id} i={i} />)}</div>)}
          <div className="card" onDragOver={e => e.preventDefault()} onDrop={() => { if (drag) move(drag, { sprint_id: null }); setDrag(null) }}><h2>Sin sprint</h2>{rows.filter(i => !i.sprint && !['cerrado', 'aceptado', 'liberado', 'verificado'].includes(i.state)).map(i => <Card key={i.id} i={i} />)}</div></div>
      )}
      {view === 'list' && (
        <div className="table-wrap"><table className="list"><thead><tr><th>Elemento</th><th>Tipo</th><th>Estado</th>{!external && <th>Responsable</th>}<th>Prio.</th><th>Vence</th>{!external && <><th className="num">Est.</th><th className="num">Rest.</th><th className="num">Reg.</th></>}<th>Hito</th>{!projectMode && <th>Proyecto</th>}</tr></thead>
          <tbody>{rows.map(i => <tr key={i.id} className="row" onClick={() => open(i)}><td>{i.name}{i.accepted && <span className="badge ok" style={{ marginLeft: 4 }}>aceptado</span>}</td><td>{i.type}</td><td><span className="badge">{STATES.find(s => s[0] === i.state)?.[1]}</span></td>{!external && <td>{i.assignee || '—'}</td>}<td>{i.priority === '2' ? 'crítica' : i.priority === '1' ? 'alta' : 'normal'}</td><td>{fmtDate(i.due)}</td>{!external && <><td className="num">{i.estimate}</td><td className="num">{i.remaining}</td><td className="num">{i.spent}</td></>}<td>{i.milestone || '—'}</td>{!projectMode && <td>{i.project}</td>}</tr>)}</tbody></table></div>
      )}
      {view === 'calendar' && (() => { const days = Array.from(new Set(rows.filter(i => i.due).map(i => i.due))).sort(); return <div className="card">{days.length === 0 && <div className="empty">Sin fechas</div>}{days.map(d => <div className="cal-day" key={d}><div className={'d' + (d === t ? ' today' : '')}>{fmtDate(d)} {d < t && <span className="badge err">vencido</span>}</div>{rows.filter(i => i.due === d).map(i => <div key={i.id} className="cal-ev"><span className="badge">{i.type}</span><a href="#" onClick={e => { e.preventDefault(); open(i) }}>{i.name}</a>{!external && <span style={{ color: 'var(--muted)', fontSize: 12 }}>· {i.assignee || '—'}</span>}</div>)}</div>)}</div> })()}
      {(view === 'gantt' || view === 'timeline' || view === 'roadmap') && <Gantt rows={view === 'roadmap' ? rows.filter(i => ['epica', 'entregable', 'objetivo', 'capacidad', 'cambio'].includes(i.type)) : rows} open={open} baseline={view === 'gantt'} />}
      {view === 'workload' && (() => { const m: Record<string, any[]> = {}; rows.filter(i => !['cerrado', 'cancelado', 'aceptado', 'liberado', 'verificado'].includes(i.state)).forEach(i => { (m[i.assignee || 'Sin asignar'] = m[i.assignee || 'Sin asignar'] || []).push(i) }); return <div className="card">{Object.entries(m).sort((a, b) => b[1].length - a[1].length).map(([k, v]) => { const h = v.reduce((s, i) => s + (i.remaining || i.estimate || 0), 0); return <div key={k} className="wl"><span style={{ width: 180 }}>{k}</span><div className="bar"><div className={h > 40 ? 'over' : ''} style={{ width: Math.min(h / 40 * 100, 100) + '%' }} /></div><span style={{ width: 140, textAlign: 'right', fontSize: 12 }}>{v.length} elem. · {h.toFixed(0)} h {h > 40 && <span className="badge err">sobrecarga</span>}</span></div> })}</div> })()}
      {view === 'deps' && <div className="card">{rows.filter(i => i.depends_on && i.depends_on.length).map(i => <div key={i.id} className="wl"><span style={{ flex: 1 }}><a href="#" onClick={e => { e.preventDefault(); open(i) }}>{i.name}</a> <span className="badge">{STATES.find(s => s[0] === i.state)?.[1]}</span></span><span style={{ color: 'var(--muted)', fontSize: 12 }}>depende de: {i.depends_on.map((d: number) => rows.find(r => r.id === d)?.name || '#' + d).join(', ')}</span></div>)}{rows.filter(i => i.depends_on && i.depends_on.length).length === 0 && <div className="empty">Sin dependencias registradas</div>}</div>}
      {view === 'deliverable' && (() => { const m: Record<string, any[]> = {}; rows.forEach(i => { (m[i.deliverable || (i.type === 'entregable' ? i.name : 'Sin entregable')] = m[i.deliverable || (i.type === 'entregable' ? i.name : 'Sin entregable')] || []).push(i) }); return <div className="grid cols-2">{Object.entries(m).map(([k, v]) => <div key={k} className="card"><h2>{k}</h2>{v.map(i => <Card key={i.id} i={i} />)}</div>)}</div> })()}
      {view === 'client' && (() => { const m: Record<string, any[]> = {}; rows.forEach(i => { (m[i.client || i.project || '—'] = m[i.client || i.project || '—'] || []).push(i) }); return <div className="grid cols-2">{Object.entries(m).map(([k, v]) => <div key={k} className="card"><h2>{k}</h2>{v.map(i => <Card key={i.id} i={i} />)}</div>)}</div> })()}
      {view === 'personal' && <div className="card">{rows.filter(i => user?.member_name && i.assignee === user.member_name).map(i => <Card key={i.id} i={i} />)}{rows.filter(i => user?.member_name && i.assignee === user.member_name).length === 0 && <div className="empty">No tiene elementos asignados{!user?.member_name && ' (su usuario no está vinculado a un integrante)'}</div>}</div>}
      <p style={{ color: 'var(--mute2)', fontSize: 11 }}>Todas las vistas muestran el mismo elemento (una sola fuente de verdad). {!external && 'Arrastre tarjetas para cambiar de estado o sprint.'}</p>
    </div>
  )
}

function Gantt({ rows, open, baseline }: { rows: any[]; open: (i: any) => void; baseline: boolean }) {
  const withDates = rows.filter(i => i.due || i.start)
  if (!withDates.length) return <div className="empty">Sin fechas para el cronograma</div>
  const dates = withDates.flatMap(i => [i.start, i.due, i.baseline].filter(Boolean))
  const min = dates.reduce((a, b) => a < b ? a : b), max = dates.reduce((a, b) => a > b ? a : b)
  const span = Math.max(1, (new Date(max).getTime() - new Date(min).getTime()) / 86400000)
  const pct = (d: string) => Math.max(0, Math.min(100, (new Date(d).getTime() - new Date(min).getTime()) / 86400000 / span * 100))
  const weeks: string[] = []; for (let d = min; d <= max; d = addDays(d, 7)) weeks.push(d)
  return (
    <div className="card gantt">
      <div className="head"><div>Elemento</div><div style={{ display: 'flex' }}>{weeks.map(w => <span key={w} style={{ flex: 1 }}>{w.slice(5)}</span>)}</div></div>
      {withDates.map(i => { const s = i.start || addDays(i.due, -5); const e = i.due || i.start; return (
        <div className="row" key={i.id}><div><a href="#" onClick={ev => { ev.preventDefault(); open(i) }}>{i.name}</a> <span className="badge">{STATES.find(x => x[0] === i.state)?.[1]}</span></div>
          <div style={{ position: 'relative', height: baseline && i.baseline ? 34 : 18 }}>
            <div className="bar" title={`${s} → ${e}`} style={{ position: 'absolute', left: pct(s) + '%', width: Math.max(1.5, pct(e) - pct(s)) + '%', opacity: i.state === 'cerrado' ? .4 : .85 }} />
            {baseline && i.baseline && <div className="bar base" title={`Plan original: ${i.baseline}`} style={{ position: 'absolute', top: 18, left: pct(addDays(i.baseline, -5)) + '%', width: Math.max(1.5, pct(i.baseline) - pct(addDays(i.baseline, -5))) + '%' }} />}
          </div></div>) })}
      {baseline && <p style={{ fontSize: 11, color: 'var(--muted)' }}>Barra sólida: plan vigente · barra punteada: plan original (línea base).</p>}
    </div>
  )
}
