import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate, today } from '../api'
import { useApp } from '../context'

const FREQ: Record<string, string> = { diario: 'Diario', semanal: 'Semanal', mensual: 'Mensual' }
const linkFor = (l?: string) => !l ? null : l === 'dashboard' ? '/' : l === 'calendar' ? '/calendar' : l === 'reports' ? '/reports' : l === 'routines' ? '/routines' : `/r/${l}`

export default function Routines() {
  const { toast, user } = useApp()
  const [date, setDate] = useState(today())
  const [data, setData] = useState<any>(null)
  const load = useCallback(() => api.routines(date).then(setData).catch(e => toast(e.message, 'err')), [date, toast])
  useEffect(() => { load() }, [load])
  const canEdit = user?.role !== 'consulta'
  const toggle = async (r: any) => { if (!canEdit) return; try { await api.toggleRoutine(r.id); load() } catch (e: any) { toast(e.message, 'err') } }
  if (!data) return <div className="empty">Cargando…</div>
  const Block = ({ f }: { f: string }) => {
    const runs = data.runs.filter((r: any) => r.frequency === f)
    const done = runs.filter((r: any) => r.done).length
    return (
      <div className="card">
        <div className="toolbar"><h2>{FREQ[f]}</h2><span className="spacer" /><span className="badge">{done}/{runs.length}</span></div>
        <div className="progress" style={{ marginBottom: 8 }}><div style={{ width: runs.length ? (done / runs.length * 100) + '%' : '0%' }} /></div>
        <div className="checklist">
          {runs.map((r: any) => (
            <label key={r.id}><input type="checkbox" checked={r.done} onChange={() => toggle(r)} disabled={!canEdit} />
              <span className={r.done ? 'done' : ''}>{r.name}{linkFor(r.link) && <> · <Link to={linkFor(r.link)!} onClick={e => e.stopPropagation()}>abrir</Link></>}{r.done && <div className="meta" style={{ fontSize: 11, color: '#6b7280' }}>{r.user} · {fmtDate(r.done_date)}</div>}</span></label>
          ))}
        </div>
      </div>
    )
  }
  return (
    <div>
      <div className="toolbar"><div><h1>Ritmo de trabajo</h1><div style={{ color: '#6b7280', fontSize: 12 }}>Checklist diario, semanal (periodo desde el lunes) y mensual. Lo pendiente de periodos anteriores aparece como carga administrativa.</div></div><span className="spacer" /><input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ width: 160 }} /></div>
      <div className="grid cols-3"><Block f="diario" /><Block f="semanal" /><Block f="mensual" /></div>
      {data.backlog.length > 0 && (
        <div className="card"><h2>Carga administrativa pendiente ({data.backlog.length})</h2>
          <div className="checklist">{data.backlog.map((r: any) => <label key={r.id}><input type="checkbox" checked={r.done} onChange={() => toggle(r)} disabled={!canEdit} /><span>{r.name} <span className="badge warn">{FREQ[r.frequency]} · {fmtDate(r.period_date)}</span></span></label>)}</div>
        </div>
      )}
    </div>
  )
}
