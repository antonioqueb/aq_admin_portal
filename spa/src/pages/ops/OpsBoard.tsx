import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApp } from '../../context'
import WorkViews from '../../components/WorkViews'

export default function OpsBoard() {
  const { rapi, toast } = useApp()
  const [sp, setSp] = useSearchParams()
  const [items, setItems] = useState<any[]>([])
  const view = sp.get('view') || localStorage.getItem('aq_board_view') || 'kanban'
  const setView = (v: string) => { localStorage.setItem('aq_board_view', v); const n = new URLSearchParams(sp); n.set('view', v); setSp(n) }
  const load = useCallback(() => rapi.list('items', { limit: 500, fields: 'name,item_type,state,assignee_id,date_due,date_start,date_baseline,priority,rank,milestone_id,sprint_id,estimate_hours,remaining_hours,spent_hours,waiting_client,project_id,partner_id,deliverable_id,depends_on_ids,accepted', order: 'rank asc' })
    .then(r => setItems(r.records.filter((x: any) => x.state !== 'cancelado').map((x: any) => ({ id: x.id, name: x.name, type: x.item_type, state: x.state, assignee: x.assignee_id?.name, due: x.date_due, start: x.date_start, baseline: x.date_baseline, priority: x.priority, rank: x.rank, milestone: x.milestone_id?.name, sprint: x.sprint_id?.name, estimate: x.estimate_hours, remaining: x.remaining_hours, spent: x.spent_hours, waiting_client: x.waiting_client, project: x.project_id?.name, client: x.partner_id?.name, deliverable: x.deliverable_id?.name, depends_on: (x.depends_on_ids || []).map((d: any) => d.id), accepted: x.accepted }))))
    .catch((e: any) => toast(e.message, 'err')), [rapi, toast])
  useEffect(() => { load() }, [load])
  return (
    <div>
      <div className="toolbar"><div><h1>Tablero de trabajo</h1><div style={{ color: 'var(--muted)', fontSize: 12 }}>Backlog, Kanban, lista, calendario, cronograma, Gantt, carga, dependencias, roadmap, por entregable, por cliente y personal — todas sincronizadas.</div></div><span className="spacer" /><a className="btn" href="#" onClick={e => { e.preventDefault(); window.location.href = '/admin-portal/ops/r/items/new' }}>+ Nuevo elemento</a></div>
      <WorkViews items={items} reload={load} view={view} setView={setView} />
    </div>
  )
}
