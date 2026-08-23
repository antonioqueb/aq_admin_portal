import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import RecordTable from '../components/RecordTable'
import Many2one from '../components/Many2one'

export default function ResourceList() {
  const { resource = '' } = useParams()
  const { schema, toast } = useApp()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const res = schema?.resources[resource]
  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState(sp.get('q') || '')
  const [order, setOrder] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 60
  const filters = useMemo(() => { const f: Record<string, any> = {}; sp.forEach((v, k) => { if (k.startsWith('f.')) f[k.slice(2)] = v }); return f }, [sp])
  const load = useCallback(() => {
    if (!res) return
    api.list(resource, { search, filters, order: order || undefined, limit, offset }).then(r => { setRecords(r.records); setTotal(r.total) }).catch(e => toast(e.message, 'err'))
  }, [res, resource, search, filters, order, offset, toast])
  useEffect(() => { setOffset(0) }, [resource, search, filters])
  useEffect(() => { load() }, [load])
  if (!res) return <div className="empty">Recurso no disponible para su rol.</div>
  const setFilter = (k: string, v: any) => {
    const n = new URLSearchParams(sp)
    if (v === '' || v == null) n.delete('f.' + k); else n.set('f.' + k, String(v))
    setSp(n)
  }
  const onSort = (f: string) => setOrder(order === f + ' asc' ? f + ' desc' : f + ' asc')
  return (
    <div>
      <div className="toolbar">
        <div><h1>{res.label}</h1><div style={{ color: '#6b7280', fontSize: 12 }}>{total} registros</div></div>
        <span className="spacer" />
        {res.can.create && <button className="btn" onClick={() => nav(`/r/${resource}/new`)}>+ Nuevo {res.singular.toLowerCase()}</button>}
      </div>
      <div className="card tight">
        <div className="filters">
          <input type="text" placeholder="Buscar…" value={search} onChange={e => setSearch(e.target.value)} />
          {res.filters.map(fn => {
            const f = res.fields[fn]; if (!f) return null
            if (f.type === 'selection') return <select key={fn} value={filters[fn] || ''} onChange={e => setFilter(fn, e.target.value)}><option value="">{f.string}: todos</option>{f.selection!.map(s => <option key={s[0]} value={s[0]}>{s[1]}</option>)}</select>
            if (f.type === 'boolean') return <select key={fn} value={filters[fn] || ''} onChange={e => setFilter(fn, e.target.value)}><option value="">{f.string}: todos</option><option value="true">Sí</option><option value="false">No</option></select>
            if (f.type === 'many2one') return <div key={fn} style={{ minWidth: 200 }}><Many2one model={f.relation!} value={filters[fn] ? { id: Number(filters[fn]), name: sp.get('n.' + fn) || f.string + ' #' + filters[fn] } : null} onChange={v => { const n = new URLSearchParams(sp); if (v) { n.set('f.' + fn, String(v.id)); n.set('n.' + fn, v.name) } else { n.delete('f.' + fn); n.delete('n.' + fn) } setSp(n) }} /></div>
            return null
          })}
          {Object.keys(filters).length > 0 && <button className="btn link small" onClick={() => setSp(new URLSearchParams())}>Limpiar filtros</button>}
        </div>
        <RecordTable res={res} records={records} onOpen={r => nav(`/r/${resource}/${r.id}`)} order={order} onSort={onSort} />
        <div className="pager">
          <button className="btn secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>‹ Anterior</button>
          <span>{offset + 1}–{Math.min(offset + limit, total)} de {total}</span>
          <button className="btn secondary small" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Siguiente ›</button>
        </div>
      </div>
    </div>
  )
}
