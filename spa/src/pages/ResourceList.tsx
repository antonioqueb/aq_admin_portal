import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from '../context'
import RecordTable from '../components/RecordTable'
import Many2one from '../components/Many2one'
import { useActiveProject } from '../project'
import { api, ops } from '../api'

export default function ResourceList() {
  const { resource = '' } = useParams()
  const { schema, toast, rapi, base, user, app } = useApp()
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const res = schema?.resources[resource]
  const active = useActiveProject()
  const projField = app === 'ops' && res ? (resource === 'projects' ? 'id' : res.fields.project_id ? 'project_id' : res.fields.ops_project_id ? 'ops_project_id' : res.tabs?.length === 0 && res.fields.meeting_id ? 'meeting_id.project_id' : res.fields.case_id ? 'case_id.project_id' : null) : null
  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const [search, setSearch] = useState(sp.get('q') || '')
  const [order, setOrder] = useState('')
  const [offset, setOffset] = useState(0)
  const [views, setViews] = useState<any[]>([])
  const loadViews = useCallback(() => { if (app === 'ops') ops.views(resource).then(r => setViews(r.views)).catch(() => {}) }, [app, resource])
  useEffect(() => { loadViews() }, [loadViews])
  const limit = 60
  const filters = useMemo(() => { const f: Record<string, any> = {}; sp.forEach((v, k) => { if (k.startsWith('f.')) f[k.slice(2)] = v }); return f }, [sp])
  const load = useCallback(() => {
    if (!res) return
    rapi.list(resource, { search, filters, order: order || undefined, limit, offset, domain: projField && active ? [[projField, '=', active.id]] : undefined }).then(r => { setRecords(r.records); setTotal(r.total) }).catch(e => toast(e.message, 'err'))
  }, [res, resource, search, filters, order, offset, toast, rapi, active, projField])
  useEffect(() => { setOffset(0) }, [resource, search, filters, active])
  useEffect(() => { load() }, [load])
  if (!res) return <div className="empty">Recurso no disponible para su rol.</div>
  const setFilter = (k: string, v: any) => {
    const n = new URLSearchParams(sp)
    if (v === '' || v == null) n.delete('f.' + k); else n.set('f.' + k, String(v))
    setSp(n)
  }
  const onSort = (f: string) => setOrder(order === f + ' asc' ? f + ' desc' : f + ' asc')
  const saveFilter = async () => {
    const name = prompt('Nombre del filtro guardado'); if (!name) return
    const names: Record<string, string> = {}; sp.forEach((v, k) => { if (k.startsWith('n.')) names[k] = v })
    await ops.saveView({ name, resource, view_mode: 'list', filters: { filters, search, order, names }, shared: confirm('¿Compartir con el equipo?') }); loadViews(); toast('Filtro guardado', 'ok')
  }
  const applyView = (v: any) => { const n = new URLSearchParams(); Object.entries(v.filters.filters || {}).forEach(([k, val]) => n.set('f.' + k, String(val))); Object.entries(v.filters.names || {}).forEach(([k, val]) => n.set(k, String(val))); setSp(n); setSearch(v.filters.search || ''); setOrder(v.filters.order || '') }
  const exportCsv = async () => {
    if (!user?.can_export) { toast('Exportación controlada: su cuenta no tiene permiso de exportación. Solicítelo a Dirección / propietario de plataforma.', 'err'); return }
    if (app === 'ops') { window.open(rapi.exportUrl(resource, { search, filters }), '_blank'); return }
    try {
      const r = await rapi.list(resource, { search, filters, order: order || undefined, limit: 500, offset: 0 })
      const cols = res.list.filter(c => res.fields[c])
      const cell = (c: string, v: any) => {
        const f = res.fields[c]
        if (v == null) return ''
        if (f.type === 'many2one') return v.name
        if (f.type === 'many2many' || f.type === 'one2many') return Array.isArray(v) ? v.map((x: any) => x.name).join('; ') : ''
        if (f.type === 'selection') return (f.selection || []).find(s => s[0] === v)?.[1] ?? v
        if (f.type === 'boolean') return v ? 'Sí' : 'No'
        return String(v).replace(/<[^>]+>/g, ' ')
      }
      const esc = (x: string) => '"' + x.replace(/"/g, '""') + '"'
      const lines = [cols.map(c => esc(res.fields[c].string)).join(',')].concat(r.records.map((rec: any) => cols.map(c => esc(cell(c, rec[c]))).join(',')))
      const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${resource}_${new Date().toISOString().slice(0, 10)}.csv`; a.click()
      toast(`Exportados ${r.records.length} registros`, 'ok')
    } catch (e: any) { toast(e.message, 'err') }
  }
  return (
    <div>
      <div className="toolbar">
        <div><h1>{res.label}</h1><div style={{ color: 'var(--muted)', fontSize: 12 }}>{total} registros{projField && active && <> · filtrado por <b>{active.name}</b></>}{projField && !active && app === 'ops' && ' · todos los proyectos'}</div></div>
        <span className="spacer" />
        {resource === 'google_inbox' && <>
          <button className="btn secondary" disabled={syncing} onClick={async () => { setSyncing(true); try { await api.post('/google/sync'); toast('Sincronización completada', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } finally { setSyncing(false) } }}>{syncing ? 'Sincronizando…' : 'Sincronizar correo'}</button>
          <button className="btn secondary" disabled={syncing} title="Trae y procesa el correo de los últimos 30 días" onClick={async () => { setSyncing(true); try { await api.post('/google/sync', { days: 30 }); toast('Correo de los últimos 30 días sincronizado', 'ok'); load() } catch (e: any) { toast(e.message, 'err') } finally { setSyncing(false) } }}>Traer 30 días</button>
        </>}
        <button className="btn secondary" onClick={exportCsv}>Exportar CSV</button>
        {res.can.create && <button className="btn" onClick={() => nav(`${base}/r/${resource}/new` + (app === 'ops' && active && res.fields.project_id ? `?d.project_id=${active.id}&n.project_id=${encodeURIComponent(active.name)}` : ''))}>+ Nuevo {res.singular.toLowerCase()}</button>}
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
          {app === 'ops' && <button className="btn secondary small" onClick={saveFilter}>Guardar filtro</button>}
        </div>
        {app === 'ops' && views.length > 0 && <div className="chip-row">{views.map(v => <span key={v.id}><button onClick={() => applyView(v)}>{v.name}{v.shared ? ' · equipo' : ''}</button>{v.mine && <button title="Eliminar" onClick={() => ops.deleteView(v.id).then(loadViews)}>✕</button>}</span>)}</div>}
        <RecordTable res={res} records={records} onOpen={r => nav(`${base}/r/${resource}/${r.id}`)} order={order} onSort={onSort} />
        <div className="pager">
          <button className="btn secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>‹ Anterior</button>
          <span>{offset + 1}–{Math.min(offset + limit, total)} de {total}</span>
          <button className="btn secondary small" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Siguiente ›</button>
        </div>
      </div>
    </div>
  )
}
