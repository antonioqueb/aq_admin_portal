import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import OpsExtras from '../components/OpsExtras'
import AdminExtras from '../components/AdminExtras'
import { useApp } from '../context'
import { FieldRow } from '../components/Field'
import SubTable from '../components/SubTable'
import Attachments from '../components/Attachments'
import Timeline from '../components/Timeline'

export default function ResourceForm() {
  const { resource = '', id } = useParams()
  const [sp] = useSearchParams()
  const { schema, user, toast, rapi, base, app } = useApp()
  const nav = useNavigate()
  const res = schema?.resources[resource]
  const isNew = !id
  const [rec, setRec] = useState<any>(null)
  const [dirty, setDirty] = useState<Record<string, any>>({})
  const [tab, setTab] = useState('form')
  const [saving, setSaving] = useState(false)
  const load = useCallback(() => {
    if (!res) return
    if (isNew) {
      const d: any = {}
      sp.forEach((v, k) => { if (k.startsWith('d.')) { const fn = k.slice(2); const f = res.fields[fn]; if (f?.type === 'many2one') d[fn] = { id: Number(v), name: sp.get('n.' + fn) || '#' + v }; else d[fn] = v } })
      setRec(d); setDirty(d); return
    }
    rapi.read(resource, Number(id)).then(r => { setRec(r.record); setDirty({}) }).catch(e => { toast(e.message, 'err'); nav(`${base}/r/${resource}`) })
  }, [res, resource, id, isNew, sp, toast, nav, rapi, base])
  useEffect(() => { load() }, [load])
  if (!res) return <div className="empty">Recurso no disponible para su rol.</div>
  if (!rec) return <div className="empty">Cargando…</div>
  const canWrite = isNew ? res.can.create : res.can.write
  const canDirection = app === 'ops' ? true : user?.role === 'direccion'
  const value = (f: string) => (f in dirty ? dirty[f] : rec[f])
  const set = (f: string, v: any) => setDirty(d => ({ ...d, [f]: v }))
  const save = async () => {
    setSaving(true)
    try {
      if (isNew) { const r = await rapi.create(resource, dirty); toast('Creado', 'ok'); nav(`${base}/r/${resource}/${r.record.id}`, { replace: true }) }
      else { const r = await rapi.write(resource, Number(id), dirty); setRec(r.record); setDirty({}); toast('Guardado', 'ok') }
    } catch (e: any) { toast(e.message, 'err') } finally { setSaving(false) }
  }
  const run = async (a: { name: string; label: string }) => {
    if (Object.keys(dirty).length && !confirm('Hay cambios sin guardar. ¿Ejecutar la acción de todos modos?')) return
    if (!confirm(`¿Ejecutar "${a.label}"?`)) return
    try { const r = await rapi.action(resource, Number(id), a.name); setRec(r.record); toast(`${a.label}: realizado`, 'ok') } catch (e: any) { toast(e.message, 'err') }
  }
  const remove = async () => {
    if (!confirm('¿Archivar/eliminar este registro? Esta acción queda en la bitácora.')) return
    try { await api.remove(resource, Number(id)); toast('Registro archivado', 'ok'); nav(`${base}/r/${resource}`) } catch (e: any) { toast(e.message, 'err') }
  }
  const groupedFields = new Set(res.groups.flatMap(g => g.fields))
  const tabFields = new Set(res.tabs.map(t => t.field))
  const others = Object.keys(res.fields).filter(f => !groupedFields.has(f) && !tabFields.has(f) && res.fields[f].type !== 'one2many' && !['active', 'last_activity_date', 'notes', 'currency_id'].includes(f))
  return (
    <div>
      <div className="toolbar">
        <div>
          <div style={{ fontSize: 12, color: '#6b7280' }}><a href="#" onClick={e => { e.preventDefault(); nav(`${base}/r/${resource}`) }}>{res.label}</a> / {isNew ? 'Nuevo' : rec.display_name}</div>
          <h1>{isNew ? `Nuevo ${res.singular.toLowerCase()}` : rec.display_name}</h1>
        </div>
        <span className="spacer" />
        {canWrite && <button className="btn" disabled={saving || !Object.keys(dirty).length} onClick={save}>{saving ? 'Guardando…' : 'Guardar'}</button>}
        {Object.keys(dirty).length > 0 && !isNew && <button className="btn secondary" onClick={() => setDirty({})}>Descartar</button>}
        {!isNew && res.actions.map(a => <button key={a.name} className="btn secondary" onClick={() => run(a)}>{a.label}</button>)}
        {!isNew && res.can.delete && <button className="btn danger small" onClick={remove}>Archivar</button>}
      </div>
      {resource === 'documents' && canWrite && (
        <div className="alert info" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          Nomenclatura estándar: <code>AAAA-MM-DD_Tipo_Contraparte_Versión</code>
          <button className="btn secondary small" onClick={async () => {
            const cp = value('partner_id')?.name || value('employee_id')?.name || value('vendor_id')?.name || value('project_id')?.name || ''
            const r = await api.get('/documents/suggest-name', { doc_type: value('document_type') || value('folder_type') || 'DOC', counterparty: cp, version: 'v' + (value('version') || '1'), date: value('doc_date') || undefined })
            set('name', r.name)
          }}>Sugerir nombre</button>
        </div>
      )}
      {res.sensitive && <div className="alert info">Información confidencial: no elimine, mueva ni sustituya documentos de este expediente sin validación de Dirección.</div>}
      {!isNew && app === 'ops' && <OpsExtras resource={resource} record={rec} reload={load} />}
      {!isNew && app === 'admin' && <AdminExtras resource={resource} record={rec} />}
      {!isNew && (
        <div className="tabs">
          <button className={tab === 'form' ? 'active' : ''} onClick={() => setTab('form')}>Ficha</button>
          {res.tabs.map(t => <button key={t.field} className={tab === t.field ? 'active' : ''} onClick={() => setTab(t.field)}>{t.label} ({(rec[t.field] || []).length})</button>)}
          {res.attachments && <button className={tab === '_att' ? 'active' : ''} onClick={() => setTab('_att')}>Archivos y evidencias</button>}
          <button className={tab === '_hist' ? 'active' : ''} onClick={() => setTab('_hist')}>Historial y notas</button>
        </div>
      )}
      {tab === 'form' && (
        <div className="grid cols-2">
          {res.groups.map(g => (
            <div className="card" key={g.title}>
              <h3>{g.title}</h3>
              {g.fields.filter(f => res.fields[f] && res.fields[f].type !== 'one2many').map(f => <FieldRow key={f} f={res.fields[f]} value={value(f)} onChange={v => set(f, v)} canDirection={canDirection} disabled={!canWrite} />)}
            </div>
          ))}
          {others.length > 0 && <div className="card"><h3>Otros</h3>{others.map(f => <FieldRow key={f} f={res.fields[f]} value={value(f)} onChange={v => set(f, v)} canDirection={canDirection} disabled={!canWrite} />)}</div>}
        </div>
      )}
      {!isNew && res.tabs.map(t => tab === t.field && <div className="card" key={t.field}><SubTable tab={t} parentId={Number(id)} parentName={rec.display_name} /></div>)}
      {!isNew && tab === '_att' && <div className="card"><Attachments resource={resource} id={Number(id)} canWrite={res.can.write} /></div>}
      {!isNew && tab === '_hist' && <div className="card"><Timeline resource={resource} id={Number(id)} /></div>}
    </div>
  )
}
